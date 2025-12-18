"""Plugins management overlay for mt-code."""

from textual.widgets import Static, Button, OptionList
from textual.widgets.option_list import Option
from textual.containers import Horizontal, Vertical
from textual.message import Message
from ui.overlay import Overlay
import logging
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class PluginSelected(Message):
    """Message sent when a plugin is selected for editing."""

    def __init__(self, plugin_name: str):
        super().__init__()
        self.plugin_name = plugin_name


class PluginsOverlay(Overlay):
    """Overlay for managing plugins."""

    def __init__(self, plugin_manager, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin_manager = plugin_manager
        self.selected_plugin = None

    def on_mount(self):
        super().on_mount()

        # Title
        self.mount(Static("Plugins", classes="overlay_title"))

        # Plugin list
        self.plugin_list = OptionList(id="plugin_list", classes="plugin_list")
        self.mount(self.plugin_list)

        # Plugin info panel
        self.info_panel = Static("Select a plugin to view details", id="plugin_info")
        self.mount(self.info_panel)

        # Buttons
        button_container = Horizontal(classes="plugin_buttons")
        self.mount(button_container)
        self.toggle_btn = Button("Enable", id="toggle_plugin", classes="plugin_btn")
        self.edit_btn = Button("Settings", id="edit_plugin", classes="plugin_btn")
        button_container.mount(self.toggle_btn)
        button_container.mount(self.edit_btn)

        # Populate the plugin list
        self.refresh_plugin_list()

    def refresh_plugin_list(self):
        """Refresh the list of plugins."""
        self.plugin_list.clear_options()

        plugins = self.plugin_manager.get_all_plugins()
        if not plugins:
            self.plugin_list.add_option(Option("No plugins installed"))
            return

        for plugin in plugins:
            status = "[ON] " if plugin.enabled else "[OFF]"
            display = f"{status} {plugin.name}"
            # Store the module name in the option id
            module_name = plugin.__class__.__name__
            # Convert PascalCase back to snake_case for module lookup
            snake_name = self._pascal_to_snake(module_name)
            self.plugin_list.add_option(Option(display, id=snake_name))

    def _pascal_to_snake(self, name: str) -> str:
        """Convert PascalCase to snake_case."""
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Handle plugin selection."""
        if event.option.id is None:
            return

        self.selected_plugin = event.option.id
        plugin = self.plugin_manager.get_plugin(self.selected_plugin)

        if plugin:
            # Update info panel
            info = f"""Name: {plugin.name}
Version: {plugin.version}
Author: {plugin.author}
Status: {'Enabled' if plugin.enabled else 'Disabled'}

{plugin.description}"""
            self.info_panel.update(info)

            # Update toggle button text
            self.toggle_btn.label = "Disable" if plugin.enabled else "Enable"

    def on_button_pressed(self, event: Button.Pressed):
        """Handle button presses."""
        if event.button.id == "toggle_plugin":
            self._toggle_selected_plugin()
        elif event.button.id == "edit_plugin":
            self._edit_selected_plugin()

    def _toggle_selected_plugin(self):
        """Toggle the selected plugin's enabled state."""
        if not self.selected_plugin:
            return

        plugin = self.plugin_manager.get_plugin(self.selected_plugin)
        if plugin:
            plugin.toggle()
            self.refresh_plugin_list()
            # Update button and info panel
            self.toggle_btn.label = "Disable" if plugin.enabled else "Enable"
            info = f"""Name: {plugin.name}
Version: {plugin.version}
Author: {plugin.author}
Status: {'Enabled' if plugin.enabled else 'Disabled'}

{plugin.description}"""
            self.info_panel.update(info)

    def _edit_selected_plugin(self):
        """Open settings for the selected plugin."""
        if not self.selected_plugin:
            return

        plugin = self.plugin_manager.get_plugin(self.selected_plugin)
        if plugin:
            settings_widget = plugin.on_edit()
            if settings_widget:
                # Store reference to plugin manager for reopening
                settings_widget._plugin_manager_ref = self.plugin_manager
                settings_widget._reopen_plugins_overlay = True
                # Remove plugins overlay and mount settings
                self.remove()
                self.app.mount(settings_widget)
            else:
                self.info_panel.update("This plugin has no settings to configure.")
