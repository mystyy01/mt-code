from textual.app import App, ComposeResult
from workspace.workspace import Workspace
import sys
from commands.messages import AppNextTab, TabMessage, FileSelected, FilePathProvided, WorkspaceNewTab, WorkspaceRemoveTab, FocusEditor, SaveAllFiles, SelectAIEvent, APIKeySet, ToggleAIEvent, DiffAccepted
from core.ai_config import get_ai_config
from pathlib import Path
from textual.events import Key, Resize
from textual.binding import Binding
from ui.side_view import SideView
from ui.confirm_exit import ConfirmExit
from ui.folder_view import FolderView
from ui.ai_view import AIView
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
            self.ai_view = AIView()
    ENABLE_COMMAND_PALETTE = False
    CSS_PATH = CSS_PATH_STR
    BINDINGS = [
        # Kill default focus navigation
        Binding("tab", "custom_tab", show=False, priority=True),

        # Shift+tab for dedent
        Binding("shift+tab", "custom_shift_tab", show=False, priority=True),
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
        self.mount(self.ai_view)
        # Connect AI view to workspace for editor access
        self.ai_view.set_workspace(self.workspace)
        # Set initial AI view visibility based on config
        ai_config = get_ai_config()
        if not ai_config.is_ai_enabled():
            self.ai_view.styles.display = "none"
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

    def action_custom_shift_tab(self):
        self.workspace.post_message(TabMessage(shift=True))
    def on_key(self, event: events.Key):
        # Try custom keybindings first
        if hasattr(self, 'workspace') and self.workspace.handle_keybinding(event.key):
            event.prevent_default()
            event.stop()
            return

        # Fallback to hardcoded bindings (for backwards compatibility)
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
        if event.key=="ctrl+l":
            self._handle_ai_comment_edit()
        if event.key=="f2":
            self.workspace.cmd_rename_file()
    def on_resize(self, event: Resize):
        logging.info("resized terminal to " + str(event.size.width))
        width = int(event.size.width * 0.3)

        # clamp between 25 and 38
        width = max(25, min(width, 38))

        self.folder_view.styles.width = width
        self.ai_view.styles.width = width
    # def on_tab_message(self, event: TabMessage):
    #     if event.is_forwarded:
    #         self.screen.focus_next()
    def on_save_all_files(self, event: SaveAllFiles):
        self.workspace.save_all_files()
        quit()

    def on_select_ai_event(self, event: SelectAIEvent):
        """Handle AI provider selection."""
        if hasattr(self, 'ai_view') and self.ai_view:
            self.ai_view.switch_provider(event.provider)

    def on_api_key_set(self, event: APIKeySet):
        """Handle API key being set."""
        if hasattr(self, 'ai_view') and self.ai_view:
            # Reinitialize the AI chat to pick up the new key
            self.ai_view.reinit_provider()

    def on_toggle_ai_event(self, event: ToggleAIEvent):
        """Handle AI features being toggled."""
        logging.info(f"=== on_toggle_ai_event received, enabled={event.enabled} ===")
        if hasattr(self, 'ai_view') and self.ai_view:
            new_display = "block" if event.enabled else "none"
            logging.info(f"Setting ai_view.styles.display to '{new_display}'")
            self.ai_view.styles.display = new_display
            logging.info(f"ai_view.styles.display is now: {self.ai_view.styles.display}")
        else:
            logging.info("ai_view not found!")

    def on_diff_accepted(self, event: DiffAccepted):
        """Handle accepted AI code changes."""
        logging.info("DiffAccepted event received")
        try:
            editor = self.workspace.tab_manager.get_active_editor()
            if editor and hasattr(editor, 'code_area') and editor.code_area:
                editor.code_area.load_text_silent(event.new_content)
                logging.info("Applied AI changes to editor")
        except Exception as e:
            logging.error(f"Error applying AI changes: {e}")

    def _handle_ai_comment_edit(self):
        """Handle Ctrl+L: extract comment from current line and send to AI for editing."""
        logging.info("Ctrl+L pressed - checking for comment")

        # Comment prefixes by language
        comment_prefixes = {
            "python": ["#"],
            "javascript": ["//"],
            "typescript": ["//"],
            "rust": ["//"],
            "go": ["//"],
            "c": ["//"],
            "cpp": ["//"],
            "java": ["//"],
            "lua": ["--"],
            "sql": ["--"],
            "bash": ["#"],
            "shell": ["#"],
            "ruby": ["#"],
            "perl": ["#"],
        }
        default_prefixes = ["#", "//", "--"]

        try:
            editor = self.workspace.tab_manager.get_active_editor()
            if not editor or not hasattr(editor, 'code_area') or not editor.code_area:
                logging.info("No active editor")
                return

            code_area = editor.code_area
            # Get current cursor row
            cursor_row, _ = code_area.cursor_location
            current_line = code_area.document.get_line(cursor_row)

            # Get language-specific prefixes
            language = getattr(code_area, 'language', None) or ""
            prefixes = comment_prefixes.get(language.lower(), default_prefixes)

            # Check if line starts with a comment prefix
            stripped = current_line.strip()
            comment_text = None

            for prefix in prefixes:
                if stripped.startswith(prefix):
                    # Extract comment text after prefix
                    comment_text = stripped[len(prefix):].strip()
                    break

            if comment_text:
                logging.info(f"Found comment: {comment_text}")
                # Send to AI for editing
                if hasattr(self, 'ai_view') and self.ai_view:
                    self.ai_view.ask_for_edit(comment_text)
            else:
                logging.info("Current line is not a comment")

        except Exception as e:
            logging.error(f"Error in _handle_ai_comment_edit: {e}")

if __name__ == "__main__":
    TextualApp().run()