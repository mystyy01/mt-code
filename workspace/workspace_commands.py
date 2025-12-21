"""Command implementations for Workspace.

This module contains all command implementations that can be triggered
from the command palette or keyboard shortcuts.
"""

import logging
from tree_sitter_language_pack import get_language
from core.paths import LOG_FILE_STR
from core.languages import get_run_command

from commands.messages import (
    WorkspaceNewTab, EditorUndo, EditorRedo, WorkspaceRemoveTab, ToggleAIEvent
)
from core.ai_config import get_ai_config
from ui.find_and_replace import FindAndReplace
from ui.select_syntax import SelectSyntax
from ui.select_ai import SelectAI
from ui.api_key_input import APIKeyInput
from ui.success_overlay import SuccessOverlay
from ui.line_input import LineInput
from ui.commit_message import GitCommitMessage
from ui.rename_file import RenameFilePopup
from ui.plugins_overlay import PluginsOverlay
from ui.keybindings_overlay import KeybindingsOverlay
from git_utils import git_actions

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class WorkspaceCommandsMixin:
    """Mixin providing command implementations for Workspace."""

    def _init_command_map(self):
        """Initialize the command map. Call from __init__."""
        self.command_map = {
            "open_file": self.cmd_open_file,
            "create_file": self.cmd_create_file,
            "quit_app": self.cmd_quit_app,
            "focus_terminal": self.cmd_focus_terminal,
            "focus_editor": self.cmd_focus_editor,
            "save_file": self.cmd_save_file,
            "save_file_as": self.cmd_save_file_as,
            "rename_file": self.cmd_rename_file,
            "close_tab": self.cmd_close_tab,
            "next_tab": self.cmd_next_tab,
            "previous_tab": self.cmd_previous_tab,
            "toggle_sidebar": self.cmd_toggle_sidebar,
            "undo": self.cmd_undo,
            "redo": self.cmd_redo,
            "find": self.cmd_find,
            "go_to_line": self.cmd_go_to_line,
            "select_syntax": self.cmd_select_syntax,
            "run_file": self.cmd_run_file,
            "git_add_commit_push": self.cmd_git_add_commit_push,
            "git_add": self.cmd_git_add,
            "git_commit": self.cmd_git_commit,
            "git_push": self.cmd_git_push,
            "edit_plugins": self.cmd_edit_plugins,
            "edit_keybindings": self.cmd_edit_keybindings,
            "command_palette": self.cmd_command_palette,
            "select_ai": self.cmd_select_ai,
            "set_api_key": self.cmd_set_api_key,
            "ask_ai": self.cmd_ask_ai,
            "toggle_ai": self.cmd_toggle_ai
        }

    def dispatch_command(self, command: str, **kwargs):
        """Dispatch a command by name."""
        func = self.command_map.get(command)
        if func:
            func(**kwargs)
        else:
            print(f"Unknown command: {command}")

    # === File Commands ===

    def cmd_open_file(self, **kwargs):
        """Open file dialog."""
        print("Opening file…")
        self.post_message(WorkspaceNewTab())

    def cmd_create_file(self, **kwargs):
        """Create new file."""
        print("Creating file…")
        self.post_message(WorkspaceNewTab())

    def cmd_save_file(self, **kwargs):
        """Save current file."""
        print("Saving file…")
        self.tab_manager.get_active_editor().code_area.save_file()

    def cmd_save_file_as(self, **kwargs):
        """Save current file with new name."""
        print("Saving file as…")
        self.tab_manager.get_active_editor().code_area.save_as()

    def cmd_rename_file(self, **kwargs):
        """Rename current file."""
        editor = self.tab_manager.get_active_editor()
        if not editor or not editor.file_path:
            logging.info("No file to rename")
            return
        self.screen.mount(RenameFilePopup(current_path=editor.file_path))

    # === Tab Commands ===

    def cmd_close_tab(self, **kwargs):
        """Close current tab."""
        self.tab_manager.post_message(WorkspaceRemoveTab())

    def cmd_next_tab(self, **kwargs):
        """Switch to next tab."""
        self.tab_manager.next_tab(self.tab_manager.active_tab)

    def cmd_previous_tab(self, **kwargs):
        """Switch to previous tab."""
        print("Switching to previous tab…")
        self.tab_manager.previous_tab(self.tab_manager.active_tab)

    # === Focus Commands ===

    def cmd_focus_terminal(self, **kwargs):
        """Focus the terminal."""
        print("Focusing terminal…")
        self.terminal.focus()

    def cmd_focus_editor(self, **kwargs):
        """Focus the editor."""
        print("Focusing editor…")
        self.tab_manager.get_active_editor().code_area.focus()

    # === Edit Commands ===

    def cmd_undo(self, **kwargs):
        """Undo last action."""
        print("Undo…")
        self.tab_manager.post_message(EditorUndo())

    def cmd_redo(self, **kwargs):
        """Redo last undone action."""
        print("Redo…")
        self.tab_manager.post_message(EditorRedo())

    def cmd_find(self, **kwargs):
        """Open find and replace."""
        print("Find…")
        self.find_and_replace(self.tab_manager.get_active_editor())

    def cmd_go_to_line(self, **kwargs):
        """Go to specific line number."""
        num_lines = len(self.tab_manager.get_active_editor().code_area.document.lines)
        self.screen.mount(LineInput(num_lines))

    def cmd_select_syntax(self, **kwargs):
        """Open syntax selection dialog."""
        logging.info("Selecting syntax")
        syntaxes = list(self.tab_manager.get_active_editor().code_area.available_languages)
        logging.info(len(syntaxes))
        available = ["none"]  # Add none option to disable syntax highlighting
        for name in syntaxes:
            try:
                get_language(name)
                available.append(name)
            except Exception:
                pass

        self.screen.mount(SelectSyntax(available))

    def cmd_run_file(self, **kwargs):
        """Run the current file in the terminal."""
        editor = self.tab_manager.get_active_editor()
        if not editor or not editor.file_path:
            logging.info("No file to run")
            return

        # Save file first
        editor.code_area.save_file()

        # Get run command for this file type
        run_cmd = get_run_command(editor.file_path)
        if not run_cmd:
            logging.info(f"No run command for: {editor.file_path}")
            return

        # Replace {file} placeholder with actual path
        cmd = run_cmd.format(file=editor.file_path)
        logging.info(f"Running: {cmd}")

        # Send command to terminal
        self.terminal.run_command(cmd)
        self.terminal.focus()

    # === UI Commands ===

    def cmd_toggle_sidebar(self, **kwargs):
        """Toggle sidebar visibility."""
        if self.folder_view:
            current = self.folder_view.styles.display
            self.folder_view.styles.display = "none" if current == "block" else "block"

    def cmd_quit_app(self, **kwargs):
        """Quit the application."""
        print("Quitting app…")
        quit()

    # === Git Commands ===

    def cmd_git_add_commit_push(self, **kwargs):
        """Stage, commit, and push all changes."""
        self.show_commit_input(id="all_3")

    def cmd_git_add(self, **kwargs):
        """Stage all changes."""
        res = git_actions.git_add(self.repo)
        if res:
            self.screen.mount(SuccessOverlay("Successfully staged all files"))

    def cmd_git_commit(self, **kwargs):
        """Open commit message dialog."""
        self.show_commit_input(id="commit")

    def cmd_git_push(self, **kwargs):
        """Push to remote."""
        res = git_actions.git_push_origin_main(self.repo)
        if res:
            self.screen.mount(SuccessOverlay("Successfully pushed commit to branch main"))

    def show_commit_input(self, id="commit"):
        """Show the commit message input dialog."""
        self.screen.mount(GitCommitMessage(message_id=id))

    # === Plugin Commands ===

    def cmd_edit_plugins(self, **kwargs):
        """Open the plugins management overlay."""
        self.screen.mount(PluginsOverlay(plugin_manager=self.plugin_manager))

    def cmd_edit_keybindings(self, **kwargs):
        """Open the keybindings editor overlay."""
        self.screen.mount(KeybindingsOverlay())

    def cmd_select_ai(self, **kwargs):
        """Open AI provider selection dialog."""
        logging.info("Selecting AI provider")
        # Get AI view from app
        if hasattr(self.app, 'ai_view') and self.app.ai_view.ai_chat:
            ai_chat = self.app.ai_view.ai_chat
            providers = ai_chat.get_available_providers()
            current = ai_chat.get_current_provider_name()
            self.screen.mount(SelectAI(providers, current))

    def cmd_set_api_key(self, **kwargs):
        """Open API key input dialog."""
        logging.info("Opening API key input")
        self.screen.mount(APIKeyInput())

    def cmd_ask_ai(self, **kwargs):
        """Send current selection to AI."""
        logging.info("Sending selection to AI")
        if hasattr(self.app, 'ai_view') and self.app.ai_view:
            # Get selected text from editor
            editor = self.tab_manager.get_active_editor()
            if editor and hasattr(editor, 'code_area') and editor.code_area:
                selected = getattr(editor.code_area, 'selected_text', '')
                if selected:
                    self.app.ai_view.ask_about_code(selected)
                else:
                    self.app.ai_view.ask_about_code(editor.code_area.text, is_full_file=True)

    def cmd_toggle_ai(self, **kwargs):
        """Toggle AI features on/off."""
        logging.info("=== cmd_toggle_ai called ===")
        ai_config = get_ai_config()
        current_state = ai_config.is_ai_enabled()
        logging.info(f"Current AI enabled state: {current_state}")
        new_state = not current_state
        logging.info(f"New AI enabled state: {new_state}")
        ai_config.set_ai_enabled(new_state)
        # Directly toggle the AI view visibility
        if hasattr(self.app, 'ai_view') and self.app.ai_view:
            new_display = "block" if new_state else "none"
            logging.info(f"Setting ai_view display to: {new_display}")
            self.app.ai_view.styles.display = new_display
            logging.info(f"ai_view display is now: {self.app.ai_view.styles.display}")

    def cmd_command_palette(self, **kwargs):
        """Open the command palette."""
        self.open_command_palette()

    # === Helper Methods ===

    def find_and_replace(self, editor):
        """Open find and replace for the given editor."""
        self.mount(FindAndReplace(editor=editor))

    def get_command_palette_commands(self):
        """Return the command palette command definitions."""
        return {
            "Run File": "run_file",
            "Open File": "open_file",
            "Create File": "create_file",
            "Quit": "quit_app",
            "Select syntax": "select_syntax",
            "Git add commit push": "git_add_commit_push",
            "Git add": "git_add",
            "Git commit": "git_commit",
            "Git push": "git_push",
            "Focus Terminal": "focus_terminal",
            "Focus Editor": "focus_editor",
            "Save": "save_file",
            "Save As": "save_file_as",
            "Rename File": "rename_file",
            "Close Current Tab": "close_tab",
            "Next Tab": "next_tab",
            "Previous Tab": "previous_tab",
            "Toggle Sidebar": "toggle_sidebar",
            "Undo": "undo",
            "Redo": "redo",
            "Find": "find",
            "Go To Line": "go_to_line",
            "Edit Plugins": "edit_plugins",
            "Edit Keybindings": "edit_keybindings",
            "Select AI Provider": "select_ai",
            "Set API Key": "set_api_key",
            "Ask AI About Selection": "ask_ai",
            "Toggle AI Features": "toggle_ai",
        }
