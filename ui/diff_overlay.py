"""Diff overlay for showing AI-suggested code changes."""

import difflib
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import Static, Button
from rich.text import Text
from ui.overlay import Overlay
from commands.messages import DiffAccepted


class DiffOverlay(Overlay):
    """Overlay showing diff between original and AI-suggested code."""

    DEFAULT_CSS = """
    DiffOverlay {
        width: 80%;
        height: 80%;
    }

    DiffOverlay #diff-container {
        width: 100%;
        height: 100%;
        padding: 1;
    }

    DiffOverlay #diff-title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }

    DiffOverlay #diff-scroll {
        height: 1fr;
        border: solid $primary;
        padding: 0 1;
    }

    DiffOverlay #diff-content {
        width: 100%;
    }

    DiffOverlay #button-row {
        height: 3;
        align: center middle;
        margin-top: 1;
    }

    DiffOverlay #accept-btn {
        margin-right: 2;
    }
    """

    def __init__(self, original: str, new_code: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original = original
        self.new_code = new_code

    def compose(self):
        with Vertical(id="diff-container"):
            yield Static("AI Suggested Changes", id="diff-title")
            with ScrollableContainer(id="diff-scroll"):
                yield Static(self._generate_diff(), id="diff-content")
            with Horizontal(id="button-row"):
                yield Button("Accept", id="accept-btn", variant="success")
                yield Button("Reject", id="reject-btn", variant="error")

    def _generate_diff(self) -> Text:
        """Generate a colored diff between original and new code."""
        original_lines = self.original.splitlines(keepends=True)
        new_lines = self.new_code.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            new_lines,
            fromfile="original",
            tofile="modified",
            lineterm=""
        )

        result = Text()
        for line in diff:
            line = line.rstrip('\n')
            if line.startswith('+++') or line.startswith('---'):
                result.append(line + "\n", style="bold")
            elif line.startswith('@@'):
                result.append(line + "\n", style="cyan")
            elif line.startswith('+'):
                result.append(line + "\n", style="green")
            elif line.startswith('-'):
                result.append(line + "\n", style="red")
            else:
                result.append(line + "\n", style="dim")

        if not result.plain:
            result.append("No changes detected.", style="dim italic")

        return result

    def on_mount(self):
        super().on_mount()
        accept_btn = self.query_one("#accept-btn", Button)
        accept_btn.focus()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "accept-btn":
            self.post_message(DiffAccepted(self.new_code))
            self.remove()
        elif event.button.id == "reject-btn":
            self.remove()
