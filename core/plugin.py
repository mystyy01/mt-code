"""Base plugin class for mt-code plugins.

Plugins should be stored in the plugins/ folder with the naming convention:
    name_of_plugin.py -> class NameOfPlugin(Plugin)

Example:
    plugins/git_extension.py would contain:

    from core.plugin import Plugin

    class GitExtension(Plugin):
        name = "Git Extension"
        description = "Adds git functionality"
        version = "1.0.0"

        def on_enable(self):
            # Called when plugin is enabled
            pass

        def on_disable(self):
            # Called when plugin is disabled
            pass

        def on_edit(self):
            # Return a widget to mount for plugin settings
            return None
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING
import json
import os
from pathlib import Path

if TYPE_CHECKING:
    from textual.widget import Widget


class Plugin(ABC):
    """Base class for all mt-code plugins."""

    # Plugin metadata - override in subclasses
    name: str = "Unnamed Plugin"
    description: str = "No description provided"
    version: str = "0.0.1"
    author: str = "Unknown"

    def __init__(self, app=None):
        """Initialize the plugin.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self.enabled = False
        self.settings = {}
        self._load_settings()

    @property
    def settings_path(self) -> Path:
        """Path to this plugin's settings file."""
        config_dir = Path(__file__).parent.parent / "config" / "plugins"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / f"{self.__class__.__name__.lower()}.json"

    def _load_settings(self):
        """Load plugin settings from disk."""
        if self.settings_path.exists():
            try:
                with open(self.settings_path, "r") as f:
                    data = json.load(f)
                    self.enabled = data.get("enabled", False)
                    self.settings = data.get("settings", {})
            except (json.JSONDecodeError, IOError):
                self.enabled = False
                self.settings = {}

    def _save_settings(self):
        """Save plugin settings to disk."""
        try:
            with open(self.settings_path, "w") as f:
                json.dump({
                    "enabled": self.enabled,
                    "settings": self.settings
                }, f, indent=2)
        except IOError:
            pass

    def enable(self):
        """Enable the plugin."""
        if not self.enabled:
            self.enabled = True
            self.on_enable()
            self._save_settings()

    def disable(self):
        """Disable the plugin."""
        if self.enabled:
            self.enabled = False
            self.on_disable()
            self._save_settings()

    def toggle(self):
        """Toggle the plugin's enabled state."""
        if self.enabled:
            self.disable()
        else:
            self.enable()

    @abstractmethod
    def on_enable(self):
        """Called when the plugin is enabled.

        Override this method to add functionality when the plugin is enabled.
        This could include registering keybindings, adding menu items, etc.
        """
        pass

    @abstractmethod
    def on_disable(self):
        """Called when the plugin is disabled.

        Override this method to clean up when the plugin is disabled.
        This could include unregistering keybindings, removing menu items, etc.
        """
        pass

    @abstractmethod
    def on_edit(self) -> "Widget | None":
        """Called when the user wants to edit plugin settings.

        Override this method to return a widget (usually an Overlay) that
        allows the user to configure the plugin's settings.

        Returns:
            A widget to mount for editing settings, or None if no settings UI.
        """
        pass

    def get_setting(self, key: str, default=None):
        """Get a plugin setting value.

        Args:
            key: The setting key
            default: Default value if key doesn't exist

        Returns:
            The setting value or default
        """
        return self.settings.get(key, default)

    def set_setting(self, key: str, value):
        """Set a plugin setting value.

        Args:
            key: The setting key
            value: The value to set
        """
        self.settings[key] = value
        self._save_settings()
