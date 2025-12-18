import logging
from typing import List, Dict, Tuple
from textual.widgets import TextArea

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class DiagnosticSeverity:
    """LSP diagnostic severity levels."""
    ERROR = 1
    WARNING = 2
    INFORMATION = 3
    HINT = 4


class DiagnosticsHandler:
    """Handle LSP diagnostics and apply styling to the editor."""
    
    def __init__(self, editor: TextArea):
        self.editor = editor
        self.diagnostics: List[Dict] = []
        self.styled_ranges: List[Tuple[int, int, int, int]] = []  # (start_line, start_col, end_line, end_col)
    
    def update_diagnostics(self, diagnostics: List[Dict]):
        """Update the diagnostics list and apply styling.
        
        Args:
            diagnostics: List of diagnostic objects from LSP
        """
        self.diagnostics = diagnostics
        logging.info(f"Received {len(diagnostics)} diagnostics")
        
        # Clear previous styling
        self.clear_diagnostics()
        
        # Apply new styling
        for diagnostic in diagnostics:
            self._apply_diagnostic_style(diagnostic)
    
    def _apply_diagnostic_style(self, diagnostic: Dict):
        """Apply styling for a single diagnostic.
        
        Args:
            diagnostic: A single diagnostic object with range, severity, message
        """
        try:
            range_data = diagnostic.get('range', {})
            start = range_data.get('start', {})
            end = range_data.get('end', {})
            severity = diagnostic.get('severity', DiagnosticSeverity.ERROR)
            message = diagnostic.get('message', '')
            
            start_line = start.get('line', 0)
            start_col = start.get('character', 0)
            end_line = end.get('line', 0)
            end_col = end.get('character', 0)
            
            logging.info(
                f"Diagnostic: line {start_line}:{start_col}-{end_line}:{end_col} "
                f"severity={severity} msg='{message}'"
            )
            
            # Store the range for later reference
            self.styled_ranges.append((start_line, start_col, end_line, end_col))
            
            # Apply styling based on severity
            style_name = self._get_style_name(severity)
            
            # TextArea uses internal methods to apply styling
            # We'll use the highlight API if available
            self._highlight_range(start_line, start_col, end_line, end_col, style_name)
            
        except Exception as e:
            logging.error(f"Error applying diagnostic style: {e}", exc_info=True)
    
    def _get_style_name(self, severity: int) -> str:
        """Get the style name for a severity level."""
        if severity == DiagnosticSeverity.ERROR:
            return "error"
        elif severity == DiagnosticSeverity.WARNING:
            return "warning"
        elif severity == DiagnosticSeverity.INFORMATION:
            return "information"
        else:  # HINT
            return "hint"
    
    def _highlight_range(self, start_line: int, start_col: int, end_line: int, end_col: int, style: str):
        """Highlight a range in the editor.
        
        This is a simplified version. Textual's TextArea doesn't have built-in
        diagnostic highlighting, so we'll need to track these and potentially
        draw them ourselves or use a custom renderer.
        
        For now, we'll log them and you can extend this to draw underlines.
        """
        logging.info(f"Would highlight {start_line}:{start_col}-{end_line}:{end_col} with style '{style}'")
        
        # TODO: Implement actual visual highlighting
        # Options:
        # 1. Use TextArea's selection/highlight features
        # 2. Custom rendering layer
        # 3. Rich markup if the editor supports it
        # 4. Overlay widgets for underlines
        
    def clear_diagnostics(self):
        """Clear all diagnostic styling."""
        logging.info("Clearing diagnostics")
        self.diagnostics.clear()
        self.styled_ranges.clear()
        
        # TODO: Remove visual highlights
    
    def get_diagnostic_at_cursor(self, line: int, col: int) -> Dict | None:
        """Get the diagnostic at a specific cursor position.
        
        Args:
            line: Line number (0-indexed)
            col: Column number (0-indexed)
            
        Returns:
            Diagnostic dict if found, None otherwise
        """
        for diagnostic in self.diagnostics:
            range_data = diagnostic.get('range', {})
            start = range_data.get('start', {})
            end = range_data.get('end', {})
            
            start_line = start.get('line', 0)
            start_col = start.get('character', 0)
            end_line = end.get('line', 0)
            end_col = end.get('character', 0)
            
            # Check if cursor is within range
            if start_line <= line <= end_line:
                if line == start_line and col < start_col:
                    continue
                if line == end_line and col > end_col:
                    continue
                return diagnostic
        
        return None
    
    def get_diagnostics_for_line(self, line: int) -> List[Dict]:
        """Get all diagnostics for a specific line.
        
        Args:
            line: Line number (0-indexed)
            
        Returns:
            List of diagnostic dicts
        """
        result = []
        for diagnostic in self.diagnostics:
            range_data = diagnostic.get('range', {})
            start = range_data.get('start', {})
            end = range_data.get('end', {})
            
            start_line = start.get('line', 0)
            end_line = end.get('line', 0)
            
            if start_line <= line <= end_line:
                result.append(diagnostic)
        
        return result