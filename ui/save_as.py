from textual import events
from textual.widgets import TextArea, Static, Input
from core.file_management import read_file, delete_file, save_file
from textual.containers import Container
from ui.overlay import Overlay
from textual.message import Message
from typing import Literal
from textual.content import Content
from rich.console import RenderableType
import logging 
from commands.messages import FilePathProvided
logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")




class SaveAsPopup(Overlay):
    def on_mount(self):
        self.mount(Static("Save as"))
        self.file_name_input = Input(placeholder="relative/path/to/save", classes="save_as")
        self.mount(self.file_name_input)
        self.file_name_input.focus()
    async def on_input_submitted(self, event: Input.Submitted):
        if "save_as" in event.input.classes:
            self.file_path = event.input.value
            from commands.messages import SaveAsProvided
            self.post_message(SaveAsProvided(self.file_path))
            self.remove()