"""Keybindings manager for mt-code.

This module provides:
- Default keybinding definitions
- Loading/saving user keybindings from config
- Keybinding lookup and execution
"""

import json
import logging
from pathlib import Path
from typing import Callable

from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

# Default keybindings - maps key combo to action
DEFAULT_KEYBINDINGS = {
    "ctrl+s": {"type": "command", "action": "save_file", "description": "Save file"},
    "ctrl+shift+s": {"type": "command", "action": "save_file_as", "description": "Save file as"},
    "ctrl+o": {"type": "command", "action": "open_file", "description": "Open file"},
    "ctrl+n": {"type": "command", "action": "create_file", "description": "New file"},
    "ctrl+w": {"type": "command", "action": "close_tab", "description": "Close tab"},
    "ctrl+q": {"type": "command", "action": "quit_app", "description": "Quit"},
    "ctrl+z": {"type": "command", "action": "undo", "description": "Undo"},
    "ctrl+y": {"type": "command", "action": "redo", "description": "Redo"},
    "ctrl+f": {"type": "command", "action": "find", "description": "Find"},
    "ctrl+g": {"type": "command", "action": "go_to_line", "description": "Go to line"},
    "ctrl+p": {"type": "command", "action": "command_palette", "description": "Command palette"},
    "ctrl+`": {"type": "command", "action": "focus_terminal", "description": "Focus terminal"},
    "ctrl+e": {"type": "command", "action": "focus_editor", "description": "Focus editor"},
    "ctrl+b": {"type": "command", "action": "toggle_sidebar", "description": "Toggle sidebar"},
    "f5": {"type": "command", "action": "run_file", "description": "Run file"},
    "ctrl+shift+p": {"type": "command", "action": "command_palette", "description": "Command palette"},
}

# Config file path
CONFIG_DIR = Path.home() / ".config" / "mt-code"
KEYBINDINGS_FILE = CONFIG_DIR / "keybindings.json"


class KeybindingsManager:
    """Manages keybindings for the application."""

    def __init__(self):
        self.keybindings = {}
        self.command_dispatcher = None
        self.bash_executor = None
        self.load_keybindings()

    def load_keybindings(self):
        """Load keybindings from config file, falling back to defaults."""
        # Start with defaults
        self.keybindings = dict(DEFAULT_KEYBINDINGS)

        # Try to load user config
        if KEYBINDINGS_FILE.exists():
            try:
                with open(KEYBINDINGS_FILE, "r") as f:
                    user_bindings = json.load(f)
                # Merge user bindings (override defaults)
                self.keybindings.update(user_bindings)
                logging.info(f"Loaded user keybindings from {KEYBINDINGS_FILE}")
            except Exception as e:
                logging.error(f"Failed to load keybindings: {e}")

    def save_keybindings(self):
        """Save current keybindings to config file."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            with open(KEYBINDINGS_FILE, "w") as f:
                json.dump(self.keybindings, f, indent=2)
            logging.info(f"Saved keybindings to {KEYBINDINGS_FILE}")
            return True
        except Exception as e:
            logging.error(f"Failed to save keybindings: {e}")
            return False

    def set_dispatcher(self, dispatcher: Callable):
        """Set the command dispatcher function."""
        self.command_dispatcher = dispatcher

    def set_bash_executor(self, executor: Callable):
        """Set the bash command executor function."""
        self.bash_executor = executor

    def get_binding(self, key: str) -> dict | None:
        """Get the binding for a key combo."""
        return self.keybindings.get(key)

    def set_binding(self, key: str, binding_type: str, action: str, description: str = ""):
        """Set a keybinding."""
        self.keybindings[key] = {
            "type": binding_type,
            "action": action,
            "description": description
        }

    def remove_binding(self, key: str):
        """Remove a keybinding."""
        if key in self.keybindings:
            del self.keybindings[key]

    def get_all_bindings(self) -> dict:
        """Get all keybindings."""
        return dict(self.keybindings)

    def execute_binding(self, key: str) -> bool:
        """Execute the action for a key combo. Returns True if handled."""
        binding = self.get_binding(key)
        if not binding:
            return False

        binding_type = binding.get("type", "command")
        action = binding.get("action", "")

        if binding_type == "command":
            if self.command_dispatcher:
                self.command_dispatcher(action)
                return True
        elif binding_type == "bash":
            if self.bash_executor:
                self.bash_executor(action)
                return True

        return False

    def reset_to_defaults(self):
        """Reset all keybindings to defaults."""
        self.keybindings = dict(DEFAULT_KEYBINDINGS)


# Global instance
_keybindings_manager = None


def get_keybindings_manager() -> KeybindingsManager:
    """Get the global keybindings manager instance."""
    global _keybindings_manager
    if _keybindings_manager is None:
        _keybindings_manager = KeybindingsManager()
    return _keybindings_manager
