from textual.app import App, ComposeResult
from textual.widgets import Static, Button, TextArea


class LayersExample(App):
    CSS_PATH = "layers.tcss"

    def on_mount(self):
        self.mount(Button("box1 (layer = above)", id="box1"))
        self.mount(TextArea("box2 (layer = below)", id="box2"))


if __name__ == "__main__":
    app = LayersExample()
    app.run()