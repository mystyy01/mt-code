from textual import events
from textual.widgets import TextArea, Static, Input, OptionList
from textual.widgets.option_list import Option
from core.file_management import read_file, delete_file, save_file
from typing import Literal
from textual.message import Message
from textual.events import Event
from textual.content import Content
from rich.console import RenderableType
import logging 
from utils.add_languages import register_supported_languages
from commands.messages import EditorSavedAs, UseFile, EditorOpenFile, EditorSaveFile, WorkspaceNextTab, TabMessage, CompletionSelected
from lsp.pyright import PyrightServer
from pathlib import Path
import asyncio
from ui.overlay import Overlay

class CompletionsOverlay(Overlay):
    """Overlay widget for showing code completions."""
    
    def __init__(self, completions: list, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.completions = completions[:5]  # Store only first 5
        logging.info(f"CompletionsOverlay created with {len(self.completions)} items")
    
    def compose(self):
        """Create child widgets."""
        options = []
        for i, item in enumerate(self.completions):
            label = item.get("label", "")
            # Also include detail/kind if available for richer display
            kind = item.get("kind", "")
            detail = item.get("detail", "")
            
            display_text = label
            if detail:
                display_text = f"{label} - {detail}"
            
            logging.info(f"Adding option: {display_text}")
            options.append(Option(display_text, id=str(i)))
        
        if not options:
            logging.warning("No options to display!")
            options.append(Option("No completions", id="0"))
        
        self.completions_list = OptionList(*options, id="completions_list")
        logging.info(f"OptionList created with {len(options)} options")
        yield self.completions_list
    
    def on_mount(self):
        """Override parent on_mount to not add overlay class."""
        # Don't call super().on_mount() to avoid the overlay class styling
        # which might be hiding the content
        logging.info(f"CompletionsOverlay mounted, option count: {len(self.completions_list._options)}")
    
    def on_option_list_option_selected(self, event: OptionList.OptionSelected):
        """Handle completion selection."""
        if event.option_list.id == "completions_list":
            index = int(event.option.id)
            completion = self.completions[index]
            self.post_message(CompletionSelected(completion))
            self.remove()
    
    def on_key(self, event: events.Key):
        """Handle key events."""
        if event.key == "escape":
            self.remove()
        elif event.key == "enter":
            # Select the highlighted option
            if self.completions_list.highlighted is not None:
                selected = self.completions[self.completions_list.highlighted]
                self.post_message(CompletionSelected(selected))
                self.remove()


