"""Tab manager - manages editor tabs and their state.

This module provides the TabManager class which handles:
- Tab creation and removal
- Tab switching and navigation (via TabNavigationMixin)
- Tab bar UI management
- File dirty state tracking
"""

from textual.containers import Container, Horizontal
from textual.widgets import Button
from pathlib import Path
import logging

from ui.editor_view import EditorView
from ui.tab import Tab
from ui.tab_navigation import TabNavigationMixin
from ui.run_button import RunButton
from commands.messages import (
    WorkspaceRemoveTab, WorkspaceNextTab, UseFile,
    EditorDirtyFile, EditorSaveFile, EditorUndo, EditorRedo
)
from git import Repo
from git_utils import git_file_status
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class TabManager(TabNavigationMixin, Container):
    """Manages editor tabs and the tab bar UI."""

    def __init__(self, tabs: dict, repo: Repo, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs = tabs
        self.repo = repo
        # Keep an ordered list of currently mounted tab ids (strings)
        self.tab_order: list[str] = []
        # Monotonic counter for allocating new tab ids within a session
        self.next_tab_id = 0
        logging.info(tabs)

    # === Path Utilities ===

    def make_relative(self, full_path: str) -> str:
        """Convert a full path to a relative path from project root."""
        full_path = Path(full_path).resolve()
        base_dir = Path(__file__).parent.parent.resolve()
        try:
            return str(full_path.relative_to(base_dir))
        except ValueError:
            return full_path.name

    # === Tab Bar Management ===

    def add_to_tab_bar(self, tab_id: str, editor: EditorView):
        """Add a tab button to the tab bar."""
        if tab_id not in self.tabs:
            return
        logging.info("add_tab_to_bar thinks editor.filepath = " + str(editor.file_path))
        logging.info("add_tab_to_bar thinks tab_id = " + tab_id)

        if editor.file_path != "":
            if editor.file_path.startswith("/"):
                tab_title = self.make_relative(editor.file_path)
            else:
                tab_title = editor.file_path
            if self.repo:
                status = git_file_status.get_file_git_status(self.repo, editor.file_path)
                tab_title = tab_title + " " + status
            tab_button = Tab(saved=True, label=str(tab_title), id="t" + tab_id, classes="tab_button")
        else:
            tab_button = Tab(saved=False, label="unsaved", id="t" + tab_id, classes="tab_button")
        self.tab_bar.mount(tab_button)
        if tab_id not in self.tab_order:
            self.tab_order.append(tab_id)

    def remove_from_tab_bar(self, tab_id: str):
        """Remove a tab button from the tab bar."""
        button = None
        for child in list(self.tab_bar.children):
            if isinstance(child, Button) and child.id == f"t{tab_id}":
                button = child
                break
        if button:
            button.remove()

    # === Tab State Management ===

    def get_active_editor(self) -> EditorView | None:
        """Return the currently active editor."""
        if self.active_tab is None:
            return None
        return self.tabs.get(self.active_tab)

    def get_next_tab_id(self):
        """Get the next available tab ID."""
        nid = str(self.next_tab_id)
        self.next_tab_id += 1
        return nid

    def has_dirty_files(self):
        """Check if any tabs have unsaved changes."""
        for tab_id in self.tab_order:
            tab_name = self.tab_bar.query_one(f"#t{tab_id}").label
            if "*" in tab_name:
                return True
        return False

    # === Tab Operations ===

    def on_mount(self):
        """Initialize the tab bar and existing tabs."""
        self.tab_bar = Horizontal(id="tab_bar")
        self.mount(self.tab_bar)
        self.run_button = RunButton(id="run_button")
        self.tab_bar.mount(self.run_button)

        if self.tabs:
            self.tabs = {str(k): v for k, v in self.tabs.items()}
            try:
                max_id = max(int(k) for k in self.tabs.keys())
                self.next_tab_id = max_id + 1
            except Exception:
                self.next_tab_id = 0
            self.tab_order = [str(k) for k in self.tabs.keys()]
            self.active_tab = "0" if "0" in self.tabs else (self.tab_order[0] if self.tab_order else None)
            logging.info(self.tabs)
            if self.active_tab and self.active_tab in self.tabs:
                logging.info((self.tabs[self.active_tab]).file_path)
        else:
            self.active_tab = None

        for tab_id, editor in self.tabs.items():
            if tab_id == self.active_tab:
                self.add_tab(tab_id, editor, first_tabs=True)
            else:
                logging.info(tab_id, editor)
                self.add_tab(tab_id, editor, first_tabs=True)

        if self.tabs[self.active_tab]:
            if self.active_tab and self.active_tab in self.tabs and self.tabs[self.active_tab]:
                logging.info(self.active_tab, self.tabs[self.active_tab])
                self.mount(self.tabs[self.active_tab])

    def add_tab(self, tab_id: str, editor: EditorView, first_tabs=False):
        """Add a new tab with the given editor."""
        logging.info("add_tab thinks its editor should be tab_id: " + tab_id)
        editor.tab_id = tab_id
        if not first_tabs:
            logging.info("adding second tab")
        self.tabs.update({tab_id: editor})
        self.add_to_tab_bar(tab_id, editor)
        if not editor.is_mounted:
            self.mount(editor)
        if not first_tabs:
            self.tab_bar.query_one(f"#t{tab_id}").press()
        else:
            self.tab_bar.query_one(f"#t{tab_id}").disabled = True

    def switch_tab(self, tab_id: str):
        """Switch to the specified tab."""
        tab_widget = self.tab_bar.query_one(f"#t{tab_id}")
        logging.info("Tab name: " + tab_widget.label)

        tab_editor = self.tabs.get(tab_id)
        logging.info("Tab editor: " + str(tab_editor.file_path))

        if tab_editor is None:
            logging.warning(f"switch_tab called with invalid tab_id: {tab_id}")
            return

        current_editor = self.get_active_editor()
        if current_editor:
            current_editor.hide()

        tab_editor.show()
        self.active_tab = tab_id

        for tab in [c for c in self.tab_bar.children if isinstance(c, Button)]:
            tab.disabled = False
        tab_widget.disabled = True

        try:
            if hasattr(tab_editor, "code_area") and tab_editor.code_area:
                tab_editor.code_area.focus()
        except Exception:
            logging.exception(f"Failed to focus editor for tab {tab_id}")

    def remove_tab(self, tab_id: str):
        """Remove the specified tab."""
        buttons_now = [c for c in self.tab_bar.children if isinstance(c, Button)]
        if len(buttons_now) <= 1:
            logging.info("Attempted to close last tab")
            return

        logging.info("Removing tab %s", tab_id)

        next_tab = self.get_nearest_tab(tab_id)
        logging.info("Next tab will be %s", next_tab)

        if self.active_tab == tab_id:
            editor = self.get_active_editor()
            if editor:
                editor.remove()

        btn = next((b for b in buttons_now if b.id == f"t{tab_id}"), None)
        if btn:
            btn.remove()

        self.tabs.pop(tab_id, None)
        try:
            self.tab_order.remove(tab_id)
        except ValueError:
            pass

        if next_tab:
            self.switch_tab(next_tab)
            try:
                tab_btn = self.tab_bar.query_one(f"#t{next_tab}")
                tab_btn.disabled = True
            except Exception:
                pass
        else:
            self.active_tab = None

    def remove_editor(self, tab_id: str):
        """Remove the editor widget for a tab."""
        editor = self.get_active_editor()
        if editor:
            editor.remove()

    # === Tab Label Management ===

    def dirty_label(self, tab_id: str):
        """Mark a tab as dirty (unsaved)."""
        logging.info(tab_id)
        try:
            tab_widget: Tab = self.tab_bar.query_one(f"#t{tab_id}")
        except Exception:
            logging.warning("Could not find tab widget for id %s", tab_id)
            return
        try:
            tab_widget.mark_dirty()
        except Exception:
            logging.exception("Failed marking tab %s dirty", tab_id)

    def save_label(self, tab_id):
        """Mark a tab as saved."""
        logging.info(tab_id)
        try:
            tab_widget: Tab = self.tab_bar.query_one(f"#t{tab_id}")
        except Exception:
            logging.warning("Could not find tab widget for id %s", tab_id)
            return
        try:
            tab_widget.save_file()
        except Exception:
            logging.exception("Failed saving tab label for %s", tab_id)

    # === Event Handlers ===

    def on_button_pressed(self, event: Button.Pressed):
        """Handle tab button press."""
        if "tab_button" in event.button.classes:
            tab_id = event.button.id[1:]
            logging.info(tab_id)
            self.switch_tab(tab_id)

    def on_workspace_remove_tab(self, message: WorkspaceRemoveTab):
        """Handle tab removal request."""
        old_tab = self.active_tab
        self.remove_tab(old_tab)

    def on_workspace_next_tab(self, message: WorkspaceNextTab):
        """Handle next tab request."""
        logging.info("message recieved")
        tid = self.get_next_tab(self.active_tab)
        self.switch_tab(tid)

    def on_use_file(self, message: UseFile):
        """Handle request to use a file (e.g., from SaveAs)."""
        logging.info("using file: %s", message.file_path)
        active = self.active_tab
        logging.info("active = " + str(active))
        if active is None:
            logging.info("Active tab = None")
            self.add_tab(self.get_next_tab_id(), EditorView(file_path=message.file_path))
            return

        current = self.get_active_editor()
        if current:
            try:
                current.remove()
            except Exception:
                pass

        new_editor = EditorView(file_path=message.file_path)
        new_editor.tab_id = active
        self.tabs[active] = new_editor

        try:
            tab_widget = self.tab_bar.query_one(f"#t{active}")
            if isinstance(tab_widget, Tab):
                if message.file_path.startswith("/"):
                    tab_widget.label = self.make_relative(message.file_path)
                else:
                    tab_widget.label = message.file_path
                try:
                    tab_widget.save_file()
                except Exception:
                    pass
            else:
                logging.warning("Tab widget for %s is not a Tab instance: %s", active, type(tab_widget))
        except Exception:
            logging.exception("Failed updating tab widget for %s", active)

        try:
            self.mount(new_editor)
            new_editor.code_area.focus()
            self.post_message(EditorSaveFile(tab_id=new_editor.tab_id))
        except Exception:
            logging.exception("Failed mounting new editor for tab %s", active)

    def on_editor_dirty_file(self, message: EditorDirtyFile):
        """Handle editor dirty notification."""
        self.dirty_label(message.tab_id)

    def on_editor_save_file(self, message: EditorSaveFile):
        """Handle editor save notification."""
        logging.info("undirtying file")
        self.save_label(message.tab_id)

    def on_editor_undo(self, message: EditorUndo):
        """Handle undo request."""
        self.get_active_editor().undo()

    def on_editor_redo(self, message: EditorRedo):
        """Handle redo request."""
        self.get_active_editor().redo()
