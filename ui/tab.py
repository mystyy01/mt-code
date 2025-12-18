from textual.widgets import Button

class Tab(Button):
    def __init__(self, saved=False, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.saved = saved
    def save_file(self):
        self.saved = True
        self.label = str(self.label).strip("*")
    def mark_dirty(self):
        """Mark this tab as having unsaved changes (append a '*' to the label)."""
        self.saved = False
        self.label = str(self.label).strip("*")
        self.label = str(self.label) + "*"