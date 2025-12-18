# mt-code Plugin System

## Overview

mt-code supports a plugin system that allows you to extend functionality by writing Python scripts. Plugins are stored in the `plugins/` folder and can be managed via the command palette (`Ctrl+P` → "Edit Plugins").

## Creating a Plugin

### File Naming Convention

- File: `snake_case.py` (e.g., `my_awesome_plugin.py`)
- Class: `PascalCase` (e.g., `MyAwesomePlugin`)

The class name must match the file name converted to PascalCase.

### Basic Structure

```python
from core.plugin import Plugin

class MyAwesomePlugin(Plugin):
    # Plugin metadata
    name = "My Awesome Plugin"
    description = "A brief description of what this plugin does"
    version = "1.0.0"
    author = "Your Name"

    def on_enable(self):
        """Called when the plugin is enabled."""
        pass

    def on_disable(self):
        """Called when the plugin is disabled."""
        pass

    def on_edit(self):
        """Return a settings widget or None if no settings."""
        return None
```

### Required Methods

| Method | Description |
|--------|-------------|
| `on_enable()` | Called when the plugin is enabled. Use this to initialize functionality. |
| `on_disable()` | Called when the plugin is disabled. Use this to clean up. |
| `on_edit()` | Return a widget (usually an Overlay) for settings UI, or `None`. |

## Plugin Settings

Plugins can store persistent settings using the built-in settings API:

```python
# Get a setting (with optional default value)
value = self.get_setting("my_key", default="default_value")

# Set a setting (automatically saved to disk)
self.set_setting("my_key", "new_value")
```

Settings are stored in `config/plugins/<plugin_name>.json`.

## Creating a Settings UI

To provide a settings interface, create an Overlay class and return it from `on_edit()`:

```python
from core.plugin import Plugin
from ui.overlay import Overlay
from textual.widgets import Static, Button, Input

class MyPluginSettings(Overlay):
    def __init__(self, plugin, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.plugin = plugin
        # These are set automatically by the plugin manager
        self._plugin_manager_ref = None
        self._reopen_plugins_overlay = False

    def on_mount(self):
        super().on_mount()
        self.mount(Static("My Plugin Settings", classes="overlay_title"))
        # Add your settings UI here
        self.mount(Button("Save", id="save_btn"))

    def _close_and_reopen_plugins(self):
        """Close settings and reopen plugins overlay."""
        if self._reopen_plugins_overlay and self._plugin_manager_ref:
            from ui.plugins_overlay import PluginsOverlay
            self.app.mount(PluginsOverlay(plugin_manager=self._plugin_manager_ref))
        self.remove()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "save_btn":
            # Save settings here
            self._close_and_reopen_plugins()

    def on_key(self, event):
        if event.key == "escape":
            self._close_and_reopen_plugins()
            event.prevent_default()
            event.stop()

class MyPlugin(Plugin):
    name = "My Plugin"
    # ... other metadata ...

    def on_edit(self):
        return MyPluginSettings(plugin=self)
```

## Accessing the Application

Plugins receive a reference to the workspace via `self.app`. This gives access to:

- `self.app.tab_manager` - Manage editor tabs
- `self.app.terminal` - Access the terminal
- `self.app.folder_view` - Access the file explorer
- `self.app.plugin_manager` - Access other plugins

### Example: Accessing the Active Editor

```python
def on_enable(self):
    editor = self.app.tab_manager.get_active_editor()
    if editor:
        # Access the code area
        code = editor.code_area.text
        file_path = editor.file_path
```

## Plugin Lifecycle

1. **Discovery**: On startup, mt-code scans `plugins/` for `.py` files
2. **Loading**: Each plugin class is instantiated with `app` reference
3. **Auto-enable**: If previously enabled, `on_enable()` is called automatically
4. **Runtime**: Users can enable/disable via "Edit Plugins" in command palette
5. **Persistence**: Enabled state and settings persist across sessions

## Example Plugin

See `example_plugin.py` in this folder for a complete working example that demonstrates:

- Plugin metadata
- Enable/disable hooks
- Settings UI with input field
- Persistent settings storage

## Tips

- Keep plugins focused on a single feature
- Use logging for debugging: `import logging; logging.info("message")`
- Test enable/disable cycles to ensure proper cleanup
- Use `self.app.mount()` to add UI elements
- Access existing UI components through `self.app`
