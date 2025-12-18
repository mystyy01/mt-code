"""Session management for mt-code.

Handles saving and restoring session state per project folder.
Session data is stored in .mt-code/session.json in the project root.
"""

import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class Session:
    """Manages session state for a project folder."""

    SESSION_DIR = ".mt-code"
    SESSION_FILE = "session.json"

    def __init__(self, project_root: str | Path):
        """Initialize session for a project folder.

        Args:
            project_root: Path to the project folder
        """
        self.project_root = Path(project_root).resolve()
        self.session_dir = self.project_root / self.SESSION_DIR
        self.session_file = self.session_dir / self.SESSION_FILE
        self._data: Dict[str, Any] = {}
        self._load()

    def _ensure_session_dir(self):
        """Create the .mt-code directory if it doesn't exist."""
        if not self.session_dir.exists():
            self.session_dir.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created session directory: {self.session_dir}")

    def _load(self):
        """Load session data from disk."""
        if self.session_file.exists():
            try:
                with open(self.session_file, "r") as f:
                    self._data = json.load(f)
                logging.info(f"Loaded session from {self.session_file}")
            except (json.JSONDecodeError, IOError) as e:
                logging.error(f"Failed to load session: {e}")
                self._data = {}
        else:
            self._data = {}

    def save(self):
        """Save session data to disk."""
        self._ensure_session_dir()
        try:
            with open(self.session_file, "w") as f:
                json.dump(self._data, f, indent=2)
            logging.info(f"Saved session to {self.session_file}")
        except IOError as e:
            logging.error(f"Failed to save session: {e}")

    def get(self, key: str, default=None) -> Any:
        """Get a session value.

        Args:
            key: The key to get
            default: Default value if key doesn't exist

        Returns:
            The value or default
        """
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        """Set a session value.

        Args:
            key: The key to set
            value: The value to store
        """
        self._data[key] = value

    # === Tab State Methods ===

    def get_open_tabs(self) -> List[Dict[str, Any]]:
        """Get the list of open tabs from session.

        Returns:
            List of tab info dicts with 'file_path' and 'is_active' keys
        """
        return self.get("open_tabs", [])

    def set_open_tabs(self, tabs: List[Dict[str, Any]]):
        """Save the list of open tabs to session.

        Args:
            tabs: List of tab info dicts with 'file_path' and 'is_active' keys
        """
        self.set("open_tabs", tabs)
        self.save()

    def get_active_tab_path(self) -> Optional[str]:
        """Get the path of the active tab.

        Returns:
            File path of the active tab or None
        """
        return self.get("active_tab_path")

    def set_active_tab_path(self, path: Optional[str]):
        """Set the active tab path.

        Args:
            path: File path of the active tab
        """
        self.set("active_tab_path", path)

    def save_tab_state(self, tab_paths: List[str], active_path: Optional[str] = None):
        """Convenience method to save tab state.

        Args:
            tab_paths: List of file paths for open tabs
            active_path: Path of the currently active tab
        """
        tabs = []
        for path in tab_paths:
            tabs.append({
                "file_path": path,
                "is_active": path == active_path
            })
        self.set_open_tabs(tabs)
        self.set_active_tab_path(active_path)
        self.save()

    def get_tab_paths(self) -> List[str]:
        """Get just the file paths of open tabs.

        Returns:
            List of file paths
        """
        tabs = self.get_open_tabs()
        return [t.get("file_path", "") for t in tabs if t.get("file_path")]

    def clear(self):
        """Clear all session data."""
        self._data = {}
        self.save()
