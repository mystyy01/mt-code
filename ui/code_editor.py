from textual import events
from textual.widgets import TextArea, Static, Input, OptionList
from textual.widgets.option_list import Option
from core.file_management import read_file, delete_file, save_file
from typing import Literal
from textual.message import Message
from textual.events import Event
from textual.content import Content
from rich.console import RenderableType
import logging 
from utils.add_languages import register_supported_languages
from commands.messages import EditorSavedAs, UseFile, EditorOpenFile, EditorSaveFile, WorkspaceNextTab, TabMessage, CompletionSelected
from lsp.pyright import PyrightServer
from lsp.completion_filter import CompletionFilter  # Add this import
from pathlib import Path
from ui.completions_overlay import CompletionsOverlay
import asyncio
from ui.overlay import Overlay

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class CodeEditor(TextArea):
    def __init__(self, tab_id: str, file_path="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path if file_path else ""
        self.tab_id = tab_id
        self.pairs = {
            "(": ")",
            "[": "]",
            "{": "}",
        }
        self.lsp = None
        self._completion_task: asyncio.Task | None = None
        self._completion_delay = 0.3
        self._lsp_initialized = False
        self._completions_overlay = None
        self._last_completion_cursor = None
        self._current_completions = []
            
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
        if self.language == "python" and self.file_path:
            logging.info(f"Initializing LSP for {self.file_path}")
            try:
                self.lsp = PyrightServer(Path(self.file_path).parent.absolute())
                await self.lsp.start()
                
                init_response = await self.lsp.send_request(
                    "initialize",
                    {
                        "processId": None,
                        "rootUri": Path(self.file_path).parent.as_uri(),
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
                
                await self.did_mount_lsp()
            except Exception as e:
                logging.error(f"Failed to initialize LSP: {e}", exc_info=True)
                self.lsp = None
                self._lsp_initialized = False
        
        if self.file_path:
            self.load_text_silent(read_file(self.file_path))
        else:
            self.text = ""

    async def did_mount_lsp(self):
        """Send didOpen notification to LSP server."""
        if self.lsp and self.file_path and self._lsp_initialized:
            logging.info(f"Sending didOpen for {self.file_path}")
            try:
                await self.lsp.send_notification(
                    "textDocument/didOpen",
                    {
                        "textDocument": {
                            "uri": Path(self.file_path).as_uri(),
                            "languageId": self.language,
                            "version": 1,
                            "text": self.text
                        }
                    }
                )
            except Exception as e:
                logging.error(f"Failed to send didOpen: {e}", exc_info=True)

    async def on_text_area_changed(self, event: TextArea.Changed):
        """Handle text changes and notify LSP server."""
        if event.text_area.id == self.id:
            if self.lsp and self.file_path and self._lsp_initialized:
                logging.info("Text changed, notifying LSP")
                try:
                    await self.lsp.send_notification(
                        "textDocument/didChange",
                        {
                            "textDocument": {
                                "uri": Path(self.file_path).as_uri(),
                                "version": 1
                            },
                            "contentChanges": [{"text": self.text}]
                        }
                    )
                except Exception as e:
                    logging.error(f"Failed to send didChange: {e}", exc_info=True)
                
            if self._completion_task:
                self._completion_task.cancel()

            self._completion_task = asyncio.create_task(self._debounced_completions())

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
                    "textDocument": {"uri": Path(self.file_path).as_uri()},
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
            if self._completions_overlay:
                self._completions_overlay.remove()
                self._completions_overlay = None
                self._last_completion_cursor = None
                self._current_completions = []
            return
        
        # Get text before cursor for context
        line, col = self.cursor_location
        current_line = str(self.get_line(line))
        text_before_cursor = current_line[:col]
        
        # Filter and sort completions based on relevance
        items = CompletionFilter.filter_and_sort(raw_items, text_before_cursor)
        
        if not items:
            logging.info("No relevant completions after filtering")
            if self._completions_overlay:
                self._completions_overlay.remove()
                self._completions_overlay = None
                self._last_completion_cursor = None
                self._current_completions = []
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

    async def on_tab_message(self, message: TabMessage):
        logging.info("code_editor received tab")
        """Handle tab key press for completion insertion."""
        if self._completions_overlay and self._current_completions:
            completion = self._current_completions[0]
            label = completion.get("label", "")
            insert_text = completion.get("insertText", label)
            
            line, col = self.cursor_location
            current_line = str(self.get_line(line))
            text_before_cursor = current_line[:col]
            
            words = text_before_cursor.split()
            if words:
                partial = words[-1]
                if insert_text.startswith(partial):
                    remaining = insert_text[len(partial):]
                    self.insert(remaining)
                    logging.info(f"Tab completion: inserted '{remaining}' (full: {insert_text}, partial: {partial})")
                else:
                    self.insert(insert_text)
                    logging.info(f"Tab completion: inserted full '{insert_text}'")
            else:
                self.insert(insert_text)
                logging.info(f"Tab completion: inserted '{insert_text}'")
            
            self._completions_overlay.remove()
            self._completions_overlay = None
            self._last_completion_cursor = None
            self._current_completions = []
            
            message.stop()
        else:
            self.insert("    ")
            message.stop()

    def change_language(self, language: str | None) -> None:
        """Change the syntax highlighting language."""
        logging.info(f"Changed syntax to {language}")
        self.language = language
        if language != "python":
            self.lsp = None
            self._lsp_initialized = False

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
        if self._completions_overlay and self._last_completion_cursor:
            current_cursor = self.cursor_location
            if (current_cursor[0] != self._last_completion_cursor[0] or 
                abs(current_cursor[1] - self._last_completion_cursor[1]) > 10):
                logging.info("Cursor moved away, closing completions")
                self._completions_overlay.remove()
                self._completions_overlay = None
                self._last_completion_cursor = None
                self._current_completions = []
        
        if self._completions_overlay and event.key not in ["escape", "tab"]:
            self._completions_overlay.remove()
            self._completions_overlay = None
            self._last_completion_cursor = None
            self._current_completions = []
        
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
            return super()._on_key(event)

        if event.character in self.pairs:
            self.insert(event.character + self.pairs[event.character])
            self.move_cursor_relative(columns=-1)
            event.prevent_default()

        elif event.character in self.pairs.values():
            try:
                char = str(self.get_line(self.cursor_location[0]))[self.cursor_location[1]]
                if char == event.character:
                    self.move_cursor_relative(columns=1)
                    event.prevent_default()
            except IndexError:
                pass

        elif event.character == '"':
            try:
                char = str(self.get_line(self.cursor_location[0]))[self.cursor_location[1]]
                if char == '"':
                    self.move_cursor_relative(columns=1)
                else:
                    self.insert('""')
                    self.move_cursor_relative(columns=-1)
                event.prevent_default()
            except IndexError:
                self.insert('""')
                self.move_cursor_relative(columns=-1)
                event.prevent_default()

        elif event.character == "'":
            try:
                char = str(self.get_line(self.cursor_location[0]))[self.cursor_location[1]]
                if char == "'":
                    self.move_cursor_relative(columns=1)
                else:
                    self.insert("''")
                    self.move_cursor_relative(columns=-1)
                event.prevent_default()
            except IndexError:
                self.insert("''")
                self.move_cursor_relative(columns=-1)
                event.prevent_default()

        if event.key == "ctrl+a":
            self.select_all()
        if event.key == "ctrl+s":
            self.save_file()
        
        if event.key == "ctrl+space":
            asyncio.create_task(self.show_completions())
            event.prevent_default()