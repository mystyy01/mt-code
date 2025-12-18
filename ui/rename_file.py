from textual.widgets import Static, Input
from ui.overlay import Overlay
from commands.messages import RenameFileProvided
import os


class RenameFilePopup(Overlay):
    def __init__(self, current_path: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.current_path = current_path

    def on_mount(self):
        self.mount(Static("Rename file"))
        self.file_name_input = Input(
            placeholder="new/path/to/file",
            value=self.current_path,
            classes="rename_file"
        )
        self.mount(self.file_name_input)
        self.file_name_input.focus()
        # Select just the filename part for easy editing
        if "/" in self.current_path:
            filename_start = self.current_path.rfind("/") + 1
        else:
            filename_start = 0
        self.file_name_input.cursor_position = len(self.current_path)

    async def on_input_submitted(self, event: Input.Submitted):
        if "rename_file" in event.input.classes:
            new_path = event.input.value
            if new_path and new_path != self.current_path:
                self.post_message(RenameFileProvided(self.current_path, new_path))
            self.remove()
