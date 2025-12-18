from icecream import ic
import logging
logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")


class Buffer():
    """
    THIS CLASS IS DEPRECATED - DO NOT USE
    """
    def __init__(self, content):
        self.undo_stack = []
        self.redo_stack = []
        self.content = content
    def store_diff(self, before, after, cursor_pos):
        self.undo_stack.append({"before": before, "after": after, "cursor_pos": cursor_pos})
    def undo(self):
        if self.undo_stack == []:
            return
        if len(self.undo_stack) > 500: # 500 chars - maybe a bit low?
            self.undo_stack.pop(0)
        diff = self.undo_stack[-1]
        self.content = diff["before"]

        #push change to redo stack

        self.redo_stack.append(diff)
        logging.info(self.undo_stack)
        self.undo_stack.pop()
        logging.info(self.undo_stack)
        return self.content
    def redo(self):
        if self.redo_stack == []:
            return
        diff = self.redo_stack[-1]
        self.content = diff["after"]
        self.redo_stack.pop()
        self.undo_stack.append(diff)
        return self.content
# test use cases
# buffer = Buffer("hello")

# buffer.store_diff("llo", "nig", 2, 4)
# buffer.content = "henig"
# buffer.undo()
# buffer.redo()
        
