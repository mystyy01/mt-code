"""Overlay for displaying multiple definition/reference locations."""

from ui.overlay import Overlay
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option
from commands.messages import GotoFileLocation
from pathlib import Path
import logging
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class ReferencesOverlay(Overlay):
    """Overlay for displaying multiple reference/definition locations."""

    def __init__(self, locations: list[dict], *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.locations = locations

    def _post_to_workspace(self, message):
        """Post message to workspace."""
        from workspace.workspace import Workspace
        workspace = self.app.query_one(Workspace)
        workspace.post_message(message)

    def on_mount(self):
        super().on_mount()
        self.title = Static("Go to Definition", classes="overlay_title")
        self.mount(self.title)

        options = []
        for i, loc in enumerate(self.locations):
            uri = loc.get("uri", "")
            range_info = loc.get("range", {})
            start = range_info.get("start", {})
            line = start.get("line", 0) + 1  # 1-indexed for display

            # Convert URI to path
            if uri.startswith("file://"):
                file_path = uri[7:]
            else:
                file_path = uri

            # Make relative path for display
            display_path = Path(file_path).name
            display_text = f"{display_path}:{line}"

            options.append(Option(display_text, id=str(i)))

        self.option_list = OptionList(*options, classes="references_list")
        self.mount(self.option_list)
        self.option_list.focus()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Handle selection of a reference."""
        index = int(event.option.id)
        location = self.locations[index]

        uri = location.get("uri", "")
        range_info = location.get("range", {})
        start = range_info.get("start", {})

        if uri.startswith("file://"):
            file_path = uri[7:]
        else:
            file_path = uri

        self._post_to_workspace(GotoFileLocation(
            file_path,
            start.get("line", 0),
            start.get("character", 0)
        ))
        self.remove()
