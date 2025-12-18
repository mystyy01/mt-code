from textual.app import App, ComposeResult
from workspace.workspace import Workspace
import sys
from commands.messages import AppNextTab, TabMessage, FileSelected, FilePathProvided, WorkspaceNewTab, WorkspaceRemoveTab, FocusEditor, SaveAllFiles
from pathlib import Path
from textual.events import Key, Resize
from textual.binding import Binding
from ui.side_view import SideView
from ui.confirm_exit import ConfirmExit
from ui.folder_view import FolderView
import logging
import os
from textual import events
from core.paths import LOG_FILE_STR, CSS_PATH_STR
logging.basicConfig(filename=LOG_FILE_STR, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

# Run with: python app.py

# get the argument
if len(sys.argv) >= 2:
    file_arg = sys.argv[1]
    path_passed = Path(file_arg).resolve()
    if path_passed.is_dir():
        file_path_passed = ""
        folder_path_passed = str(path_passed)
    else:
        folder_path_passed = ""
        file_path_passed = str(path_passed)
else:
    folder_path_passed = ""
    file_path_passed = ""

class TextualApp(App):
    def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            if file_path_passed:
                self.cwd = Path(file_path_passed).parent # set to parent dir of the file passed
            elif folder_path_passed:
                self.cwd = Path(folder_path_passed) # set to the working dir of where the command was ran
            else:
                self.cwd = os.getcwd()
            self.folder_view = FolderView(path=self.cwd)
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = CSS_PATH_STR
    BINDINGS = [
        # Kill default focus navigation
        Binding("tab", "custom_tab", show=False, priority=True),

        # Cycle tabs
        Binding("shift+tab", "switch_tab", show=False, priority=True),
        Binding("ctrl+q", "confirm_quit", show=False, priority=True)
    ]
    def action_confirm_quit(self):
        if self.workspace.has_got_dirty_files():
            self.mount(self.confirm_exit)
        else:
            quit()
    def action_noop(self):
        pass
    def on_mount(self):
        self.confirm_exit = ConfirmExit()
        self.mount(self.folder_view)
        self.workspace = Workspace(
            file_path_passed=file_path_passed,
            folder_view=self.folder_view,
            project_root=self.cwd
        )
        self.mount(self.workspace)
    def on_file_selected(self, event: FileSelected):
        self.workspace.post_message(FilePathProvided(str(event.path)))
    def action_switch_tab(self):
        logging.info("switching tabs")
        self.workspace.post_message(AppNextTab())
    def action_custom_tab(self):
        self.workspace.post_message(TabMessage())
        if self.confirm_exit.is_mounted:
            self.confirm_exit.post_message(TabMessage())
            return
    def on_key(self, event: events.Key):
        if event.key=="ctrl+n" or event.key=="ctrl+o":
            self.workspace.post_message(WorkspaceNewTab())
        if event.key=="ctrl+w":
            self.workspace.tab_manager.post_message(WorkspaceRemoveTab())
        if event.key=="ctrl+p":
            self.workspace.open_command_palette()
        if event.key=="ctrl+f":
            self.workspace.find_and_replace(self.workspace.tab_manager.get_active_editor())
        if event.key=="ctrl+t":
            logging.info("focusing terminal")
            self.workspace.terminal.focus()
        if event.key=="ctrl+r":
            logging.info("focusing file explorer")
            self.workspace.folder_view.focus()
        if event.key=="ctrl+e":
            logging.info("focusing editor")
            self.workspace.post_message(FocusEditor())
        if event.key=="ctrl+k":
            # put whatever popup im testing here
            pass
        if event.key=="f2":
            self.workspace.cmd_rename_file()
    def on_resize(self, event: Resize):
        logging.info("resized terminal to " + str(event.size.width))
        width = int(event.size.width * 0.3)

        # clamp between 33 and 41 (values i tested)
        width = max(25, min(width, 38))

        self.folder_view.styles.width = width
    # def on_tab_message(self, event: TabMessage):
    #     if event.is_forwarded:
    #         self.screen.focus_next()
    def on_save_all_files(self, event: SaveAllFiles):
        self.workspace.save_all_files()
        quit()
if __name__ == "__main__":
    TextualApp().run()