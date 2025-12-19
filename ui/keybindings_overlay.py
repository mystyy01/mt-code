"""Keybindings overlay for viewing and editing keybindings."""

from textual.app import ComposeResult
from textual.containers import Container, Horizontal, VerticalScroll
from textual.widgets import Button, Static, Input, Select
from textual import events
import logging

from ui.overlay import Overlay
from core.keybindings import get_keybindings_manager
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Available commands for the command type
AVAILABLE_COMMANDS = [
    ("Run File", "run_file"),
    ("Open File", "open_file"),
    ("Create File", "create_file"),
    ("Quit", "quit_app"),
    ("Select Syntax", "select_syntax"),
    ("Git Add Commit Push", "git_add_commit_push"),
    ("Git Add", "git_add"),
    ("Git Commit", "git_commit"),
    ("Git Push", "git_push"),
    ("Focus Terminal", "focus_terminal"),
    ("Focus Editor", "focus_editor"),
    ("Save", "save_file"),
    ("Save As", "save_file_as"),
    ("Rename File", "rename_file"),
    ("Close Tab", "close_tab"),
    ("Next Tab", "next_tab"),
    ("Previous Tab", "previous_tab"),
    ("Toggle Sidebar", "toggle_sidebar"),
    ("Undo", "undo"),
    ("Redo", "redo"),
    ("Find", "find"),
    ("Go To Line", "go_to_line"),
    ("Edit Plugins", "edit_plugins"),
    ("Edit Keybindings", "edit_keybindings"),
    ("Command Palette", "command_palette"),
]


