"""Workspace container - main workspace management.

This module provides the Workspace class which manages:
- Tab management and file editing
- Terminal integration
- Command palette
- Git operations (via WorkspaceCommandsMixin)
"""

from textual.containers import Container
import logging
from pathlib import Path
import os

from core.paths import LOG_FILE_STR
from commands.messages import (
    FilePathProvided, WorkspaceNewTab, WorkspaceNextTab, AppNextTab,
    CommandPaletteCommand, OpenCommandPalette, FocusEditor,
    SelectSyntaxEvent, GitCommitMessageSubmitted, LineInputSubmitted, TabMessage,
    RenameFileProvided, GotoFileLocation
)
from ui.open_file import OpenFilePopup
from ui.tab_manager import TabManager
from ui.editor_view import EditorView
from ui.command_palette import CommandPalette
from ui.terminal import Terminal, TerminalContainer
from ui.success_overlay import SuccessOverlay
from ui.folder_view import FolderView
from ui.run_button import RunButtonPressed
from git_utils import get_repo, git_actions
from workspace.workspace_commands import WorkspaceCommandsMixin
from core.plugin_manager import PluginManager
from core.session import Session
from core.keybindings import get_keybindings_manager

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class Workspace(WorkspaceCommandsMixin, Container):
    """Main workspace container managing tabs, terminal, and commands."""

    def __init__(self, folder_view: FolderView | None = None, file_path_passed="", project_root=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = get_repo.get_repo(os.getcwd())
        self.file_path_passed = file_path_passed
        self.folder_view = folder_view
        self.project_root = project_root or os.getcwd()
        self.session = Session(self.project_root)
        self.plugin_manager = PluginManager(app=self)
        self._init_command_map()
        self._init_keybindings()

    def has_got_dirty_files(self):
        """Check if any open files have unsaved changes."""
        return self.tab_manager.has_dirty_files()

    def _init_keybindings(self):
        """Initialize the keybindings manager."""
        self.keybindings = get_keybindings_manager()
        self.keybindings.set_dispatcher(self.dispatch_command)
        self.keybindings.set_bash_executor(self._execute_bash_keybinding)

    def _execute_bash_keybinding(self, command: str):
        """Execute a bash command from a keybinding."""
        if hasattr(self, 'terminal') and self.terminal:
            # Replace placeholders
            editor = self.tab_manager.get_active_editor()
            if editor and editor.file_path:
                command = command.replace("%file%", editor.file_path)
                command = command.replace("%dir%", str(Path(editor.file_path).parent))
            self.terminal.run_command(command)

    def handle_keybinding(self, key: str) -> bool:
        """Handle a key press via keybindings. Returns True if handled."""
        return self.keybindings.execute_binding(key)

    def change_workspace_dir(self, new_path: str):
        """Change the workspace directory.

        Updates the project root, folder view, session, and git repo.

        Args:
            new_path: The new directory path
        """
        abs_path = str(Path(new_path).resolve())
        if not os.path.isdir(abs_path):
            logging.warning(f"Cannot change workspace dir to non-directory: {abs_path}")
            return

        self.project_root = abs_path

        # Update folder view
        if self.folder_view:
            self.folder_view.path = abs_path

        # Update session to use new directory
        self.session = Session(abs_path)

        # Update git repo for workspace and tab manager
        self.repo = get_repo.get_repo(abs_path)
        if hasattr(self, 'tab_manager') and self.tab_manager:
            self.tab_manager.repo = self.repo
            self.tab_manager.session = self.session

        logging.info(f"Changed workspace directory to: {abs_path}")

    def on_mount(self):
        """Initialize workspace components on mount."""
        # Try to restore tabs from session
        session_tabs = self.session.get_tab_paths()
        active_tab_path = self.session.get_active_tab_path()

        # Pre-filter session tabs to only include existing files
        valid_session_paths = [p for p in session_tabs if os.path.exists(p)]

        # Log any removed files
        for p in session_tabs:
            if p not in valid_session_paths:
                logging.info(f"Session file no longer exists, skipping: {p}")

        # Build tabs dict and determine active tab
        tabs = {}
        active_tab_id = None

        if self.file_path_passed != "":
            # A specific file was passed as argument - open it
            tabs["0"] = EditorView(file_path=self.file_path_passed, classes="editor-view")
            active_tab_id = "0"
        elif valid_session_paths:
            # Restore tabs from session
            for i, file_path in enumerate(valid_session_paths):
                tab_id = str(i)
                tabs[tab_id] = EditorView(file_path=file_path, classes="editor-view")
                if file_path == active_tab_path:
                    active_tab_id = tab_id
            # Clean up session if some files were removed
            if len(valid_session_paths) < len(session_tabs):
                self.session.save_tab_state(valid_session_paths, active_tab_path if active_tab_path in valid_session_paths else None)
        else:
            # No session, create empty tab
            tabs["0"] = EditorView(file_path="", classes="editor-view")
            active_tab_id = "0"

        self.tab_manager = TabManager(
            tabs=tabs,
            repo=self.repo,
            session=self.session,
            active_tab_id=active_tab_id
        )
        self.mount(self.tab_manager)

        self.terminal = Terminal("/bin/zsh", "> ")
        self.terminal_container = TerminalContainer(terminal=self.terminal)
        self.mount(self.terminal_container)
        self.focus()

        # Load plugins
        self.plugin_manager.load_all_plugins()

    def on_run_button_pressed(self, event: RunButtonPressed):
        """Handle run button press."""
        self.cmd_run_file()

    # === Tab Management ===

    def new_tab(self, path, tab_id):
        """Create a new tab with the given file path."""
        logging.info("path: " + path)
        logging.info("workspace thinks this is tab id: " + str(tab_id))
        self.tab_manager.add_tab(tab_id, EditorView(file_path=path))

    def on_workspace_new_tab(self, event: WorkspaceNewTab):
        """Handle request to open a new tab."""
        self.open_file_popup = OpenFilePopup(root_dir=self.project_root)
        self.screen.mount(self.open_file_popup)

    def on_app_next_tab(self, event: AppNextTab):
        """Handle request to switch to next tab."""
        logging.info("message recieved in Workspace")
        self.tab_manager.post_message(WorkspaceNextTab())

    def on_file_path_provided(self, event: FilePathProvided):
        """Handle file path provided from open dialog."""
        # Resolve to absolute path for LSP URI compatibility
        abs_path = str(Path(event.file_path).resolve())
        # If directory selected, change workspace directory
        if os.path.isdir(abs_path):
            self.change_workspace_dir(abs_path)
            return

        # Check if file is already open in an existing tab
        existing_tab_id = self.tab_manager.find_tab_by_path(abs_path)
        if existing_tab_id is not None:
            # Switch to existing tab instead of opening a new one
            self.tab_manager.switch_tab(existing_tab_id)
            logging.info(f"Switched to existing tab for: {abs_path}")
            return

        if self.tab_manager.tabs:
            max_id = max(int(tab_id) for tab_id in self.tab_manager.tabs.keys())
        else:
            max_id = -1
        next_id = str(max_id + 1)
        prev_file_path = self.tab_manager.get_active_editor().file_path
        prev_file_editor = self.tab_manager.get_active_editor()
        self.new_tab(abs_path, next_id)
        # Replace empty unsaved files with the new file opened
        if prev_file_path == "" and prev_file_editor.code_area.text.strip() == "":
            self.tab_manager.remove_tab(prev_file_editor.tab_id)
        logging.info(self.tab_manager.tabs)

    def on_rename_file_provided(self, event: RenameFileProvided):
        """Handle file rename request."""
        old_path = str(Path(event.old_path).resolve())
        new_path = str(Path(event.new_path).resolve())

        # Skip if paths are the same
        if old_path == new_path:
            return

        # Rename the file on disk
        try:
            # Ensure parent directory exists for new path
            parent = os.path.dirname(new_path)
            if parent and not os.path.exists(parent):
                os.makedirs(parent, exist_ok=True)
            os.rename(old_path, new_path)
        except OSError as e:
            logging.error(f"Failed to rename file: {e}")
            return

        # Update the active editor with the new path
        editor = self.tab_manager.get_active_editor()
        if editor and editor.file_path == old_path:
            editor.file_path = new_path
            editor.code_area.file_path = new_path

            # Update the tab label
            from ui.tab import Tab
            tab_widget = self.tab_manager.tab_bar.query_one(f"#t{editor.tab_id}")
            if isinstance(tab_widget, Tab):
                tab_widget.label = self.tab_manager.make_relative(new_path)

        logging.info(f"Renamed file from {old_path} to {new_path}")

    def on_goto_file_location(self, event: GotoFileLocation):
        """Handle request to open file at specific location (for go-to-definition)."""
        logging.info(f"on_goto_file_location received: file={event.file_path}, line={event.line}, col={event.column}")
        abs_path = str(Path(event.file_path).resolve())
        logging.info(f"Resolved absolute path: {abs_path}")

        # Check if file is already open
        existing_tab_id = self.tab_manager.find_tab_by_path(abs_path)
        logging.info(f"Existing tab id for path: {existing_tab_id}")

        if existing_tab_id is not None:
            # Switch to existing tab
            logging.info(f"Switching to existing tab: {existing_tab_id}")
            self.tab_manager.switch_tab(existing_tab_id)
        else:
            # Open new tab
            if self.tab_manager.tabs:
                max_id = max(int(tab_id) for tab_id in self.tab_manager.tabs.keys())
            else:
                max_id = -1
            next_id = str(max_id + 1)
            logging.info(f"Opening new tab with id: {next_id}")
            self.new_tab(abs_path, next_id)

        # Navigate to position after editor is ready
        def navigate():
            logging.info(f"navigate() callback executing for line={event.line}, col={event.column}")
            editor = self.tab_manager.get_active_editor()
            if editor and hasattr(editor, 'code_area') and editor.code_area:
                logging.info(f"Moving cursor to ({event.line}, {event.column})")
                editor.code_area.move_cursor((event.line, event.column))
                editor.code_area.scroll_cursor_visible()
                editor.code_area.focus()
                logging.info("Navigation complete")
            else:
                logging.warning("Could not get editor or code_area for navigation")

        # Use call_later to ensure editor is mounted
        logging.info("Scheduling navigate() with call_later")
        self.call_later(navigate)

    # === Command Palette ===

    def on_command_palette_command(self, event: CommandPaletteCommand):
        """Handle command from command palette."""
        self.dispatch_command(event.command, **event.kwargs)

    def open_command_palette(self):
        """Open the command palette."""
        commands = self.get_command_palette_commands()
        self.command_palette = CommandPalette(commands)
        self.screen.mount(self.command_palette)

    def on_open_command_palette(self, event: OpenCommandPalette):
        """Handle request to open command palette."""
        self.open_command_palette()

    # === Focus Management ===

    def on_focus_editor(self, event: FocusEditor):
        """Handle request to focus the editor."""
        logging.info("focusing editor")
        editor = self.tab_manager.get_active_editor()
        logging.info(editor)
        editor.code_area.focus()

    # === Event Handlers ===

    def on_select_syntax_event(self, event: SelectSyntaxEvent):
        """Handle syntax selection."""
        syntax = event.syntax
        logging.info("syntax selected: " + syntax)
        if event.syntax != "none":
            self.tab_manager.get_active_editor().code_area.language = syntax
        else:
            self.tab_manager.get_active_editor().code_area.language = None

    def on_git_commit_message_submitted(self, message: GitCommitMessageSubmitted):
        """Handle git commit message submission."""
        message_id = message.message_id
        commit_message = message.commit_message
        if message_id == "all_3":
            res = git_actions.git_add_commit_push(self.repo, commit_message)
            if res:
                self.screen.mount(SuccessOverlay("Successfully added, commited and pushed all changes."))
        elif message_id == "commit":
            res = git_actions.git_commit(self.repo, commit_message)
            if res:
                self.screen.mount(SuccessOverlay("Successfully committed changes"))
        message.input_widget.remove()

    def on_line_input_submitted(self, event: LineInputSubmitted):
        """Handle line number input submission."""
        num_lines = len(self.tab_manager.get_active_editor().code_area.document.lines)
        if int(event.line) <= num_lines:
            self.tab_manager.get_active_editor().code_area.move_cursor((int(event.line) - 1, 0))
        else:
            self.line_input = LineInput(num_lines)
            self.screen.mount(self.line_input)

    async def on_tab_message(self, event: TabMessage):
        """Handle custom tab message for auto-completion."""
        logging.info("recieved custom tab")
        try:
            if self.open_file_popup.is_mounted:
                self.open_file_popup.action_auto_complete()
        except AttributeError:
            pass
        try:
            if self.command_palette.is_mounted:
                self.command_palette.action_auto_complete()
        except AttributeError:
            pass
        try:
            if self.tab_manager.get_active_editor().code_area.has_focus:
                self.tab_manager.get_active_editor().code_area.post_message(TabMessage(shift=event.shift))
            else:
                pass
        except Exception:
            pass

    def save_all_files(self):
        """Save all open files."""
        for tab in self.tab_manager.tabs.keys():
            editor = self.tab_manager.tabs[tab]
            if editor.file_path and hasattr(editor, 'code_area') and editor.code_area:
                editor.code_area.save_file()
