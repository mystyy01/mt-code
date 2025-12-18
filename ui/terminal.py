from textual.widgets import TextArea
from textual.containers import Container
from textual.binding import Binding
import os
from commands.messages import OpenCommandPalette, FocusEditor
import pty
import logging
from textual import events
import asyncio
from pathlib import Path
import re
import pyperclip
from core.paths import LOG_FILE_STR

logging.basicConfig(filename=LOG_FILE_STR, level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")
KEY_CHAR_MAP = {
    "full_stop": ".",
    "slash": "/",
    "semicolon": ";",
    "colon": ":",
    "apostrophe": "'",
    "at": "@",
    "number_sign": "#",
    "tilde": "~",
    "grave_accent": "`",
    "minus": "-",
    "underscore": "_",
    "plus": "+",
    "equals_sign": "=",
    "not_sign": "!",
    "backslash": "\\",
    "vertical_line": "|",
    "left_square_bracket": "[",
    "right_square_bracket": "]",
    "left_curly_bracket": "{",
    "right_curly_bracket": "}",
    "left_parenthesis": "(",
    "right_parenthesis": ")",
    "quotation_mark": '"'
}

class Terminal(TextArea):
    BINDINGS = [
        # Remove enter binding - handle in on_key
    ]
    
    def __init__(self, shell: str = "/bin/zsh", *args, **kwargs):
        super().__init__(*args, **kwargs, read_only=True)
        self.shell = shell
        self.master_fd = None
        self.process_pid = None
        self.loop = asyncio.get_event_loop()
        
        # Buffer to store ALL shell output
        self.shell_output = ""
        
        # Track where the current prompt starts (to prevent backspace before it)
        self.prompt_start_pos = 0
        
        current_file = Path(__file__).resolve()
        project_root = current_file.parent.parent
        self.zshrc_path = project_root / "config" / ".mt-code-zshrc"

    def strip_ansi_codes(self, text: str) -> str:
        """Remove ANSI escape sequences from text"""
        ansi_pattern = r'\x1b\[[0-9;]*[a-zA-Z]|\x1b\].*?\x07|\x1b\[.*?[\x40-\x7e]'
        cleaned = re.sub(ansi_pattern, '', text)
        cleaned = re.sub(r'[\x00-\x08\x0b-\x0c\x0e-\x1f]', '', cleaned)
        return cleaned

    async def start_shell(self):
        self.master_fd, slave_fd = pty.openpty()
        
        # Make master_fd non-blocking
        import fcntl
        flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
        fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)
        
        self.process_pid = os.fork()
        
        if self.process_pid == 0:
            os.setsid()
            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)
            os.close(self.master_fd)
            os.close(slave_fd)
            
            env = os.environ.copy()
            env['ZDOTDIR'] = str(self.zshrc_path.parent)
            os.execvpe(self.shell, [self.shell], env)
        else:
            os.close(slave_fd)
            logging.info(f"Shell started with PID {self.process_pid}")
            self.loop.add_reader(self.master_fd, self.on_pty_data)
            
            # Wait for shell to start, then disable zle
            await asyncio.sleep(0.3)
            os.write(self.master_fd, b'unsetopt zle\n')

    def on_pty_data(self):
        if not self.prompt_start_pos:
            logging.info("line: " + self.get_line(self.cursor_location[0]).plain)
            self.prompt_start_pos = self.get_line(self.cursor_location[0]).plain.find(">")
            logging.info("start_pos: " + str(self.prompt_start_pos))
        try:
            data = os.read(self.master_fd, 4096)
        except BlockingIOError:
            return
        except OSError as e:
            logging.error(f"PTY closed: {e}")
            self.loop.remove_reader(self.master_fd)
            return
        
        if not data:
            self.loop.remove_reader(self.master_fd)
            return
        
        text = data.decode(errors="ignore")
        # handle carriage return properly
        if " " in text:
            return
        if "\r" in text:
            lines = self.text.split("\n")
            lines[-1] = ""  # clear current line
            self.text = "\n".join(lines)
            text = "\n" + text.replace("\r", "")
        logging.info(text)
        cleaned_text = self.strip_ansi_codes(text)
        logging.info(f"PTY: {repr(cleaned_text)}")
        
        # Add to buffer
        self.shell_output += cleaned_text
        
        # Strip leading newlines/whitespace from the beginning only
        display_text = self.shell_output.lstrip('\r\n')
        
        # Update the entire textarea with ALL shell output
        self.read_only = False
        self.text = display_text
        
        # Move cursor to end
        lines = self.text.split('\n')
        self.move_cursor((len(lines) - 1, len(lines[-1])))
        self.read_only = True

    def on_key(self, event: events.Key) -> None:
        if event.key=="ctrl+p":
            return
        if event.key=="ctrl+e":
            return
        if event.key=="ctrl+r":
            return
        if not self.master_fd:
            return
        
        key = event.key
        logging.info(f"Key pressed: {repr(key)}")

        self.read_only = False
        # --- ENTER ---
        if key == "enter":
            self.text += "\n"
            os.write(self.master_fd, b"\n")

        # --- SPACE ---
        elif key == "space":
            self.text += " "
            os.write(self.master_fd, b" ")

        # --- BACKSPACE ---
        elif key == "backspace":
            if self.cursor_location[1] <= self.prompt_start_pos+2:
                logging.info("hitting start_pos")
                event.prevent_default(True)
                event.stop()
                return
            # if len(self.text) > self.prompt_start_pos:
            self.shell_output = self.text[:-1]
            self.text = self.text[:-1]
            os.write(self.master_fd, b"\x7f")

        # --- CTRL KEYS ---
        elif key == "ctrl+c":
            self.read_only = True
            pyperclip.copy(self.selected_text)  # DO NOT TOUCH
            event.prevent_default()
            event.stop()
            return

        elif key == "ctrl+d":
            os.write(self.master_fd, b"\x04")

        # --- TAB ---
        elif key == "tab":
            self.text += "    "
            os.write(self.master_fd, b"\t")

        # --- ARROWS ---
        elif key == "up":
            os.write(self.master_fd, b"\x1b[A")
        elif key == "down":
            os.write(self.master_fd, b"\x1b[B")
        elif key == "left":
            os.write(self.master_fd, b"\x1b[D")
        elif key == "right":
            os.write(self.master_fd, b"\x1b[C")

        # --- SYMBOLS (Textual key names → chars) ---
        elif key in KEY_CHAR_MAP:
            char = KEY_CHAR_MAP[key]
            self.text += char
            os.write(self.master_fd, char.encode())

        # --- NORMAL PRINTABLE CHARS ---
        elif len(key) == 1 and key.isprintable():
            self.text += key
            os.write(self.master_fd, key.encode())

        # Move cursor to end
        lines = self.text.split("\n")
        self.move_cursor((len(lines) - 1, len(lines[-1])))
        self.read_only = True

        event.prevent_default()
        event.stop()

    def action_send_enter(self):
        """Deprecated - enter is handled in on_key"""
        pass

    def run_command(self, command: str):
        if self.master_fd:
            os.write(self.master_fd, (command + "\n").encode())

class TerminalContainer(Container):
    can_focus = True
    can_focus_children = True
    
    def __init__(self, terminal: Terminal, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.terminal_widget = terminal
    
    async def on_mount(self):
        self.mount(self.terminal_widget)
        await self.terminal_widget.start_shell()