class KeybindingRow(Horizontal):
    """A single row representing a keybinding."""

    DEFAULT_CSS = """
    KeybindingRow {
        height: auto;
        min-height: 3;
        padding: 0 1;
        border-bottom: solid $primary-darken-3;
        width: 100%;
    }

    KeybindingRow:hover {
        background: $primary-darken-2;
    }

    KeybindingRow .keybind-key {
        width: 18;
        color: $success;
        content-align: left middle;
    }

    KeybindingRow .keybind-desc {
        width: 1fr;
        color: $text;
        content-align: left middle;
        overflow: hidden;
    }

    KeybindingRow .rebind-btn {
        width: 10;
        min-width: 10;
    }

    KeybindingRow .del-btn {
        width: 7;
        min-width: 7;
        margin-left: 1;
    }
    """

    def __init__(self, key: str, binding: dict, row_index: int, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.key = key
        self.binding = binding
        self.row_index = row_index

    def compose(self) -> ComposeResult:
        yield Static(self.key, classes="keybind-key")
        yield Static(self.binding.get("description", ""), classes="keybind-desc")
        yield Button("Rebind", id=f"rebind-row-{self.row_index}", classes="rebind-btn")
        yield Button("Del", variant="error", id=f"del-row-{self.row_index}", classes="del-btn")


class AddKeybindingOverlay(Overlay):
    """Overlay for adding/editing a single keybinding."""
    # No way to select what the keybind does - maybe the buttons are clipping off the width of the overlay?
    DEFAULT_CSS = """
    AddKeybindingOverlay {
        align: center middle;
        width: 100%;
        height: 70%;
        background: $surface 80%;
        position: absolute;
        /* offset: 30% 30%; */
    }

    #add-keybind-container {
        width: 80;
        height: 100%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #add-keybind-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $text;
    }

    .add-row {
        height: 70%;
        min-height: 3;
        margin-bottom: 1;
        width: 100%;
    }

    .add-label {
        width: 14;
        content-align: right middle;
        padding-right: 1;
    }

    #key-display {
        width: 20;
        height: 3;
        content-align: center middle;
        background: $primary-darken-2;
        border: solid $primary;
    }

    #set-key-btn {
        margin-left: 1;
    }

    #waiting-indicator {
        margin-left: 1;
        color: $warning;
        content-align: left middle;
        width: 1fr;
    }

    #add-type-select {
        width: 30;
    }

    #add-action-select {
        width: 50;
    }

    #add-action-input {
        width: 50;
    }

    #add-desc-input {
        width: 50;
    }

    #add-buttons {
        height: 5;
        align: center middle;
        margin-top: 1;
        width: 100%;
        padding: 1;
    }

    #add-buttons Button {
        margin: 0 2;
        min-width: 10;
    }

    #save-add-btn {
        min-width: 10;
    }

    #cancel-add-btn {
        min-width: 10;
    }

    #set-key-btn {
        min-width: 12;
    }
    """

    def __init__(self, parent_overlay, edit_key: str = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent_overlay = parent_overlay
        self.manager = get_keybindings_manager()
        self.listening_for_key = False
        self.captured_key = edit_key
        self.edit_key = edit_key  # Original key if editing
        self.current_type = "command"
        self.can_focus = True
    def compose(self) -> ComposeResult:
        title = "Edit Keybinding" if self.edit_key else "Add Keybinding"
        with Container(id="add-keybind-container"):
            yield Static(title, id="add-keybind-title")

            with Horizontal(classes="add-row"):
                yield Static("Key:", classes="add-label")
                yield Static(self.captured_key or "(none)", id="key-display")
                yield Button("Set Key", id="set-key-btn")
                yield Static("", id="waiting-indicator")

            with Horizontal(classes="add-row"):
                yield Static("Type:", classes="add-label")
                yield Select(
                    [("Command", "command"), ("Bash", "bash")],
                    value="command",
                    id="add-type-select"
                )

            with Horizontal(classes="add-row", id="action-row"):
                yield Static("Action:", classes="add-label")
                yield Select(
                    AVAILABLE_COMMANDS,
                    value="run_file",
                    id="add-action-select"
                )

            with Horizontal(classes="add-row"):
                yield Static("Description:", classes="add-label")
                yield Input(placeholder="Description (optional)", id="add-desc-input")

            with Horizontal(id="add-buttons"):
                yield Button("Save", id="save-add-btn", variant="success")
                yield Button("Cancel", id="cancel-add-btn")

    def on_mount(self):
        super().on_mount()
        # If editing, load existing values
        if self.edit_key:
            binding = self.manager.get_binding(self.edit_key)
            if binding:
                binding_type = binding.get("type", "command")
                self.current_type = binding_type

                type_select = self.query_one("#add-type-select", Select)
                type_select.value = binding_type

                # Update action field based on type
                action_value = binding.get("action", "")
                if binding_type == "command":
                    # Just update the existing select value
                    action_select = self.query_one("#add-action-select", Select)
                    action_select.value = action_value if action_value else "run_file"
                else:
                    # Need to swap to input field
                    self._update_action_field(binding_type, action_value)

                desc_input = self.query_one("#add-desc-input", Input)
                desc_input.value = binding.get("description", "")

    def _update_action_field(self, binding_type: str, current_value: str = ""):
        """Update the action field based on binding type."""
        action_row = self.query_one("#action-row", Horizontal)

        # Remove existing action widget
        try:
            old_select = self.query_one("#add-action-select", Select)
            old_select.remove()
        except Exception:
            pass
        try:
            old_input = self.query_one("#add-action-input", Input)
            old_input.remove()
        except Exception:
            pass

        # Add appropriate widget
        if binding_type == "command":
            select = Select(
                AVAILABLE_COMMANDS,
                value=current_value if current_value else "run_file",
                id="add-action-select"
            )
            action_row.mount(select)
        else:
            input_widget = Input(
                placeholder="Bash command (use %file% and %dir%)",
                id="add-action-input",
                value=current_value
            )
            action_row.mount(input_widget)

    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle type selection change."""
        if event.select.id == "add-type-select":
            new_type = str(event.value)
            if new_type != self.current_type:
                self.current_type = new_type
                self._update_action_field(new_type)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "set-key-btn":
            if self.listening_for_key:
                self.stop_listening()
            else:
                self.start_listening()
        elif button_id == "save-add-btn":
            self.save_binding()
        elif button_id == "cancel-add-btn":
            self.close_overlay()

    def start_listening(self):
        """Start listening for key press."""
        self.listening_for_key = True
        indicator = self.query_one("#waiting-indicator", Static)
        indicator.update("Press a key...")
        btn = self.query_one("#set-key-btn", Button)
        btn.label = "Cancel"

    def stop_listening(self):
        """Stop listening for key press."""
        self.listening_for_key = False
        indicator = self.query_one("#waiting-indicator", Static)
        indicator.update("")
        btn = self.query_one("#set-key-btn", Button)
        btn.label = "Set Key"

    def on_key(self, event: events.Key) -> None:
        """Handle key events."""
        if event.key == "escape":
            if self.listening_for_key:
                self.stop_listening()
                event.prevent_default()
                event.stop()
                return
            # Close overlay and show parent
            self.close_overlay()
            event.prevent_default()
            event.stop()
            return

        if self.listening_for_key:
            self.captured_key = event.key
            key_display = self.query_one("#key-display", Static)
            key_display.update(event.key)
            self.stop_listening()
            event.prevent_default()
            event.stop()

    def save_binding(self):
        """Save the keybinding."""
        if not self.captured_key:
            return

        type_select = self.query_one("#add-type-select", Select)
        desc_input = self.query_one("#add-desc-input", Input)

        binding_type = str(type_select.value) if type_select.value else "command"
        description = desc_input.value

        # Get action based on type
        if binding_type == "command":
            try:
                action_select = self.query_one("#add-action-select", Select)
                action = str(action_select.value) if action_select.value else ""
            except Exception:
                return
        else:
            try:
                action_input = self.query_one("#add-action-input", Input)
                action = action_input.value
            except Exception:
                return

        if not action:
            return

        # If editing and key changed, remove old binding
        if self.edit_key and self.edit_key != self.captured_key:
            self.manager.remove_binding(self.edit_key)

        # Set the binding
        self.manager.set_binding(self.captured_key, binding_type, action, description)
        self.manager.save_keybindings()

        # Refresh parent and close
        self.parent_overlay.refresh_list()
        self.close_overlay()

    def close_overlay(self):
        """Close this overlay and show parent."""
        self.parent_overlay.styles.display = "block"
        self.remove()


class KeybindingsOverlay(Overlay):
    """Overlay for viewing and editing keybindings."""

    DEFAULT_CSS = """
    KeybindingsOverlay {
        align: center middle;
        width: 100%;
        height: 100%;
        background: $surface 80%;
    }

    #keybindings-container {
        width: 100;
        height: 100%;
        max-height: 85%;
        background: $surface;
        border: tall $primary;
        padding: 1 2;
    }

    #keybindings-title {
        text-align: center;
        text-style: bold;
        padding-bottom: 1;
        color: $text;
    }

    #keybindings-list {
        height: 50%;
        max-height: 25;
        border: solid $primary-darken-2;
        margin-bottom: 1;
        overflow-x: auto;
    }

    .header-row {
        height: 3;
        padding: 0 1;
        background: $primary-darken-1;
        text-style: bold;
    }

    .header-row Static {
        content-align: left middle;
    }

    .header-key {
        width: 18;
    }

    .header-desc {
        width: 1fr;
    }

    .header-spacer {
        width: 18;
    }

    #button-row {
        height: auto;
        min-height: 3;
        align: center middle;
    }

    #button-row Button {
        margin: 0 1;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.manager = get_keybindings_manager()
        self.can_focus = True
    def on_mount(self):
        self.focus()
    def compose(self) -> ComposeResult:
        with Container(id="keybindings-container"):
            yield Static("Keybindings", id="keybindings-title")

            # Header row
            with Horizontal(classes="header-row"):
                yield Static("Key", classes="header-key")
                yield Static("Description", classes="header-desc")
                yield Static("", classes="header-spacer")

            # Scrollable list of keybindings
            with VerticalScroll(id="keybindings-list"):
                for i, (key, binding) in enumerate(sorted(self.manager.get_all_bindings().items())):
                    yield KeybindingRow(key, binding, row_index=i)

            # Buttons
            with Horizontal(id="button-row"):
                yield Button("Add", id="add-btn", variant="success")
                yield Button("Reset", id="reset-btn", variant="warning")
                yield Button("Close", id="close-btn")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id

        if button_id == "close-btn":
            self.remove()
        elif button_id == "add-btn":
            self.open_add_overlay()
        elif button_id == "reset-btn":
            self.reset_to_defaults()
        elif button_id and button_id.startswith("rebind-row-"):
            row = event.button.parent
            if isinstance(row, KeybindingRow):
                self.open_edit_overlay(row.key)
        elif button_id and button_id.startswith("del-row-"):
            row = event.button.parent
            if isinstance(row, KeybindingRow):
                self.delete_binding(row.key)

    def open_add_overlay(self):
        """Open the add keybinding overlay."""
        self.styles.display = "none"
        add_overlay = AddKeybindingOverlay(parent_overlay=self)
        self.app.mount(add_overlay)
        add_overlay.focus()

    def open_edit_overlay(self, key: str):
        """Open the edit keybinding overlay."""
        self.styles.display = "none"
        self.app.mount(AddKeybindingOverlay(parent_overlay=self, edit_key=key))

    def delete_binding(self, key: str):
        """Delete a keybinding."""
        self.manager.remove_binding(key)
        self.manager.save_keybindings()
        self.refresh_list()

    def reset_to_defaults(self):
        """Reset all keybindings to defaults."""
        self.manager.reset_to_defaults()
        self.manager.save_keybindings()
        self.refresh_list()

    def refresh_list(self):
        """Refresh the keybindings list."""
        keybindings_list = self.query_one("#keybindings-list", VerticalScroll)

        # Remove all existing rows
        for child in list(keybindings_list.children):
            child.remove()

        # Add new rows
        for i, (key, binding) in enumerate(sorted(self.manager.get_all_bindings().items())):
            keybindings_list.mount(KeybindingRow(key, binding, row_index=i))
