from ui.overlay import Overlay
from textual.widgets import Button, Static
class SuccessOverlay(Overlay):
    def __init__(self, message, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = message
    def on_mount(self):
        self.mount(Static(self.message, classes="success_message"))
        button = Button("close", classes="close_button")
        self.mount(button)
        button.focus()
    def on_button_pressed(self, event: Button.Pressed):
        self.remove()
        
