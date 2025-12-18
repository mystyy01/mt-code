from ui.overlay import Overlay
from textual.widgets import Input, OptionList, Static
from textual.widgets.option_list import Option
from commands.messages import CommandPaletteCommand
from textual.binding import Binding
import difflib

class CommandPalette(Overlay):
    BINDINGS = [
        Binding("tab", "auto_complete", "Auto-complete command", priority=True)
    ]

    def __init__(self, commands: dict, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commands = commands
        self.search_text = ""

    def on_mount(self):
        # Option list with search bar
        self.search_bar = Input(placeholder=">")
        self.mount(self.search_bar)
        self.search_bar.focus()

        command_options = [Option(cmd) for cmd in self.commands]
        self.option_list = OptionList(*command_options, classes="commands_options")
        self.mount(self.option_list)

        self.status = Static("Command palette")
        self.mount(self.status)

    async def on_input_changed(self, event: Input.Changed):
        query = event.value
        self.search_text = query

        # Fuzzy ranking
        all_commands = list(self.commands.keys())
        if query:
            matches = difflib.get_close_matches(query, all_commands, n=len(all_commands), cutoff=0)
        else:
            matches = all_commands

        # Clear and re-mount OptionList with new order
        self.option_list.clear_options()
        for name in matches:
            self.option_list.add_option(Option(name))

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.value in self.commands:
            self.status.update("Selected: " + event.input.value)
            self.post_message(CommandPaletteCommand(self.commands[event.input.value]))
            self.remove()
        else:
            self.option_list.focus()
            self.option_list.action_first()

    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        self.status.update("Selected: " + event.option.prompt)
        self.post_message(CommandPaletteCommand(self.commands[event.option.prompt]))
        self.remove()

    def action_auto_complete(self):
        """Autocomplete input to the top fuzzy match."""
        if not self.search_text:
            return

        all_commands = list(self.commands.keys())
        matches = difflib.get_close_matches(self.search_text, all_commands, n=1, cutoff=0)
        if matches:
            top_match = matches[0]
            self.search_bar.value = top_match
            self.search_bar.cursor_position = len(top_match)
            self.search_text = top_match
