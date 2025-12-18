from textual.app import App
from textual.widgets import Static, Button, TextArea, Input
from textual.containers import Vertical, Horizontal, Container, Grid
from textual.events import Key
from textual.document._document import Location
from textual.binding import Binding
from typing import Tuple
from textual import events
from textual.message import Message
import logging
from core.buffer import Buffer
from core.file_management import delete_file, read_file, save_file
import asyncio
from ui.save_as import SaveAsPopup
from ui.overlay import Overlay
from ui.code_editor import CodeEditor
from commands.messages import EditorSavedAs, FilePathProvided, UseFile, EditorOpenFile, WorkspaceNewTab, WorkspaceRemoveTab, WorkspaceNextTab, AppNextTab, CommandPaletteCommand, OpenCommandPalette, EditorUndo, EditorRedo, FocusEditor, SelectSyntaxEvent, GitCommitMessageSubmitted, LineInputSubmitted, TabMessage, FileSelected
from ui.open_file import OpenFilePopup
from ui.tab_manager import TabManager
from ui.code_editor import CodeEditor
from ui.editor_view import EditorView
from ui.command_palette import CommandPalette
from pathlib import Path
from ui.find_and_replace import FindAndReplace
from ui.select_syntax import SelectSyntax
from ui.terminal import Terminal, TerminalContainer
from ui.commit_message import GitCommitMessage
import sys
from ui.success_overlay import SuccessOverlay
from ui.line_input import LineInput
from ui.folder_view import FolderView
from ui.side_view import SideView
from git_utils import get_repo, git_file_status, git_actions
from tree_sitter_language_pack import get_language
from pathlib import Path
import os
logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

