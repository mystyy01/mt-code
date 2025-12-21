"""CodeEditor widget - main text editing component.

This module provides the CodeEditor class which extends TextArea with:
- LSP integration (via LSPMixin)
- Key handling with auto-pairing (via KeyHandlersMixin)
- File operations (save, open)
- Syntax highlighting
"""

from textual import events
from textual.widgets import TextArea
from textual.content import Content
from rich.console import RenderableType
from typing import Literal
import logging
import asyncio

from core.file_management import read_file, save_file
from commands.messages import EditorSavedAs, EditorOpenFile, EditorSaveFile, TabMessage
from utils.add_languages import register_supported_languages
from ui.lsp_mixin import LSPMixin
from ui.key_handlers import KeyHandlersMixin
from core.paths import LOG_FILE_STR
from core.languages import get_language_for_file
from core.ai_config import get_ai_config

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class CodeEditor(LSPMixin, KeyHandlersMixin, TextArea):
    """Text editor widget with LSP support and auto-pairing."""

    def __init__(self, tab_id: str, file_path="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path if file_path else ""
        self.tab_id = tab_id

        # Initialize mixin state
        self._init_lsp_state()
        self._init_key_handlers_state()
        self._init_ai_suggestion_state()

        register_supported_languages(self)

    @classmethod
    def code_editor(
        cls,
        text: str = "",
        *,
        language: str | None = None,
        theme: str = "monokai",
        soft_wrap: bool = False,
        tab_behavior: Literal["focus", "indent"] = None,
        read_only: bool = False,
        show_cursor: bool = True,
        show_line_numbers: bool = True,
        line_number_start: int = 1,
        max_checkpoints: int = 50,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
        tooltip: RenderableType | None = None,
        compact: bool = False,
        highlight_cursor_line: bool = True,
        placeholder: str | Content = "",
        file: str = "",
        tab_id: str = ""
    ) -> "CodeEditor":
        """Construct a new `CodeEditor` with sensible defaults for editing code."""
        return cls(
            text="",
            language=language,
            theme=theme,
            soft_wrap=soft_wrap,
            tab_behavior=tab_behavior,
            read_only=read_only,
            show_cursor=show_cursor,
            show_line_numbers=show_line_numbers,
            line_number_start=line_number_start,
            max_checkpoints=max_checkpoints,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
            tooltip=tooltip,
            compact=compact,
            highlight_cursor_line=highlight_cursor_line,
            placeholder=placeholder,
            file_path=file,
            tab_id=tab_id
        )

    async def on_mount(self):
        """Initialize the editor when mounted."""
        # Auto-detect language from file extension
        if self.file_path and self.language is None:
            detected_lang = get_language_for_file(self.file_path)
            if detected_lang and detected_lang in self.available_languages:
                self.language = detected_lang
                logging.info(f"Auto-detected language: {detected_lang} for {self.file_path}")

        await self._init_lsp()

        if self.file_path:
            self.load_text_silent(read_file(self.file_path))
        else:
            self.text = ""

    async def on_text_area_changed(self, event: TextArea.Changed):
        """Handle text changes and notify LSP server."""
        if event.text_area.id == self.id:
            await self._lsp_did_change()

            # If AI is disabled, show LSP completions automatically
            ai_config = get_ai_config()
            if not ai_config.is_ai_enabled():
                if self._completion_task:
                    self._completion_task.cancel()
                self._completion_task = asyncio.create_task(self._debounced_completions())
            # Otherwise, AI suggestions triggered via update_suggestion()

    async def on_tab_message(self, message: TabMessage):
        """Handle tab key press for completion insertion or indentation."""
        logging.info(f"code_editor received tab (shift={message.shift})")

        # Check if there's an actual selection (not just cursor position)
        selection = self.selection
        has_selection = selection.start != selection.end

        if has_selection:
            # Selection exists: indent or dedent selected lines
            self._indent_selection(dedent=message.shift)
            message.stop()
            return

        # No selection
        if message.shift:
            # Shift+tab without selection: cycle tabs
            # Don't stop the message - let it bubble up, and post AppNextTab
            from commands.messages import AppNextTab
            self.post_message(AppNextTab())
            message.stop()
            return

        # Check for AI suggestion first
        if self.suggestion:
            # Only complete one line at a time
            lines = self.suggestion.split('\n')
            first_line = lines[0]
            self.insert(first_line)

            # Keep remaining lines as suggestion
            if len(lines) > 1:
                self.suggestion = '\n'.join(lines[1:])
            else:
                self.suggestion = ""
            message.stop()
            return

        # Normal tab behavior - try LSP completion, otherwise indent
        if self._handle_tab_completion():
            message.stop()
        else:
            self.insert("    ")
            message.stop()

    def _indent_selection(self, dedent: bool = False):
        """Indent or dedent all lines in the current selection."""
        selection = self.selection
        start_row = min(selection.start[0], selection.end[0])
        end_row = max(selection.start[0], selection.end[0])
        indent_str = " " * getattr(self, "indent_width", 4)

        # Process lines from bottom to top to preserve line numbers
        for row in range(end_row, start_row - 1, -1):
            line = str(self.get_line(row))

            if dedent:
                # Remove one level of indentation
                if line.startswith(indent_str):
                    new_line = line[len(indent_str):]
                    self.replace(new_line, start=(row, 0), end=(row, len(line)))
                elif line.startswith(" "):
                    # Remove as many spaces as possible up to indent_width
                    spaces_to_remove = 0
                    for char in line:
                        if char == " " and spaces_to_remove < len(indent_str):
                            spaces_to_remove += 1
                        else:
                            break
                    new_line = line[spaces_to_remove:]
                    self.replace(new_line, start=(row, 0), end=(row, len(line)))
            else:
                # Add one level of indentation
                new_line = indent_str + line
                self.replace(new_line, start=(row, 0), end=(row, len(line)))

    def change_language(self, language: str | None) -> None:
        """Change the syntax highlighting language."""
        logging.info(f"Changed syntax to {language}")
        self.language = language
        if language != "python":
            self._disable_lsp()

    def load_text_silent(self, text):
        """Load text into the TextArea without firing the Changed event."""
        self.history.clear()
        self._set_document(text, self.language)
        self.update_suggestion()

    def save_as(self):
        """Post a message to save the file with a new name."""
        self.post_message(EditorSavedAs(self.text))

    def open_file(self):
        """Post a message to open a file."""
        self.post_message(EditorOpenFile())

    def save_file(self):
        """Save the current file."""
        logging.info(f"Saving file: {self.file_path}")
        if self.file_path:
            logging.info("Saving to specified file path")
            save_file(self.file_path, self.text)
        else:
            logging.info("No file path, saving as")
            self.save_as()

        logging.info(f"Code editor tab_id: {self.tab_id}")
        self.post_message(EditorSaveFile(self.tab_id))

    def _on_key(self, event: events.Key) -> None:
        """Handle key events for auto-pairing and shortcuts."""
        if self._handle_key_event(event):
            return
        return super()._on_key(event)

    async def on_click(self, event: events.Click) -> None:
        """Handle mouse click events for ctrl+click go-to-definition."""
        logging.info(f"on_click triggered: x={event.x}, y={event.y}, ctrl={event.ctrl}, button={event.button}")
        if event.ctrl:
            logging.info("Ctrl+click detected!")
            # First, let the parent handle the click to position the cursor correctly
            # Then use cursor_location which is more reliable than manual calculation

            # Calculate position manually for comparison/debugging
            manual_position = self._click_to_document_position(event)
            logging.info(f"Manual calculated position: {manual_position}")

            # Get cursor position from click using TextArea's offset_to_location
            try:
                # offset in the event is relative to widget content
                click_offset = event.offset
                logging.info(f"Click offset: {click_offset}")

                # Use cursor_screen_offset to help debug
                logging.info(f"Current cursor_location before: {self.cursor_location}")

                # Try using the click coordinates with scroll offset
                scroll_y = self.scroll_offset.y
                scroll_x = self.scroll_offset.x
                gutter_width = self.gutter_width if hasattr(self, 'gutter_width') else 0
                logging.info(f"Gutter width: {gutter_width}, scroll: ({scroll_x}, {scroll_y})")

                # Attempt to get location from the actual click
                # The y coordinate should map directly to lines
                # But we may need to subtract 1 if there's a header
                doc_line = int(event.y + scroll_y)

                # Try with offset adjustment
                adjusted_line = doc_line - 1 if doc_line > 0 else 0
                logging.info(f"Trying adjusted line: {adjusted_line} (original: {doc_line})")

                # Get line text at both positions for debugging
                if doc_line < self.document.line_count:
                    logging.info(f"Line at doc_line={doc_line}: '{self.get_line(doc_line)}'")
                if adjusted_line < self.document.line_count:
                    logging.info(f"Line at adjusted_line={adjusted_line}: '{self.get_line(adjusted_line)}'")

                # Use adjusted position
                line_number_width = len(str(self.document.line_count)) + 2
                doc_col = max(0, int(event.x - line_number_width + scroll_x))
                doc_position = (adjusted_line, doc_col)

            except Exception as e:
                logging.error(f"Error getting position: {e}", exc_info=True)
                doc_position = manual_position

            logging.info(f"Final document position: {doc_position}")
            if doc_position:
                logging.info(f"Calling _goto_definition with position {doc_position}")
                await self._goto_definition(doc_position)
            else:
                logging.warning("Could not determine document position from click")
            event.stop()
            return
        else:
            logging.debug(f"Regular click (no ctrl): x={event.x}, y={event.y}")

    # === AI Suggestion Methods ===

    def _init_ai_suggestion_state(self):
        """Initialize AI suggestion state variables."""
        self._ai_suggestion_task: asyncio.Task | None = None
        self._ai_suggestion_delay = 0.8  # Delay before fetching AI suggestions
        self._last_ai_cursor = None
        self._ai_enabled = True

    def update_suggestion(self) -> None:
        """Override to trigger AI suggestions with debouncing."""
        # Check if AI is enabled
        ai_config = get_ai_config()
        if not ai_config.is_ai_enabled():
            self.suggestion = ""
            return

        # Cancel any pending AI suggestion request
        if self._ai_suggestion_task and not self._ai_suggestion_task.done():
            self._ai_suggestion_task.cancel()

        # Get current cursor position
        cursor_pos = self.cursor_location

        # Don't fetch if cursor hasn't moved meaningfully
        if cursor_pos == self._last_ai_cursor:
            return

        self._last_ai_cursor = cursor_pos

        # Start debounced AI suggestion fetch
        self._ai_suggestion_task = asyncio.create_task(self._debounced_ai_suggestion())

    async def _debounced_ai_suggestion(self):
        """Debounce AI suggestion requests."""
        try:
            await asyncio.sleep(self._ai_suggestion_delay)
            await self._fetch_ai_suggestion()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logging.error(f"Error in AI suggestion: {e}")

    async def _fetch_ai_suggestion(self):
        """Fetch AI suggestion for current cursor position."""
        try:
            # Get AI chat from app
            if not hasattr(self, 'app') or not hasattr(self.app, 'ai_view'):
                return

            ai_view = self.app.ai_view
            if not ai_view or not ai_view.ai_chat or not ai_view.ai_chat.is_available():
                return

            # Get context: text before cursor
            cursor_row, cursor_col = self.cursor_location
            lines = self.text.split('\n')

            # Get text up to cursor
            text_before = '\n'.join(lines[:cursor_row])
            if cursor_row < len(lines):
                text_before += '\n' + lines[cursor_row][:cursor_col]

            # Get a few lines after for context (but we're completing at cursor)
            text_after = ""
            if cursor_row < len(lines):
                text_after = lines[cursor_row][cursor_col:]
            if cursor_row + 1 < len(lines):
                text_after += '\n' + '\n'.join(lines[cursor_row + 1:cursor_row + 5])

            # Build prompt for completion
            prompt = f"""You are a code completion assistant. Analyze the code context and decide if there's a meaningful completion.

IMPORTANT: Only provide a suggestion if:
1. The user has left a comment asking for something to be implemented (e.g., "# TODO:", "# implement", "// add")
2. There's an obvious incomplete statement (e.g., function call missing arguments, incomplete expression)
3. The context strongly suggests what should come next (e.g., after "def " or "if ")

If there's no meaningful completion, respond with exactly: NO_SUGGESTION

If you have a suggestion, return ONLY the code to insert. No explanations, no markdown, no code blocks.

Language: {self.language or 'unknown'}

Code before cursor:
{text_before[-1500:]}

Code after cursor:
{text_after[:500]}

Response:"""

            # Send to AI (use a shorter timeout for suggestions)
            response = await asyncio.wait_for(
                ai_view.ai_chat.send_message(prompt, on_chunk=None),
                timeout=5.0
            )

            # Clean up response
            suggestion = self._clean_ai_suggestion(response)

            # Only set if we're still at the same cursor position
            if self.cursor_location == self._last_ai_cursor and suggestion:
                self.suggestion = suggestion
                logging.info(f"AI suggestion: {suggestion[:50]}...")

        except asyncio.TimeoutError:
            logging.debug("AI suggestion timed out")
        except Exception as e:
            logging.error(f"Error fetching AI suggestion: {e}")

    def _clean_ai_suggestion(self, response: str) -> str:
        """Clean AI response to extract just the completion."""
        response = response.strip()

        # Check for no suggestion response
        if response.upper() == "NO_SUGGESTION" or "NO_SUGGESTION" in response.upper():
            return ""

        # Remove markdown code blocks if present
        if response.startswith("```"):
            lines = response.split('\n')
            lines = lines[1:]  # Remove opening ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response = '\n'.join(lines)

        # Remove common prefixes the AI might add
        prefixes_to_remove = [
            "Here's the completion:",
            "Completion:",
            "Here is the completion:",
            "Here's the code:",
            "Code:",
        ]
        for prefix in prefixes_to_remove:
            if response.lower().startswith(prefix.lower()):
                response = response[len(prefix):].strip()

        return response
