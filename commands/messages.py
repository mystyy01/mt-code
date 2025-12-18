from textual.message import Message
from textual.widgets import Input
class EditorSavedAs(Message):
    def __init__(self, contents: str):
        super().__init__()
        self.contents = contents
class FilePathProvided(Message):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
class SaveAsProvided(Message):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
class UseFile(Message):
    def __init__(self, file_path: str):
        super().__init__()
        self.file_path = file_path
class EditorOpenFile(Message):
    def __init__(self):
        super().__init__()
class WorkspaceNewTab(Message):
    def __init__(self):
        super().__init__()
class WorkspaceRemoveTab(Message):
    def __init__(self):
        super().__init__()
class WorkspaceNextTab(Message):
    def __init__(self):
        super().__init__()
class AppNextTab(Message):
    def __init__(self):
        super().__init__()
class EditorDirtyFile(Message):
    def __init__(self, tab_id: str, file_path: str):
        super().__init__()
        self.tab_id = tab_id
        self.file_path = file_path
class EditorSaveFile(Message):
    def __init__(self, tab_id: str):
        super().__init__()
        self.tab_id = tab_id
class CommandPaletteCommand(Message):
    def __init__(self, command: str, **kwargs):
        super().__init__()
        self.command = command
        self.kwargs = kwargs
class SelectSyntaxEvent(Message):
    def __init__(self, syntax: str, **kwargs):
        super().__init__()
        self.syntax = syntax
        self.kwargs = kwargs
class OpenCommandPalette(Message):
    def __init__(self):
        super().__init__()
class EditorUndo(Message):
    def __init__(self):
        super().__init__()
class EditorRedo(Message):
    def __init__(self):
        super().__init__()
class FocusEditor(Message):
    def __init__(self):
        super().__init__()
class GitCommitMessageSubmitted(Message):
    def __init__(self, message_id: str, message: str, input: Input, **kwargs):
        super().__init__()
        self.commit_message = message
        self.message_id = message_id
        self.input_widget = input
        self.kwargs = kwargs
class LineInputSubmitted(Message):
    def __init__(self, line: str, **kwargs):
        super().__init__()
        self.line = line
        self.kwargs = kwargs
class TabMessage(Message):
    def __init__(self):
        super().__init__()
class FileSelected(Message):
    def __init__(self, path):
        super().__init__()
        self.path = path
class OpenFolder(Message):
    def __init__(self, path):
        super().__init__()
        self.path = path
class SaveAllFiles(Message):
    def __init__(self):
        super().__init__()
class CompletionSelected(Message):
    """Message sent when a completion is selected."""

    def __init__(self, completion: dict):
        super().__init__()
        self.completion = completion

class RenameFileProvided(Message):
    """Message sent when a new file name is provided for renaming."""

    def __init__(self, old_path: str, new_path: str):
        super().__init__()
        self.old_path = old_path
        self.new_path = new_path

