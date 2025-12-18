from textual.app import App, ComposeResult
from textual.widgets import Static
from workspace.workspace import Workspace
from ui.overlay import PopupScreen
import sys
from pathlib import Path
# Run with: python app.py
var = 2

var
# get the argument
if len(sys.argv) >= 2:
    file_arg = sys.argv[1]
    file_path_passed = str(Path(file_arg).resolve())
else:
    file_path_passed = ""

class TextualApp(App):
    CSS_PATH = "config/app.tcss"
    async def on_mount(self):
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        self.mount(Static("Backgounr"))
        
        await self.app.push_screen(PopupScreen(title="Command Palette"))

if __name__ == "__main__":
    TextualApp().run()