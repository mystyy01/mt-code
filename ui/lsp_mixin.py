"""LSP (Language Server Protocol) mixin for CodeEditor.

This module contains all LSP-related functionality including:
- Server initialization and lifecycle
- Completion requests and display
- Document synchronization (didOpen, didChange)
"""

import asyncio
import logging
import re
from pathlib import Path

from lsp.pyright import PyrightServer
from lsp.completion_filter import CompletionFilter
from ui.completions_overlay import CompletionsOverlay
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class LSPMixin:
    """Mixin class providing LSP functionality to CodeEditor."""

    def _init_lsp_state(self):
        """Initialize LSP-related state variables. Call from __init__."""
        self.lsp = None
        self._completion_task: asyncio.Task | None = None
        self._completion_delay = 0.3
        self._lsp_initialized = False
        self._completions_overlay = None
        self._last_completion_cursor = None
        self._current_completions = []

    async def _init_lsp(self):
        """Initialize LSP server for Python files. Call from on_mount."""
        if self.language == "python" and self.file_path:
            logging.info(f"Initializing LSP for {self.file_path}")
            try:
                self.lsp = PyrightServer(Path(self.file_path).resolve().parent)
                await self.lsp.start()

                init_response = await self.lsp.send_request(
                    "initialize",
                    {
                        "processId": None,
                        "rootUri": Path(self.file_path).resolve().parent.as_uri(),
                        "capabilities": {
                            "textDocument": {
                                "completion": {
                                    "completionItem": {
                                        "snippetSupport": True
                                    }
                                }
                            }
                        }
                    }
                )
                logging.info(f"LSP initialized: {init_response}")

                await self.lsp.send_notification("initialized", {})
                self._lsp_initialized = True

                await self._lsp_did_open()
            except Exception as e:
                logging.error(f"Failed to initialize LSP: {e}", exc_info=True)
                self.lsp = None
                self._lsp_initialized = False

    async def _lsp_did_open(self):
        """Send didOpen notification to LSP server."""
        if self.lsp and self.file_path and self._lsp_initialized:
            logging.info(f"Sending didOpen for {self.file_path}")
            try:
                await self.lsp.send_notification(
                    "textDocument/didOpen",
                    {
                        "textDocument": {
                            "uri": Path(self.file_path).resolve().as_uri(),
                            "languageId": self.language,
                            "version": 1,
                            "text": self.text
                        }
                    }
                )
            except Exception as e:
                logging.error(f"Failed to send didOpen: {e}", exc_info=True)

    async def _lsp_did_change(self):
        """Send didChange notification to LSP server."""
        if self.lsp and self.file_path and self._lsp_initialized:
            logging.info("Text changed, notifying LSP")
            try:
                await self.lsp.send_notification(
                    "textDocument/didChange",
                    {
                        "textDocument": {
                            "uri": Path(self.file_path).resolve().as_uri(),
                            "version": 1
                        },
                        "contentChanges": [{"text": self.text}]
                    }
                )
            except Exception as e:
                logging.error(f"Failed to send didChange: {e}", exc_info=True)

    async def _debounced_completions(self):
        """Debounce completion requests to avoid overwhelming the LSP server."""
        try:
            await asyncio.sleep(self._completion_delay)
            await self.show_completions()
        except asyncio.CancelledError:
            pass

    async def request_completions(self):
        """Request completions from LSP server at current cursor position."""
        if not self.lsp or not self.file_path or not self._lsp_initialized:
            logging.info(
                f"Cannot request completions: lsp={bool(self.lsp)}, "
                f"file={bool(self.file_path)}, init={self._lsp_initialized}"
            )
            return []

        line, col = self.cursor_location
        logging.info(f"Requesting completions at line={line}, col={col}")

        try:
            resp = await self.lsp.send_request(
                "textDocument/completion",
                {
                    "textDocument": {"uri": Path(self.file_path).resolve().as_uri()},
                    "position": {"line": line, "character": col}
                }
            )
            logging.info(f"Completion response: {resp}")

            result = resp.get("result", [])
            if isinstance(result, dict) and "items" in result:
                return result["items"]
            return result if isinstance(result, list) else []
        except Exception as e:
            logging.error(f"Error requesting completions: {e}", exc_info=True)
            return []

    def _get_cursor_screen_position(self):
        """Calculate the screen position (x, y) of the cursor."""
        try:
            region = self.region
            cursor_line, cursor_col = self.cursor_location
            scroll_y = self.scroll_offset.y
            scroll_x = self.scroll_offset.x
            line_number_width = len(str(self.document.line_count)) + 2

            visible_line = cursor_line - scroll_y
            visible_col = cursor_col - scroll_x + line_number_width

            screen_x = region.x + visible_col
            screen_y = region.y + visible_line

            logging.info(f"Cursor screen position: x={screen_x}, y={screen_y}")
            return (screen_x, screen_y)
        except Exception as e:
            logging.error(f"Error calculating cursor position: {e}", exc_info=True)
            return None

    async def show_completions(self):
        """Show completion suggestions in an overlay near the cursor."""
        raw_items = await self.request_completions()
        logging.info(f"Got {len(raw_items) if raw_items else 0} raw completion items")

        if not raw_items:
            self._close_completions_overlay()
            return

        # Get text before cursor for context
        line, col = self.cursor_location
        current_line = str(self.get_line(line))
        text_before_cursor = current_line[:col]

        # Filter and sort completions based on relevance
        items = CompletionFilter.filter_and_sort(raw_items, text_before_cursor)

        if not items:
            logging.info("No relevant completions after filtering")
            self._close_completions_overlay()
            return

        # Log filtered items
        for i, item in enumerate(items[:5]):
            logging.info(f"Filtered completion {i}: {item.get('label', '')}")

        if self._completions_overlay:
            self._completions_overlay.remove()

        self._current_completions = items[:5]
        self._last_completion_cursor = self.cursor_location

        cursor_pos = self._get_cursor_screen_position()

        self._completions_overlay = CompletionsOverlay(items, id="completions_overlay")

        screen = self.screen
        await screen.mount(self._completions_overlay)

        if cursor_pos:
            x, y = cursor_pos
            self._completions_overlay.styles.offset = (x, max(0, y + 2))
            logging.info(f"Positioned overlay at x={x}, y={y + 2}")

        labels = [item.get("label", "") for item in items[:5]]
        logging.info(f"Showing completions: {labels}")

    def _close_completions_overlay(self):
        """Close the completions overlay if open."""
        if self._completions_overlay:
            self._completions_overlay.remove()
            self._completions_overlay = None
            self._last_completion_cursor = None
            self._current_completions = []

    def _handle_tab_completion(self):
        """Handle tab key press for completion insertion. Returns True if handled."""
        if self._completions_overlay and self._current_completions:
            completion = self._current_completions[0]
            label = completion.get("label", "")
            insert_text = completion.get("insertText", label)

            # Log the full completion item to understand auto-import structure
            logging.info(f"Full completion item: {completion}")

            line, col = self.cursor_location
            current_line = str(self.get_line(line))
            text_before_cursor = current_line[:col]

            # Use regex to find partial word - handles brackets, dots, etc.
            match = re.search(r'(\w+)$', text_before_cursor)
            if match:
                partial = match.group(1)
                # Delete the partial word first, then insert full completion
                for _ in range(len(partial)):
                    self.action_delete_left()
                self.insert(insert_text)
                logging.info(
                    f"Tab completion: deleted '{partial}', inserted '{insert_text}'"
                )
            else:
                self.insert(insert_text)
                logging.info(f"Tab completion: inserted '{insert_text}'")

            # Handle auto-imports
            self._handle_auto_import(completion)

            self._close_completions_overlay()
            return True
        return False

    def _handle_auto_import(self, completion):
        """Handle auto-import by adding import statement at the top of the file."""
        label = completion.get("label", "")
        label_details = completion.get("labelDetails", {})
        description = label_details.get("description", "") if label_details else ""

        # Check if this is an auto-import completion
        is_auto_import = (
            label.endswith("- Auto-import") or
            "Auto-import" in description or
            completion.get("additionalTextEdits")
        )

        if not is_auto_import:
            return

        logging.info(f"Handling auto-import for: {label}")

        # Check for additionalTextEdits (standard LSP way)
        additional_edits = completion.get("additionalTextEdits", [])
        if additional_edits:
            logging.info(f"Additional text edits: {additional_edits}")
            for edit in additional_edits:
                self._apply_text_edit(edit)
            return

        # Fallback: parse the description to construct import statement
        # Description is typically like "(from module_name)"
        if description and description.startswith("(") and description.endswith(")"):
            # Extract module path, e.g., "(from os.path)" -> "os.path"
            import_source = description[1:-1]  # Remove parentheses
            if import_source.startswith("from "):
                module = import_source[5:]  # Remove "from "
                # Get the actual symbol name (remove "- Auto-import" suffix if present)
                symbol = label.replace(" - Auto-import", "").strip()
                import_statement = f"from {module} import {symbol}\n"
                self._add_import_to_file(import_statement)

    def _apply_text_edit(self, edit):
        """Apply a single LSP text edit."""
        try:
            range_info = edit.get("range", {})
            start = range_info.get("start", {})
            end = range_info.get("end", {})
            new_text = edit.get("newText", "")

            start_loc = (start.get("line", 0), start.get("character", 0))
            end_loc = (end.get("line", 0), end.get("character", 0))

            logging.info(f"Applying text edit: {start_loc} -> {end_loc}, text: {repr(new_text)}")
            self.replace(new_text, start=start_loc, end=end_loc)
        except Exception as e:
            logging.error(f"Failed to apply text edit: {e}", exc_info=True)

    def _add_import_to_file(self, import_statement):
        """Add an import statement at the top of the file (after existing imports)."""
        try:
            # Find the best location to insert the import
            lines = self.text.split("\n")
            insert_line = 0

            # Skip shebang, docstrings, and find the import section
            in_docstring = False
            docstring_char = None

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Handle docstrings
                if not in_docstring:
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        docstring_char = stripped[:3]
                        if stripped.count(docstring_char) >= 2:
                            # Single line docstring
                            continue
                        in_docstring = True
                        continue
                else:
                    if docstring_char in stripped:
                        in_docstring = False
                    continue

                # Skip comments and empty lines at the top
                if stripped.startswith("#") or stripped == "":
                    insert_line = i + 1
                    continue

                # Track import lines
                if stripped.startswith("import ") or stripped.startswith("from "):
                    insert_line = i + 1
                    continue

                # Stop at first non-import code
                break

            # Insert the import
            logging.info(f"Inserting import at line {insert_line}: {repr(import_statement)}")
            self.replace(import_statement, start=(insert_line, 0), end=(insert_line, 0))
        except Exception as e:
            logging.error(f"Failed to add import: {e}", exc_info=True)

    def _check_cursor_moved_from_completion(self):
        """Check if cursor moved away from completion position and close if so."""
        if self._completions_overlay and self._last_completion_cursor:
            current_cursor = self.cursor_location
            if (current_cursor[0] != self._last_completion_cursor[0] or
                    abs(current_cursor[1] - self._last_completion_cursor[1]) > 10):
                logging.info("Cursor moved away, closing completions")
                self._close_completions_overlay()
                return True
        return False

    def _disable_lsp(self):
        """Disable LSP (e.g., when changing to non-Python language)."""
        self.lsp = None
        self._lsp_initialized = False
