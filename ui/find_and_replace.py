from textual import events
from textual.widgets import TextArea, Static, Input
from core.file_management import read_file, delete_file, save_file
from textual.containers import Container
from ui.editor_view import EditorView
from textual.message import Message
from typing import Literal
from ui.overlay import Overlay
from textual.content import Content
from rich.console import RenderableType
import logging 
logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
from textual.events import Key



class FindAndReplace(Container):
    def __init__(self, editor: EditorView, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.editor = editor
        logging.info(self.classes)
        self.add_class("find_and_replace")
        logging.info(self.classes)
        self.match_index = None
    def on_mount(self):
        self.classes = "overlay" 
    def on_key(self, event: Key):
        if event.key=="escape":
            self.remove()
    def on_mount(self):
        self.mount(Static("Find text"))
        self.position = Static("")
        self.text_input = Input(placeholder="text_to_find", classes="find_text_input")
        self.mount(self.text_input)
        self.text_input.focus()
        # self.mount(self.position)
    async def on_input_changed(self, event: Input.Changed):
        if "find_text_input" in event.input.classes:
            text_to_find = event.input.value.lower()
            lines = self.editor.code_area.text.splitlines()  # split into lines

            matches = []  # collect all matches

            for line_index, line in enumerate(lines):
                search_start = 0
                line_lower = line.lower()
                while True:
                    col = line_lower.find(text_to_find, search_start)
                    if col == -1:
                        break
                    matches.append((line_index, col))
                    search_start = col + 1  # move past the last match

            for line_index, col in matches:
                print(f"{matches}")

            # optionally update your UI with first match
            if matches:
                self.matches = matches
                self.match_index = 0
                first_line, first_col = matches[0]
                self.position.update(f"")
                self.editor.code_area.cursor_location = matches[0]
            else:
                self.position.update("Not found")
    async def on_input_submitted(self, event: Input.Submitted):
        try:
            if self.match_index is not None:
                self.match_index += 1
                logging.info(self.matches[self.match_index])
                self.editor.code_area.cursor_location = self.matches[self.match_index]
        except IndexError:
            self.match_index = 0
            logging.info(self.matches[self.match_index])
            self.editor.code_area.cursor_location = self.matches[self.match_index]




