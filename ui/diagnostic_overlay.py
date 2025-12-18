from textual.widgets import Static
from textual.containers import Container
import logging

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class DiagnosticMarker(Static):
    """A visual marker for a diagnostic (error/warning underline)."""
    
    def __init__(self, diagnostic: dict, line: int, start_col: int, end_col: int, *args, **kwargs):
        super().__init__("", *args, **kwargs)
        self.diagnostic = diagnostic
        self.line = line
        self.start_col = start_col
        self.end_col = end_col
        self.severity = diagnostic.get('severity', 1)
        
        # Apply CSS class based on severity
        if self.severity == 1:  # Error
            self.add_class("diagnostic-error")
        elif self.severity == 2:  # Warning
            self.add_class("diagnostic-warning")
        else:
            self.add_class("diagnostic-hint")
    
    def render(self) -> str:
        """Render the underline marker."""
        # Calculate the width of the underline
        width = self.end_col - self.start_col
        if width <= 0:
            width = 1
        
        # Create a string of ~ or ^ characters for the underline
        if self.severity == 1:  # Error
            return "~" * width
        elif self.severity == 2:  # Warning
            return "~" * width
        else:
            return "." * width


class DiagnosticTooltip(Static):
    """Tooltip showing diagnostic message on hover."""
    
    def __init__(self, message: str, *args, **kwargs):
        super().__init__(message, *args, **kwargs)
        self.add_class("diagnostic-tooltip")