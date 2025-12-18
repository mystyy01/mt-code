from textual.containers import Container, Horizontal
from textual.widgets import Button
from ui.editor_view import EditorView
import logging
from commands.messages import WorkspaceRemoveTab, WorkspaceNextTab, UseFile, EditorDirtyFile, EditorSaveFile, EditorUndo, EditorRedo
logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
from pathlib import Path
from ui.tab import Tab
from git import Repo
from git_utils import git_file_status

class TabManager(Container):
    def __init__(self, tabs: dict, repo: Repo,*args, **kwargs):
        super().__init__(*args, **kwargs)
        self.tabs = tabs
        self.repo = repo
        # Keep an ordered list of currently mounted tab ids (strings)
        # This ensures we can pick neighbors by index reliably and avoid
        # relying on stale dict keys when buttons are removed.
        self.tab_order: list[str] = []
        # Monotonic counter for allocating new tab ids within a session.
        # Initialized properly in on_mount based on existing tabs.
        self.next_tab_id = 0
        logging.info(tabs)
    def make_relative(self, full_path: str) -> str:
        full_path = Path(full_path).resolve()
        # Assume project root is the folder containing this script
        base_dir = Path(__file__).parent.parent.resolve()  # go up if workspace/ is inside project
        try:
            return str(full_path.relative_to(base_dir))
        except ValueError:
            # If full_path is outside project, fallback to just the file name
            return full_path.name

    def add_to_tab_bar(self, tab_id: str, editor: EditorView):
        if not tab_id in self.tabs:
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
            tab_button = Tab(saved=True, label=str(tab_title), id="t"+tab_id, classes="tab_button")
        else:
            tab_button = Tab(saved=False, label="unsaved", id="t"+tab_id, classes="tab_button")
        self.tab_bar.mount(tab_button)
        # track the tab_id in the visual order if not already present
        if tab_id not in self.tab_order:
            self.tab_order.append(tab_id)
    def get_active_editor(self) -> EditorView | None:
        """Return the currently mounted editor (active tab)."""
        if self.active_tab is None:
            return None
        return self.tabs.get(self.active_tab)

    def remove_from_tab_bar(self, tab_id: str):
        # Safely find and remove the button matching this tab id.
        button = None
        for child in list(self.tab_bar.children):
            if isinstance(child, Button) and child.id == f"t{tab_id}":
                button = child
                break
        if button:
            button.remove()
    def remove_editor(self, tab_id: str):
        editor = self.get_active_editor()
        if editor:
            editor.remove()
    def get_next_tab_id(self):
        # Use a monotonic counter so ids are never reused within a session
        nid = str(self.next_tab_id)
        self.next_tab_id += 1
        return nid
    def get_next_tab(self, tab_id: str) -> str | None:
        logging.info("get_next_tab called with tab_id=%s", tab_id)
        logging.info("Current tab_order=%s", self.tab_order)

        if not self.tab_order:
            logging.info("tab_order empty")
            return None

        try:
            current_index = self.tab_order.index(tab_id)
        except ValueError:
            logging.info("tab_id not found in tab_order: %s", tab_id)
            return None

        # Look ahead
        if current_index + 1 < len(self.tab_order):
            next_tab = self.tab_order[current_index + 1]
            logging.info("Next tab ahead: %s", next_tab)
            return next_tab

        # Nothing ahead, return the tab with the lowest numeric value
        numeric_tabs = [int(tid) for tid in self.tab_order if tid.isdigit()]
        if numeric_tabs:
            lowest_tab = str(min(numeric_tabs))
            logging.info("Nothing ahead, returning lowest tab_id: %s", lowest_tab)
            return lowest_tab

        # Fallback: just return the first tab in order
        fallback_tab = self.tab_order[0]
        logging.info("Fallback to first tab in order: %s", fallback_tab)
        return fallback_tab

    def get_nearest_tab(self, tab_id: str) -> str | None:
        logging.info("get_nearest_tab called with tab_id=%s", tab_id)
        logging.info("Current tab_order=%s", self.tab_order)

        if not self.tab_order:
            logging.info("tab_order empty")
            return None

        try:
            current = int(tab_id)
        except ValueError:
            logging.info("tab_id is not numeric: %s", tab_id)
            return None

        nearest_id = None
        nearest_distance = None

        for other in self.tab_order:
            if other == tab_id:
                logging.info("Skipping same tab_id %s", other)
                continue

            try:
                other_int = int(other)
            except ValueError:
                logging.info("Skipping non-numeric tab id: %s", other)
                continue

            distance = abs(other_int - current)

            logging.info(
                "Comparing removed tab %s -> remaining tab %s | distance=%d",
                tab_id,
                other,
                distance
            )

            if nearest_distance is None or distance < nearest_distance:
                nearest_distance = distance
                nearest_id = other
                logging.info(
                    "New nearest tab: %s (distance=%d)",
                    nearest_id,
                    nearest_distance
                )

        logging.info("Final nearest tab for %s is %s", tab_id, nearest_id)
        return nearest_id
    def get_nearest_tab_after(self, tab_id: str) -> str | None:
        logging.info("get_nearest_tab_after called with tab_id=%s", tab_id)
        logging.info("Current tab_order=%s", self.tab_order)

        if not self.tab_order:
            logging.info("tab_order empty")
            return None

        try:
            current = int(tab_id)
        except ValueError:
            logging.info("tab_id is not numeric: %s", tab_id)
            return None

        # Find all numeric tabs
        numeric_tabs = []
        for other in self.tab_order:
            try:
                numeric_tabs.append(int(other))
            except ValueError:
                logging.info("Skipping non-numeric tab id: %s", other)

        # Prefer the smallest tab ID that is higher than current
        higher_tabs = [tid for tid in numeric_tabs if tid > current]
        if higher_tabs:
            nearest_id = str(min(higher_tabs))
            logging.info("Found nearest higher tab: %s", nearest_id)
            return nearest_id

        # If no higher tabs, wrap around to the lowest tab ID
        if numeric_tabs:
            nearest_id = str(min(numeric_tabs))
            logging.info("No higher tabs, wrapping to lowest tab: %s", nearest_id)
            return nearest_id

        return None

    def get_nearest_tab_before(self, tab_id: str) -> str | None:
        logging.info("get_nearest_tab_before called with tab_id=%s", tab_id)
        logging.info("Current tab_order=%s", self.tab_order)

        if not self.tab_order:
            logging.info("tab_order empty")
            return None

        try:
            current = int(tab_id)
        except ValueError:
            logging.info("tab_id is not numeric: %s", tab_id)
            return None

        # Find all numeric tabs
        numeric_tabs = []
        for other in self.tab_order:
            try:
                numeric_tabs.append(int(other))
            except ValueError:
                logging.info("Skipping non-numeric tab id: %s", other)

        # Prefer the highest tab ID that is lower than current
        lower_tabs = [tid for tid in numeric_tabs if tid < current]
        if lower_tabs:
            nearest_id = str(max(lower_tabs))
            logging.info("Found nearest lower tab: %s", nearest_id)
            return nearest_id

        # If no lower tabs, return the lowest tab ID (wrap around)
        if numeric_tabs:
            nearest_id = str(min(numeric_tabs))
            logging.info("No lower tabs, wrapping to lowest tab: %s", nearest_id)
            return nearest_id

        return None


    def on_mount(self):
        self.tab_bar = Horizontal(id="tab_bar")
        self.mount(self.tab_bar)
        # Initialize next_tab_id and the visual tab order from existing tabs
        if self.tabs:
                # Ensure keys are strings so ids are consistent across the codebase
                self.tabs = {str(k): v for k, v in self.tabs.items()}
                try:
                    max_id = max(int(k) for k in self.tabs.keys())
                    self.next_tab_id = max_id + 1
                except Exception:
                    self.next_tab_id = 0
                # Preserve insertion order of the dict as the initial visual order
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
        # Register the editor in the model for newly-created tabs
        logging.info("add_tab thinks its editor should be tab_id: " + tab_id)
        editor.tab_id = tab_id
        if not first_tabs:
            logging.info("adding second tab")
        self.tabs.update({tab_id: editor})
        # Ensure visual tab and tab_order are created/updated
        self.add_to_tab_bar(tab_id, editor)
        # mount on first add
        if not editor.is_mounted:
            self.mount(editor)
            # editor.visible = False  # hidden until activated
        if not first_tabs: 
            self.tab_bar.query_one(f"#t{tab_id}").press()
        else:
            self.tab_bar.query_one(f"#t{tab_id}").disabled = True
    def has_dirty_files(self):
        for tab_id in self.tab_order:
            tab_name = self.tab_bar.query_one(f"#t{tab_id}").label
            if "*" in tab_name:
                return True
    def switch_tab(self, tab_id: str):
        tab_widget = self.tab_bar.query_one(f"#t{tab_id}")
        logging.info("Tab name: " + tab_widget.label)

        tab_editor = self.tabs.get(tab_id)
        logging.info("Tab editor: " + str(tab_editor.file_path))

        if tab_editor is None:
            logging.warning(f"switch_tab called with invalid tab_id: {tab_id}")
            return

        # remove current editor
        current_editor = self.get_active_editor()
        if current_editor:
            current_editor.hide()

        # mount new editor
        tab_editor.show()
        self.active_tab = tab_id

        # disable the new tab button, enable others
        for tab in [c for c in self.tab_bar.children if isinstance(c, Button)]:
            tab.disabled = False
        tab_widget.disabled = True

        try:
            if hasattr(tab_editor, "code_area") and tab_editor.code_area:
                tab_editor.code_area.focus()
        except Exception:
            logging.exception(f"Failed to focus editor for tab {tab_id}")

    def remove_tab(self, tab_id: str):
        buttons_now = [c for c in self.tab_bar.children if isinstance(c, Button)]
        if len(buttons_now) <= 1:
            logging.info("Attempted to close last tab")
            return

        logging.info("Removing tab %s", tab_id)

        # Decide next tab BEFORE mutating state
        next_tab = self.get_nearest_tab(tab_id)
        logging.info("Next tab will be %s", next_tab)

        # Remove editor if active
        if self.active_tab == tab_id:
            editor = self.get_active_editor()
            if editor:
                editor.remove()

        # Remove button
        btn = next((b for b in buttons_now if b.id == f"t{tab_id}"), None)
        if btn:
            btn.remove()

        # Remove model entries
        self.tabs.pop(tab_id, None)
        try:
            self.tab_order.remove(tab_id)
        except ValueError:
            pass

        # Switch explicitly
        if next_tab:
            self.switch_tab(next_tab)
            try:
                tab_btn = self.tab_bar.query_one(f"#t{next_tab}")
                tab_btn.disabled = True
            except Exception:
                pass
        else:
            self.active_tab = None

    def dirty_label(self, tab_id: str):
        logging.info(tab_id)
        """Mark the tab button for `tab_id` as dirty (unsaved).

        This queries the visual Tab widget mounted in the tab bar and calls
        its `mark_dirty()` helper. We guard the lookup so a missing id does
        not raise an exception.
        """
        try:
            tab_widget: Tab = self.tab_bar.query_one(f"#t{tab_id}")
        except Exception:
            logging.warning("Could not find tab widget for id %s", tab_id)
            return
        # call the widget helper to mark as dirty
        try:
            tab_widget.mark_dirty()
        except Exception:
            logging.exception("Failed marking tab %s dirty", tab_id)
    def save_label(self, tab_id):
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
    def on_button_pressed(self, event: Button.Pressed):
        if "tab_button" in event.button.classes:
            tab_id = event.button.id[1:]
            logging.info(tab_id)
            self.switch_tab(tab_id)


    def next_tab(self, active_tab):
        next_tab_id = self.get_nearest_tab_after(active_tab)
        self.switch_tab(next_tab_id)
    def previous_tab(self, active_tab):
        next_tab_id = self.get_nearest_tab_before(active_tab)
        self.switch_tab(next_tab_id)
    def on_workspace_remove_tab(self, message: WorkspaceRemoveTab):
        old_tab = self.active_tab
        self.remove_tab(old_tab)
        # logging.info(f"Tab: {old_tab}")
        # logging.info(f"Switching to {self.get_nearest_tab(old_tab)}")
        # self.switch_tab(self.get_nearest_tab(old_tab))
    def on_workspace_next_tab(self, message: WorkspaceNextTab):
        logging.info("message recieved")
        tid = self.get_next_tab(self.active_tab)
        self.switch_tab(tid)
    def on_use_file(self, message: UseFile):
        logging.info("using file: %s", message.file_path)
        # Replace the currently active tab with an editor bound to the saved file.
        # This avoids creating duplicate tabs when saving an in-memory buffer
        # via SaveAs: we keep the same tab id but swap the EditorView and
        # update the tab button label.
        active = self.active_tab
        logging.info("active = " + str(active))
        if active is None:
            # No active tab: behave like a normal new tab
            logging.info("Active tab = None")
            self.add_tab(self.get_next_tab_id(), EditorView(file_path=message.file_path))
            return

        # Remove currently mounted editor widget (if any)
        current = self.get_active_editor()
        if current:
            try:
                current.remove()
            except Exception:
                pass

        # Create and register the new editor for the same tab id
        new_editor = EditorView(file_path=message.file_path)
        new_editor.tab_id = active
        self.tabs[active] = new_editor

        # Update the tab button label to the file path
        try:
            tab_widget = self.tab_bar.query_one(f"#t{active}")
            # Only operate on our Tab widget type
            if isinstance(tab_widget, Tab):
                # compute a relative label if needed
                if message.file_path.startswith("/"):
                    tab_widget.label = self.make_relative(message.file_path)
                else:
                    tab_widget.label = message.file_path
                # mark as saved
                try:
                    tab_widget.save_file()
                except Exception:
                    pass
            else:
                logging.warning("Tab widget for %s is not a Tab instance: %s", active, type(tab_widget))
        except Exception:
            logging.exception("Failed updating tab widget for %s", active)

        # Mount the new editor
        try:
            self.mount(new_editor)
            new_editor.code_area.focus()
            self.post_message(EditorSaveFile(tab_id=new_editor.tab_id))
        except Exception:
            logging.exception("Failed mounting new editor for tab %s", active)
    def on_editor_dirty_file(self, message: EditorDirtyFile):
        self.dirty_label(message.tab_id)
    def on_editor_save_file(self, message: EditorSaveFile):
        logging.info("undirtying file")
        self.save_label(message.tab_id)
    def on_editor_undo(self, message: EditorUndo):
        self.get_active_editor().undo()
    def on_editor_redo(self, message: EditorRedo):
        self.get_active_editor().redo()


