from textual.app import App
from textual.widgets import Static, Button, TextArea, Input
from textual.containers import Vertical, Horizontal, Container
from textual.events import Key
from textual.document._document import Location
from textual.binding import Binding
from typing import Tuple
from textual.message import Message
import logging
from core.buffer import Buffer
from core.file_management import delete_file, read_file, save_file
import asyncio
from ui.save_as import SaveAsPopup
from ui.code_editor import CodeEditor
from commands.messages import EditorSavedAs, FilePathProvided, UseFile, EditorOpenFile, SaveAsProvided, EditorSaveFile, EditorDirtyFile
from ui.open_file import OpenFilePopup
from core.paths import LOG_FILE_STR
logging.basicConfig(filename=LOG_FILE_STR, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
import random
import string
import os
class EditorView(Container):
    def __init__(self, file_path="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_path = file_path
        self.tab_id: str | None = None  # will be set by TabManager

    def random_hash(self):
        first = random.choice(string.ascii_lowercase)
        rest = ''.join(
            random.choices(string.ascii_lowercase + string.digits, k=5)
        )
        return first + rest
    def hide(self):
        self.styles.display = "none"
        # Close completions overlay when hiding the editor
        if hasattr(self, 'code_area') and self.code_area:
            self.code_area._close_completions_overlay()
    def show(self):
        self.styles.display = "block"
    
    def on_mount(self):
        self.newid = self.random_hash()
        # If a file_path was provided, ensure the file exists on disk.
        # If no file_path was provided (empty string), treat this editor as
        # an in-memory buffer and do not attempt to create a filesystem file.
        if self.file_path:
            if not os.path.exists(self.file_path):
                # Create the file path (and parent dir) if necessary
                parent = os.path.dirname(self.file_path)
                if parent and not os.path.exists(parent):
                    os.makedirs(parent, exist_ok=True)
                with open(self.file_path, "w") as f:
                    f.write("")
        self.code_area = CodeEditor.code_editor(tab_id=self.tab_id, file=self.file_path, classes="editor", id=self.newid)
        self.code_area.indent_type = "spaces"
        self.code_area.indent_width = 4
        self.code_area.show_line_numbers = True
        self.last_text = self.code_area.text
        self.mount(self.code_area)
        
    async def on_text_area_changed(self, event: TextArea.Changed):
        # import here or top-level
        from commands.messages import EditorDirtyFile
        # include tab id when posting
        self.post_message(EditorDirtyFile(self.tab_id, self.file_path))

    def on_editor_saved_as(self, event: EditorSavedAs):
        logging.info(event.contents)
        self.contents = event.contents
        self.mount(SaveAsPopup())
    def on_editor_open_file(self, event: EditorOpenFile):
        self.mount(OpenFilePopup())
    def on_file_path_provided(self, event: FilePathProvided):
        logging.info("file path provided!")
        file_path = event.file_path
        self.file_path = file_path
        if os.path.exists(file_path):
            contents = read_file(file_path)
        else:
            contents = self.contents
        save_file(file_path, contents)
        # For global FilePathProvided events (e.g., OpenFilePopup from Workspace),
        # we create a new tab. For SaveAs (editor-local) flows, SaveAsPopup will
        # post a SaveAsProvided message which is handled separately by
        # `on_save_as_provided`.
        # Do not post UseFile here to avoid duplicate tab creation.
        self.post_message(EditorSaveFile(self.tab_id))
        return

    def on_save_as_provided(self, event: "SaveAsProvided"):
        # Handle SaveAs submissions originating from this editor's SaveAsPopup.
        # Save the contents to the chosen path and instruct the TabManager to
        # replace the current active tab with an editor bound to the file.
        logging.info("save-as provided: %s", event.file_path)
        file_path = event.file_path
        self.file_path = file_path
        if os.path.exists(file_path):
            contents = read_file(file_path)
        else:
            contents = self.contents
        save_file(file_path, contents)
        # notify higher-level manager to use this file for the current tab
        self.post_message(UseFile(file_path))
    async def on_key(self, event: Key):
        pass
    def undo(self):
        self.code_area.undo()
    def redo(self):
        self.code_area.redo()



