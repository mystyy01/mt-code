"""Plugin manager for discovering and loading mt-code plugins."""

import importlib
import importlib.util
import logging
import os
import re
from pathlib import Path
from typing import Dict, List, Type

from core.plugin import Plugin
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase.

    Args:
        name: Snake case string (e.g., 'git_extension')

    Returns:
        Pascal case string (e.g., 'GitExtension')
    """
    return ''.join(word.capitalize() for word in name.split('_'))


class PluginManager:
    """Manages discovery, loading, and lifecycle of plugins."""

    def __init__(self, app=None):
        """Initialize the plugin manager.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_classes: Dict[str, Type[Plugin]] = {}
        self._plugins_dir = Path(__file__).parent.parent / "plugins"

    @property
    def plugins_dir(self) -> Path:
        """Path to the plugins directory."""
        return self._plugins_dir

    def discover_plugins(self) -> List[str]:
        """Discover all plugin files in the plugins directory.

        Returns:
            List of plugin module names (without .py extension)
        """
        if not self.plugins_dir.exists():
            self.plugins_dir.mkdir(parents=True, exist_ok=True)
            return []

        plugin_files = []
        for file in self.plugins_dir.glob("*.py"):
            if file.name.startswith("_"):
                continue
            plugin_files.append(file.stem)

        logging.info(f"Discovered plugins: {plugin_files}")
        return plugin_files

    def load_plugin(self, module_name: str) -> Plugin | None:
        """Load a single plugin by module name.

        Args:
            module_name: Name of the plugin module (e.g., 'git_extension')

        Returns:
            Loaded plugin instance or None if loading failed
        """
        try:
            # Build the path to the plugin file
            plugin_path = self.plugins_dir / f"{module_name}.py"
            if not plugin_path.exists():
                logging.error(f"Plugin file not found: {plugin_path}")
                return None

            # Load the module
            spec = importlib.util.spec_from_file_location(
                f"plugins.{module_name}",
                plugin_path
            )
            if spec is None or spec.loader is None:
                logging.error(f"Failed to load spec for plugin: {module_name}")
                return None

            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)

            # Find the plugin class (PascalCase version of the module name)
            class_name = snake_to_pascal(module_name)
            if not hasattr(module, class_name):
                logging.error(f"Plugin class {class_name} not found in {module_name}")
                return None

            plugin_class = getattr(module, class_name)
            if not issubclass(plugin_class, Plugin):
                logging.error(f"{class_name} does not inherit from Plugin")
                return None

            # Store the class and create an instance
            self.plugin_classes[module_name] = plugin_class
            plugin_instance = plugin_class(app=self.app)
            self.plugins[module_name] = plugin_instance

            logging.info(f"Loaded plugin: {plugin_instance.name} v{plugin_instance.version}")

            # Auto-enable if it was previously enabled
            if plugin_instance.enabled:
                plugin_instance.on_enable()

            return plugin_instance

        except Exception as e:
            logging.exception(f"Failed to load plugin {module_name}: {e}")
            return None

    def load_all_plugins(self):
        """Discover and load all plugins."""
        plugin_names = self.discover_plugins()
        for name in plugin_names:
            self.load_plugin(name)

    def reload_plugin(self, module_name: str) -> Plugin | None:
        """Reload a plugin (useful for development).

        Args:
            module_name: Name of the plugin module

        Returns:
            Reloaded plugin instance or None if failed
        """
        # Disable and remove the old instance
        if module_name in self.plugins:
            old_plugin = self.plugins[module_name]
            if old_plugin.enabled:
                old_plugin.disable()
            del self.plugins[module_name]

        if module_name in self.plugin_classes:
            del self.plugin_classes[module_name]

        # Load fresh
        return self.load_plugin(module_name)

    def get_plugin(self, module_name: str) -> Plugin | None:
        """Get a plugin instance by module name.

        Args:
            module_name: Name of the plugin module

        Returns:
            Plugin instance or None if not loaded
        """
        return self.plugins.get(module_name)

    def get_all_plugins(self) -> List[Plugin]:
        """Get all loaded plugin instances.

        Returns:
            List of all loaded plugins
        """
        return list(self.plugins.values())

    def get_enabled_plugins(self) -> List[Plugin]:
        """Get all enabled plugin instances.

        Returns:
            List of enabled plugins
        """
        return [p for p in self.plugins.values() if p.enabled]

    def enable_plugin(self, module_name: str) -> bool:
        """Enable a plugin by module name.

        Args:
            module_name: Name of the plugin module

        Returns:
            True if successful, False otherwise
        """
        plugin = self.plugins.get(module_name)
        if plugin:
            plugin.enable()
            return True
        return False

    def disable_plugin(self, module_name: str) -> bool:
        """Disable a plugin by module name.

        Args:
            module_name: Name of the plugin module

        Returns:
            True if successful, False otherwise
        """
        plugin = self.plugins.get(module_name)
        if plugin:
            plugin.disable()
            return True
        return False

    def toggle_plugin(self, module_name: str) -> bool:
        """Toggle a plugin's enabled state.

        Args:
            module_name: Name of the plugin module

        Returns:
            True if successful, False otherwise
        """
        plugin = self.plugins.get(module_name)
        if plugin:
            plugin.toggle()
            return True
        return False
