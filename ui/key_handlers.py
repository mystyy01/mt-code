"""Key handling mixin for CodeEditor.

This module contains key event handling including:
- Auto-pairing of brackets, quotes
- Keyboard shortcuts (ctrl+s, ctrl+a, etc.)
"""

import asyncio
import logging
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class KeyHandlersMixin:
    """Mixin class providing key handling functionality to CodeEditor."""

    def _init_key_handlers_state(self):
        """Initialize key handler state variables. Call from __init__."""
        self.pairs = {
            "(": ")",
            "[": "]",
            "{": "}",
        }
        # Keywords that trigger dedent on next line (Python)
        self.dedent_keywords = {"return", "break", "continue", "pass", "raise"}
        # Languages that use colon-based indentation
        self.colon_indent_languages = {"python"}
        # Languages that use brace-based indentation
        self.brace_indent_languages = {"javascript", "typescript", "c", "cpp", "java", "rust", "go", "json"}

    def _handle_key_event(self, event):
        """
        Handle key events for auto-pairing and shortcuts.
        Call from _on_key. Returns True if event was fully handled.
        """
        # Check if cursor moved away from completions
        self._check_cursor_moved_from_completion()

        # Close completions on most key presses except escape/tab
        if self._completions_overlay and event.key not in ["escape", "tab"]:
            self._close_completions_overlay()

        # Handle shift+backspace as regular backspace
        if self._handle_shift_backspace(event):
            return False  # Let parent handle modified event

        # Handle backspace on whitespace-only prefix (dedent by one level)
        if self._handle_indent_backspace(event):
            return True

        # Handle auto-pairing
        if self._handle_auto_pair(event):
            return True

        # Handle quotes
        if self._handle_quotes(event):
            return True

        # Handle auto-indentation on Enter
        if self._handle_auto_indent(event):
            return True

        # Handle shortcuts
        self._handle_shortcuts(event)

        return False

    def _handle_shift_backspace(self, event):
        """Normalize shift+backspace to regular backspace."""
        try:
            keyname = getattr(event, "key", None)
        except Exception:
            keyname = None

        if keyname and (
            keyname == "shift+backspace" or
            (keyname == "backspace" and getattr(event, "shift", False))
        ):
            try:
                event.key = "backspace"
                event.shift = False
            except Exception:
                pass
            return True
        return False

    def _handle_auto_pair(self, event):
        """Handle auto-pairing of brackets. Returns True if handled."""
        if event.character in self.pairs:
            self.insert(event.character + self.pairs[event.character])
            self.move_cursor_relative(columns=-1)
            event.prevent_default()
            return True

        if event.character in self.pairs.values():
            try:
                char = str(self.get_line(self.cursor_location[0]))[self.cursor_location[1]]
                if char == event.character:
                    self.move_cursor_relative(columns=1)
                    event.prevent_default()
                    return True
            except IndexError:
                pass

        return False

    def _handle_quotes(self, event):
        """Handle auto-pairing of quotes. Returns True if handled."""
        if event.character == '"':
            return self._handle_quote_char('"', event)
        elif event.character == "'":
            return self._handle_quote_char("'", event)
        return False

    def _handle_quote_char(self, quote_char, event):
        """Handle a specific quote character."""
        try:
            char = str(self.get_line(self.cursor_location[0]))[self.cursor_location[1]]
            if char == quote_char:
                self.move_cursor_relative(columns=1)
            else:
                self.insert(quote_char * 2)
                self.move_cursor_relative(columns=-1)
            event.prevent_default()
            return True
        except IndexError:
            self.insert(quote_char * 2)
            self.move_cursor_relative(columns=-1)
            event.prevent_default()
            return True

    def _handle_shortcuts(self, event):
        """Handle keyboard shortcuts."""
        if event.key == "ctrl+a":
            self.select_all()

        if event.key == "ctrl+s":
            self.save_file()

        if event.key == "ctrl+space":
            # Clear AI suggestion to show only LSP completions
            self.suggestion = ""
            # Cancel any pending AI suggestion request
            if hasattr(self, '_ai_suggestion_task') and self._ai_suggestion_task:
                self._ai_suggestion_task.cancel()
            asyncio.create_task(self.show_completions())
            event.prevent_default()

    def _handle_auto_indent(self, event):
        """Handle auto-indentation on Enter key. Returns True if handled."""
        if event.key != "enter":
            return False

        # Get current line and cursor position
        row, col = self.cursor_location
        current_line = str(self.get_line(row))

        # Calculate current indentation
        current_indent = self._get_line_indent(current_line)
        indent_str = " " * current_indent

        # Get the indent unit (spaces per level)
        indent_unit = getattr(self, "indent_width", 4)

        # Check if we should increase indent (line ends with colon for Python-like languages)
        should_increase = False
        if self.language in self.colon_indent_languages:
            stripped = current_line.rstrip()
            if stripped.endswith(":"):
                should_increase = True

        # Check if we should decrease indent (dedent keywords)
        should_decrease = False
        if self.language in self.colon_indent_languages:
            stripped = current_line.strip()
            before_paren = stripped.split("(")[0].split()
            first_word = before_paren[0] if before_paren else ""
            if first_word in self.dedent_keywords:
                should_decrease = True

        # Calculate new indentation
        if should_increase:
            new_indent = indent_str + " " * indent_unit
        elif should_decrease:
            # Dedent by one level, but not below 0
            new_indent_level = max(0, current_indent - indent_unit)
            new_indent = " " * new_indent_level
        else:
            new_indent = indent_str

        # Insert newline with appropriate indentation
        self.insert("\n" + new_indent)
        event.prevent_default()
        return True

    def _get_line_indent(self, line: str) -> int:
        """Get the number of leading spaces in a line."""
        count = 0
        for char in line:
            if char == " ":
                count += 1
            elif char == "\t":
                count += getattr(self, "indent_width", 4)
            else:
                break
        return count

    def _handle_indent_backspace(self, event):
        """Handle backspace to move cursor back one indent level when only whitespace before cursor."""
        if event.key != "backspace":
            return False

        row, col = self.cursor_location
        if col == 0:
            return False

        current_line = str(self.get_line(row))
        text_before_cursor = current_line[:col]

        # Only handle if text before cursor is all whitespace
        if not text_before_cursor.isspace():
            return False

        indent_unit = getattr(self, "indent_width", 4)

        # Calculate target column (previous indent level)
        remainder = col % indent_unit
        if remainder == 0:
            target_col = col - indent_unit
        else:
            target_col = col - remainder

        # Don't go below 0, and adjust for 0-indexing
        target_col = max(0, target_col + 1)

        # Delete the whitespace and move cursor
        self.replace("", start=(row, target_col), end=(row, col))

        event.prevent_default()
        return True
