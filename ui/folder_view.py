from textual.widgets import DirectoryTree
import logging
from commands.messages import FileSelected
from pathlib import Path
import asyncio

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

class FolderView(DirectoryTree):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watch_path()
    async def watch_path_for_changes(self, path: Path, interval: float = 1.0):
        path = Path(path)
        if not path.is_dir():
            raise ValueError(f"{path} is not a valid directory")

        previous_children = set(path.iterdir())

        while True:
            await asyncio.sleep(interval)
            current_children = set(path.iterdir())
            if current_children != previous_children:
                added = current_children - previous_children
                removed = previous_children - current_children
                logging.info(f"Folder changes detected. Added: {added}, Removed: {removed}")
                # You could also post a message or update the UI here
                previous_children = current_children
                self.path = self.path

    async def on_mount(self):
        # Run the watcher in the background
        asyncio.create_task(self.watch_path_for_changes(Path(self.path), interval=1.0))

    def on_directory_tree_file_selected(self, event: DirectoryTree.FileSelected):
        logging.info("file selected")
        self.post_message(FileSelected(event.path))

    def on_directory_tree_directory_selected(self, event: DirectoryTree.DirectorySelected):
        logging.info("folder selected")
