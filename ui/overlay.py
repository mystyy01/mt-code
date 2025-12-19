from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.reactive import reactive
from textual.events import Key
from textual.widgets import Static, Button


class Overlay(Container):
    """Base overlay class with optional width/height configuration."""

    def __init__(self, width: int = None, height: int = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._overlay_width = width
        self._overlay_height = height

    def on_mount(self):
        self.classes = "overlay"
        # Apply custom dimensions if provided
        if self._overlay_width:
            self.styles.width = self._overlay_width
        if self._overlay_height:
            self.styles.height = self._overlay_height

    def on_key(self, event: Key):
        if event.key == "escape":
            self.remove()