class Workspace(Container):
    def __init__(self, folder_view: FolderView | None = None, file_path_passed="", *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo = get_repo.get_repo(os.getcwd())
        self.file_path_passed = file_path_passed
        self.folder_view = folder_view
        self.command_map = {
            "open_file": self.open_file,
            "create_file": self.create_file,
            "quit_app": self.quit_app,
            "focus_terminal": self.focus_terminal,
            "focus_editor": self.focus_editor,
            "save_file": self.save_file,
            "save_file_as": self.save_file_as,
            "close_tab": self.close_tab,
            "next_tab": self.next_tab,
            "previous_tab": self.previous_tab,
            "toggle_sidebar": self.toggle_sidebar,
            "undo": self.undo,
            "redo": self.redo,
            "find": self.find,
            "go_to_line": self.go_to_line,
            "select_syntax": self.select_syntax,
            "git_add_commit_push": self.git_add_commit_push,
            "git_add": self.git_add,
            "git_commit": self.git_commit,
            "git_push": self.git_push
        }
    def has_got_dirty_files(self):
        return self.tab_manager.has_dirty_files()
    def on_mount(self):
        # owns the tab manager
        tabs = {}
        if self.file_path_passed != "":
            tabs.update({"0":EditorView(file_path=self.file_path_passed, classes="editor-view")})
        else:
            tabs.update({"0":EditorView()})
        self.tab_manager = TabManager(tabs, repo=self.repo)

        self.mount(self.tab_manager)
        self.terminal = Terminal("/bin/zsh", "> ")
        self.terminal_container = TerminalContainer(terminal=self.terminal)
        self.mount(self.terminal_container)
        self.focus()
    def on_workspace_new_tab(self, event: WorkspaceNewTab):
        self.open_file_popup = OpenFilePopup()
        self.mount(self.open_file_popup)
    def on_app_next_tab(self, event: AppNextTab):
        logging.info("message recieved in Workspace")
        self.tab_manager.post_message(WorkspaceNextTab())
    def on_file_path_provided(self, event: FilePathProvided):
        if self.tab_manager.tabs:
            max_id = max(int(tab_id) for tab_id in self.tab_manager.tabs.keys())
        else:
            max_id = -1
        next_id = str(max_id+1)
        prev_file_path = self.tab_manager.get_active_editor().file_path
        prev_file_editor = self.tab_manager.get_active_editor()
        self.new_tab(event.file_path, next_id)
        # replace empty unsaved files with the new file opened
        if prev_file_path == "" and prev_file_editor.code_area.text.strip() == "":
            self.tab_manager.remove_tab(prev_file_editor.tab_id)
        logging.info(self.tab_manager.tabs)
    def on_command_palette_command(self, event: CommandPaletteCommand):
        """Dispatch a command by name."""
        command = event.command
        kwargs = event.kwargs
        func = self.command_map.get(command)
        if func:
            func(**kwargs)
        else:
            print(f"Unknown command: {command}")
    def find_and_replace(self, editor: EditorView):
        self.mount(FindAndReplace(editor=editor))
    # === Command implementations ===
    def open_file(self, **kwargs):
        print("Opening file…")
        self.post_message(WorkspaceNewTab())

    def create_file(self, **kwargs):
        print("Creating file…")
        self.post_message(WorkspaceNewTab())

    def quit_app(self, **kwargs):
        print("Quitting app…")
        quit()

    def focus_terminal(self, **kwargs):
        print("Focusing terminal…")
        self.terminal.focus()

    def focus_editor(self, **kwargs):
        print("Focusing editor…")
        self.tab_manager.get_active_editor().code_area.focus()

    def save_file(self, **kwargs):
        print("Saving file…")
        self.tab_manager.get_active_editor().code_area.save_file()

    def save_file_as(self, **kwargs):
        print("Saving file as…")
        self.tab_manager.get_active_editor().code_area.save_as()

    def close_tab(self, **kwargs):
        self.tab_manager.post_message(WorkspaceRemoveTab())
    def next_tab(self, **kwargs):
        self.tab_manager.next_tab(self.tab_manager.active_tab)

    def previous_tab(self, **kwargs):
        print("Switching to previous tab…")
        self.tab_manager.previous_tab(self.tab_manager.active_tab)

    def toggle_sidebar(self, **kwargs):
        print("Toggling sidebar…")
        # your sidebar logic

    def undo(self, **kwargs):
        print("Undo…")
        self.tab_manager.post_message(EditorUndo())

    def redo(self, **kwargs):
        print("Redo…")
        self.tab_manager.post_message(EditorRedo())

    def find(self, **kwargs):
        print("Find…")
        self.find_and_replace(self.tab_manager.get_active_editor())

    def go_to_line(self, **kwargs):
        num_lines = len(self.tab_manager.get_active_editor().code_area.document.lines)
        self.mount(LineInput(num_lines))
        # move cursor to line
    def select_syntax(self):
        logging.info("Selecting syntax")
        syntaxes = list(self.tab_manager.get_active_editor().code_area.available_languages)
        # custom_langs = [
        #     "elisp",
        #     "make",
        #     "dockerfile",
        #     "go-mod",
        #     "sqlite",
        #     "elixir",
        #     "elm",
        #     "kotlin",
        #     "objc",
        #     "sql",
        #     "hcl",
        #     "r",
        #     "dot",
        #     "hack",
        #     "haskell",
        # ]
        # syntaxes = list(set(syntaxes + custom_langs))
        logging.info(len(syntaxes))
        available = []
        for name in syntaxes:
            try:
                lang = get_language(name)
                available.append(name)
            except Exception:
                pass

        self.mount(SelectSyntax(available))
    def git_add_commit_push(self):
        self.show_commit_input(id="all_3")
    def git_add(self):
        res = git_actions.git_add(self.repo)
        if res:
            self.mount(SuccessOverlay("Successfully staged all files"))
    def git_commit(self):
        self.show_commit_input(id="commit")
    def git_push(self):
        res = git_actions.git_push_origin_main(self.repo)
        if res:
            self.mount(SuccessOverlay("Successfully pushed commit to branch main"))
    
    def new_tab(self, path, tab_id):
        logging.info("path: " + path)
        logging.info("workspace thinks this is tab id: " + str(tab_id))
        self.tab_manager.add_tab(tab_id, EditorView(file_path=path))
    def open_command_palette(self):
        # the value is "what message should i send when its selected"
        # the message will then be sent to a core module and evaluated based on a load of cases
        # then when the real command is found, it is ran/executed/etc
        
        commands = {
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
            "Close Current Tab": "close_tab",
            "Next Tab": "next_tab",
            "Previous Tab": "previous_tab",
            "Toggle Sidebar": "toggle_sidebar",
            "Undo": "undo",
            "Redo": "redo",
            "Find": "find",
            "Go To Line": "go_to_line",
        }
        self.command_palette = CommandPalette(commands)
        self.mount(self.command_palette)
    def on_open_command_palette(self, event: OpenCommandPalette):
        self.open_command_palette()
    def on_focus_editor(self, event: FocusEditor):
        logging.info("focusing editor")
        editor = self.tab_manager.get_active_editor()
        logging.info(editor)
        editor.code_area.focus()
    
    def on_select_syntax_event(self, event: SelectSyntaxEvent):
        syntax = event.syntax
        logging.info("syntax selected: "+syntax)
        if event.syntax != "none":
            self.tab_manager.get_active_editor().code_area.language = syntax
        else:
            self.tab_manager.get_active_editor().code_area.language = None
    def on_git_commit_message_submitted(self, message: GitCommitMessageSubmitted):
        message_id = message.message_id
        commit_message = message.commit_message
        if message_id == "all_3":
            res = git_actions.git_add_commit_push(self.repo, commit_message)
            if res:
                self.mount(SuccessOverlay("Successfully added, commited and pushed all changes."))
        elif message_id == "commit":
            res = git_actions.git_commit(self.repo, commit_message)
            if res:
                self.mount(SuccessOverlay("Successfully committed changes"))
        message.input_widget.remove()
    def show_commit_input(self, id="commit"):
        self.mount(GitCommitMessage(message_id=id))
    def on_line_input_submitted(self, event: LineInputSubmitted):
        num_lines = len(self.tab_manager.get_active_editor().code_area.document.lines)
        if int(event.line) <= num_lines:
            self.tab_manager.get_active_editor().code_area.move_cursor((int(event.line)-1, 0))
        else:
            self.line_input = LineInput(num_lines)
            self.mount(self.line_input)

    async def on_tab_message(self, event: TabMessage):
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
                self.tab_manager.get_active_editor().code_area.post_message(TabMessage())
            else:
                pass
        except:
            pass
    def save_all_files(self):
        # if this doesnt work iterate over tabs.keys
        for tab in self.tab_manager.tabs.keys():
            editor = self.tab_manager.tabs[tab]
            if editor.file_path:
                editor: EditorView
                editor.code_area.save_file()
            else:
                pass