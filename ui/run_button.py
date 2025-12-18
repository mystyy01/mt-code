"""Run button widget for executing files."""

from textual.widgets import Button
from textual.message import Message


class RunButtonPressed(Message):
    """Message sent when run button is pressed."""
    pass


class RunButton(Button):
    """A button to run the current file."""

    DEFAULT_CSS = """
    RunButton {
        dock: right;
        width: auto;
        min-width: 8;
        height: 3;
        background: $success;
        color: $text;
        border: none;
        padding: 0 1;
        margin: 0;
    }

    RunButton:hover {
        background: $success-darken-1;
    }

    RunButton:focus {
        background: $success-darken-2;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__("▶ Run", *args, **kwargs)

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button press."""
        event.stop()
        self.post_message(RunButtonPressed())
