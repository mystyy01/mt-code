from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Button
from ui.overlay import Overlay
from commands.messages import TabMessage, SaveAllFiles

class ConfirmExit(Overlay):
    def on_mount(self):
        self.save_button = Button("Save", classes="confirm_button padding_1")
        self.exit_button = Button("Exit without saving", classes="exit_button padding_1")
        self.mount(
            Vertical(
                Static("Do you want to save changes to unsaved files?", classes="center padding_1"),
                Static("changes will be lost otherwise", classes="grey center"),
                Static("", classes="spacer"),
                Horizontal(
                    self.save_button,
                    self.exit_button,
                    classes="bottom_buttons"
                ),
                classes="confirm_container"
            )
        )
        self.save_button.focus()
    def on_tab_message(self, event: TabMessage):
        currently_focused = self.save_button if self.save_button.has_focus else self.exit_button
        next_to_focus = self.save_button if currently_focused == self.exit_button else self.exit_button
        next_to_focus.focus()
    def on_button_pressed(self, event: Button.Pressed):
        if "confirm_button" in event.button.classes:
            pass
            self.post_message(SaveAllFiles())
        elif "exit_button" in event.button.classes:
            quit()
