"""Example plugin demonstrating the mt-code plugin system.

This plugin shows how to create a basic plugin with:
- Enable/disable functionality
- Settings UI
- Custom settings storage
"""

from core.plugin import Plugin
from textual.widgets import Static, Button, Input
from textual.containers import Vertical
from ui.overlay import Overlay


class ExamplePluginSettings(Overlay):
    """Settings overlay for the example plugin."""

    def __init__(self, plugin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin = plugin
        self._plugin_manager_ref = None
        self._reopen_plugins_overlay = False

    def on_mount(self):
        super().on_mount()
        self.mount(Static("Example Plugin Settings", classes="overlay_title"))

        # Show current greeting setting
        current_greeting = self.plugin.get_setting("greeting", "Hello")
        self.mount(Static(f"Current greeting: {current_greeting}"))

        # Input for changing greeting
        self.greeting_input = Input(
            placeholder="Enter new greeting",
            value=current_greeting,
            id="greeting_input"
        )
        self.mount(self.greeting_input)

        # Save button
        self.mount(Button("Save", id="save_settings"))

    def _close_and_reopen_plugins(self):
        """Close this overlay and reopen the plugins overlay."""
        if self._reopen_plugins_overlay and self._plugin_manager_ref:
            from ui.plugins_overlay import PluginsOverlay
            self.app.mount(PluginsOverlay(plugin_manager=self._plugin_manager_ref))
        self.remove()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save_settings":
            new_greeting = self.greeting_input.value
            self.plugin.set_setting("greeting", new_greeting)
            self._close_and_reopen_plugins()

    def on_key(self, event):
        """Handle escape key to close and reopen plugins overlay."""
        if event.key == "escape":
            self._close_and_reopen_plugins()
            event.prevent_default()
            event.stop()


class ExamplePlugin(Plugin):
    """An example plugin that demonstrates the plugin system."""

    name = "Example Plugin"
    description = "A sample plugin that shows how to create mt-code plugins. It adds a greeting feature that can be customized."
    version = "1.0.0"
    author = "mt-code"

    def on_enable(self):
        """Called when the plugin is enabled."""
        greeting = self.get_setting("greeting", "Hello")
        print(f"{greeting} from Example Plugin! Plugin enabled.")

    def on_disable(self):
        """Called when the plugin is disabled."""
        print("Goodbye from Example Plugin! Plugin disabled.")

    def on_edit(self):
        """Return a settings widget for this plugin."""
        return ExamplePluginSettings(plugin=self)
