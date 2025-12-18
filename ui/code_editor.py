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

            if self._completion_task:
                self._completion_task.cancel()

            self._completion_task = asyncio.create_task(self._debounced_completions())

    async def on_tab_message(self, message: TabMessage):
        """Handle tab key press for completion insertion."""
        logging.info("code_editor received tab")
        if self._handle_tab_completion():
            message.stop()
        else:
            self.insert("    ")
            message.stop()

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
