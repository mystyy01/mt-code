from textual.containers import Container, Vertical
from textual.widget import Widget
from textual.reactive import reactive
from textual.events import Key
from textual.widgets import Static, Button

class Overlay(Container):
    def on_mount(self):
        self.classes = "overlay" 
        
    def on_key(self, event: Key):
        if event.key=="escape":
            self.remove()
