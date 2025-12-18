"""mt-code plugins package.

Place your plugin files here. Each plugin should be a .py file with a class
that inherits from core.plugin.Plugin.

Naming convention:
    - File: snake_case.py (e.g., my_plugin.py)
    - Class: PascalCase (e.g., MyPlugin)

Example plugin (my_plugin.py):

    from core.plugin import Plugin

    class MyPlugin(Plugin):
        name = "My Plugin"
        description = "A sample plugin"
        version = "1.0.0"
        author = "Your Name"

        def on_enable(self):
            print("Plugin enabled!")

        def on_disable(self):
            print("Plugin disabled!")

        def on_edit(self):
            # Return a widget for settings, or None
            return None
"""
