from textual.containers import Vertical

class SideView(Vertical):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)