from textual import events
from textual.widgets import Static, Input, OptionList
from textual.widgets.option_list import Option
from ui.overlay import Overlay
from textual.binding import Binding
from commands.messages import FilePathProvided
import os
import difflib
import logging

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class OpenFilePopup(Overlay):
    BINDINGS = [
        Binding("tab", "auto_complete", "Auto-complete file/folder", priority=True)
    ]

    def on_mount(self):
        self.root_dir = os.getcwd()
        self.cwd = self.root_dir
        self.search_text = ""
        self.file_options = []

        self.mount(Static("Open file"))

        self.file_name_input = Input(
            placeholder="relative/path/to/open", classes="open_file"
        )
        self.mount(self.file_name_input)
        self.file_name_input.focus()

        self.files_option_list = OptionList(*self.file_options, classes="files_option_list")
        self.files_option_list.disabled = True
        self.mount(self.files_option_list)

        self.update_options()

    def update_options(self):
        """Populate OptionList with entries in self.cwd, dirs with / appended."""
        if not os.path.isdir(self.cwd):
            return

        entries = os.listdir(self.cwd)
        entries.sort(key=lambda f: (not os.path.isdir(os.path.join(self.cwd, f)), f.lower()))

        self.entries = []
        self.file_options.clear()
        for entry in entries:
            full_path = os.path.join(self.cwd, entry)
            display_name = entry + ("/" if os.path.isdir(full_path) else "")
            self.entries.append(display_name)
            self.file_options.append(Option(display_name))

        # Update OptionList
        self.files_option_list.clear_options()
        for opt in self.file_options:
            self.files_option_list.add_option(opt)

    async def on_input_changed(self, event: Input.Changed):
        typed_path = event.value.strip()
        self.search_text = typed_path

        # Determine new cwd from everything before last slash
        if "/" in typed_path:
            path_before_last_slash = typed_path.rsplit("/", 1)[0]
        else:
            path_before_last_slash = ""

        # Resolve relative to root
        new_cwd = os.path.normpath(os.path.join(self.root_dir, path_before_last_slash))
        if os.path.isdir(new_cwd):
            self.cwd = new_cwd
            logging.info(f"Changed cwd to {self.cwd}")
            self.update_options()

        # Fuzzy search only last segment, strip trailing / for matching
        search_term = typed_path.split("/")[-1].rstrip("/")
        match_entries = [e.rstrip("/") for e in self.entries]
        if search_term:
            matches = difflib.get_close_matches(search_term, match_entries, n=len(match_entries), cutoff=0)
        else:
            matches = match_entries

        # Map back to entries with / if directory
        display_matches = []
        for m in matches:
            for e in self.entries:
                if e.rstrip("/") == m:
                    display_matches.append(e)
                    break

        self.files_option_list.clear_options()
        for name in display_matches:
            self.files_option_list.add_option(Option(name))

    async def on_input_submitted(self, event: Input.Submitted):
        if "open_file" in event.input.classes:
            self.file_path = event.input.value
            self.post_message(FilePathProvided(self.file_path))
            self.remove()

    def action_auto_complete(self):
        logging.info("Tab pressed for auto-complete")
        if not self.search_text:
            return

        # Last segment typed
        last_segment = self.search_text.split("/")[-1].rstrip("/")
        match_entries = [e.rstrip("/") for e in self.entries]
        matches = difflib.get_close_matches(last_segment, match_entries, n=1, cutoff=0)
        if not matches:
            return

        top_match = matches[0]

        # Determine if matched entry is a directory
        matched_display = next((e for e in self.entries if e.rstrip("/") == top_match), top_match)
        append_slash = "/" if matched_display.endswith("/") else ""

        # Replace last segment with matched entry
        path_parts = self.search_text.rsplit("/", 1)
        if len(path_parts) == 1:
            completed = top_match + append_slash
        else:
            completed = f"{path_parts[0]}/{top_match}{append_slash}"

        self.file_name_input.value = completed
        self.file_name_input.cursor_position = len(completed)
