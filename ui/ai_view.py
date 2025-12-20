"""AI View - Right side panel for AI chat integration."""

import asyncio
from textual.containers import Vertical, VerticalScroll
from textual.widgets import Static, Input
from textual.app import ComposeResult
from textual import work
import logging

from core.paths import LOG_FILE_STR
from core.ai_chat import AIChat
from ui.diff_overlay import DiffOverlay

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class ChatMessage(Static):
    """A single chat message."""

    DEFAULT_CSS = """
    ChatMessage {
        width: 100%;
        padding: 1;
        margin: 0 0 1 0;
    }

    ChatMessage.user-message {
        background: $primary-darken-2;
        text-align: right;
        margin-left: 4;
    }

    ChatMessage.ai-message {
        background: $surface-darken-1;
        text-align: left;
        margin-right: 4;
    }

    ChatMessage.system-message {
        background: $warning-darken-2;
        text-align: center;
        text-style: italic;
    }
    """

    def __init__(self, content: str, role: str = "ai", *args, **kwargs):
        super().__init__(content, *args, **kwargs)
        self.role = role
        if role == "user":
            self.add_class("user-message")
        elif role == "ai":
            self.add_class("ai-message")
        else:
            self.add_class("system-message")


class AIView(Vertical):
    """Right side panel for AI chat integration."""

    DEFAULT_CSS = """
    AIView {
        dock: right;
        width: 30;
        height: 100%;
        background: $surface;
        border-left: solid $primary-darken-2;
    }

    AIView .ai-title {
        dock: top;
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: $primary-darken-1;
    }

    AIView #chat-scroll {
        height: 1fr;
        padding: 1;
    }

    AIView #chat-input {
        dock: bottom;
        height: 3;
        margin: 0 1 1 1;
    }

    AIView #typing-indicator {
        height: 1;
        color: $text-muted;
        text-style: italic;
        padding: 0 1;
    }
    """

    def __init__(self, workspace=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.workspace = workspace
        self.ai_chat = None
        self.current_ai_message = None

    def compose(self) -> ComposeResult:
        yield Static("AI Chat", classes="ai-title", id="ai-title")
        yield VerticalScroll(id="chat-scroll")
        yield Static("", id="typing-indicator")
        yield Input(placeholder="Ask about your code...", id="chat-input")

    def on_mount(self):
        """Initialize AI chat on mount."""
        self._init_ai_chat()
        self._update_title()

        # Add welcome message
        if self.ai_chat and self.ai_chat.is_available():
            provider_name = self.ai_chat.get_current_display_name()
            self._add_message(
                f"Hi! I'm {provider_name}. I can help with your code. I have access to your project files and the current editor.",
                role="ai"
            )
        else:
            self._add_message(
                "Set API key (OPENAI_API_KEY or ANTHROPIC_API_KEY) to enable AI chat",
                role="system"
            )

    def _init_ai_chat(self):
        """Initialize the AI chat backend."""
        project_root = "."
        if self.workspace:
            project_root = self.workspace.project_root

        self.ai_chat = AIChat(
            project_root=project_root,
            get_editor_content=self._get_editor_content
        )

    def _get_editor_content(self) -> str:
        """Get content from the current editor."""
        if not self.workspace:
            return ""
        try:
            editor = self.workspace.tab_manager.get_active_editor()
            if editor and hasattr(editor, 'code_area') and editor.code_area:
                file_path = editor.file_path or "(untitled)"
                content = editor.code_area.text
                return f"File: {file_path}\n\n{content}"
        except Exception as e:
            logging.error(f"Error getting editor content: {e}")
        return ""

    def _get_selected_text(self) -> str:
        """Get selected text from the current editor."""
        if not self.workspace:
            return ""
        try:
            editor = self.workspace.tab_manager.get_active_editor()
            if editor and hasattr(editor, 'code_area') and editor.code_area:
                code_area = editor.code_area
                # Check if there's a selection
                if hasattr(code_area, 'selected_text') and code_area.selected_text:
                    return code_area.selected_text
        except Exception as e:
            logging.error(f"Error getting selected text: {e}")
        return ""

    def set_workspace(self, workspace):
        """Set the workspace reference."""
        self.workspace = workspace
        self._init_ai_chat()
        self._update_title()

    def _update_title(self):
        """Update the title to show current provider."""
        try:
            title = self.query_one("#ai-title", Static)
            if self.ai_chat:
                provider_name = self.ai_chat.get_current_display_name()
                title.update(f"AI: {provider_name}")
            else:
                title.update("AI Chat")
        except Exception:
            pass

    def switch_provider(self, provider_name: str):
        """Switch to a different AI provider."""
        if self.ai_chat:
            if self.ai_chat.switch_provider(provider_name):
                self._update_title()
                display_name = self.ai_chat.get_current_display_name()
                if self.ai_chat.is_available():
                    self._add_message(f"Switched to {display_name}", role="system")
                else:
                    self._add_message(f"Switched to {display_name} (no API key set)", role="system")

    def reinit_provider(self):
        """Reinitialize the current provider (e.g., after API key change)."""
        if self.ai_chat:
            current = self.ai_chat.get_current_provider_name()
            self.ai_chat.switch_provider(current)
            self._update_title()
            if self.ai_chat.is_available():
                display_name = self.ai_chat.get_current_display_name()
                self._add_message(f"API key updated for {display_name}", role="system")

    def ask_about_code(self, code: str, is_full_file: bool = False):
        """Send code to AI with a default question."""
        if not self.ai_chat or not self.ai_chat.is_available():
            self._add_message("AI not available. Use 'Set API Key' command.", role="system")
            return

        # Build the question
        if is_full_file:
            question = "What does this code do?"
            display_msg = "[Asking about current file]"
        else:
            question = "Explain this code:"
            display_msg = f"[Selected code]\n```\n{code[:200]}{'...' if len(code) > 200 else ''}\n```"

        # Add user message to chat
        self._add_message(display_msg, role="user")

        # Build message for AI
        ai_message = f"{question}\n\n```\n{code}\n```"

        # Send to AI
        self._send_to_ai(ai_message)

    def _add_message(self, content: str, role: str = "ai"):
        """Add a message to the chat."""
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        message = ChatMessage(content, role=role)
        chat_scroll.mount(message)
        # Scroll to bottom
        chat_scroll.scroll_end(animate=False)
        return message

    def _update_typing_indicator(self, text: str = ""):
        """Update the typing indicator."""
        indicator = self.query_one("#typing-indicator", Static)
        indicator.update(text)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle user input submission."""
        if event.input.id != "chat-input":
            return

        user_text = event.value.strip()
        if not user_text:
            return

        # Clear input
        event.input.value = ""

        # Get selected text for context
        selected_text = self._get_selected_text()

        # Build display message (what user sees)
        if selected_text:
            display_msg = f"{user_text}\n\n[Selected code included]"
        else:
            display_msg = user_text

        # Add user message to chat
        self._add_message(display_msg, role="user")

        # Check if AI is available
        if not self.ai_chat or not self.ai_chat.is_available():
            self._add_message("AI not available. Use 'Set API Key' command.", role="system")
            return

        # Handle special commands
        if user_text.lower() == "/clear":
            self._clear_chat()
            return

        # Build message for AI with selected code context
        if selected_text:
            ai_message = f"Selected code:\n```\n{selected_text}\n```\n\nUser question: {user_text}"
        else:
            ai_message = user_text

        # Send to AI
        self._send_to_ai(ai_message)

    @work(exclusive=True)
    async def _send_to_ai(self, user_text: str):
        """Send message to AI and get response."""
        self._update_typing_indicator("AI is thinking...")

        # Create placeholder for AI response
        self.current_ai_message = self._add_message("...", role="ai")

        try:
            # Don't use streaming for now - get full response
            response = await self.ai_chat.send_message(user_text, on_chunk=None)
            self._update_ai_message(response)
        except Exception as e:
            logging.error(f"AI error: {e}")
            self._update_ai_message(f"Error: {str(e)}")
        finally:
            self._update_typing_indicator("")
            self.current_ai_message = None

    def _update_ai_message(self, content: str):
        """Update the current AI message."""
        if self.current_ai_message:
            self.current_ai_message.update(content)
            # Scroll to bottom
            chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
            chat_scroll.scroll_end(animate=False)

    def _clear_chat(self):
        """Clear chat history."""
        chat_scroll = self.query_one("#chat-scroll", VerticalScroll)
        for child in list(chat_scroll.children):
            child.remove()

        if self.ai_chat:
            self.ai_chat.clear_history()

        self._add_message("Chat cleared. How can I help?", role="ai")

    def ask_for_edit(self, instruction: str):
        """Ask AI to edit the current file based on instruction."""
        if not self.ai_chat or not self.ai_chat.is_available():
            self._add_message("AI not available. Use 'Set API Key' command.", role="system")
            return

        # Get current file content
        if not self.workspace:
            self._add_message("No workspace available.", role="system")
            return

        try:
            editor = self.workspace.tab_manager.get_active_editor()
            if not editor or not hasattr(editor, 'code_area') or not editor.code_area:
                self._add_message("No active editor.", role="system")
                return

            original_code = editor.code_area.text
            file_path = editor.file_path or "(untitled)"
        except Exception as e:
            logging.error(f"Error getting editor content: {e}")
            self._add_message(f"Error: {e}", role="system")
            return

        # Add user message to chat
        self._add_message(f"[Edit request] {instruction}", role="user")

        # Send to AI
        self._send_edit_request(instruction, original_code, file_path)

    @work(exclusive=True)
    async def _send_edit_request(self, instruction: str, original_code: str, file_path: str):
        """Send edit request to AI and show diff overlay on response."""
        self._update_typing_indicator("AI is editing...")

        # Create placeholder for AI response
        self.current_ai_message = self._add_message("Generating changes...", role="ai")

        try:
            # Build the prompt for code editing
            prompt = f"""Edit the following code according to this instruction: {instruction}

File: {file_path}

```
{original_code}
```

IMPORTANT: Return ONLY the complete modified code, nothing else. No explanations, no markdown code blocks, just the raw code."""

            response = await self.ai_chat.send_message(prompt, on_chunk=None)

            # Clean up the response - remove markdown code blocks if present
            new_code = self._extract_code_from_response(response)

            self._update_ai_message("Changes generated. Review the diff.")

            # Show diff overlay
            diff_overlay = DiffOverlay(original_code, new_code)
            self.app.mount(diff_overlay)

        except Exception as e:
            logging.error(f"AI edit error: {e}")
            self._update_ai_message(f"Error: {str(e)}")
        finally:
            self._update_typing_indicator("")
            self.current_ai_message = None

    def _extract_code_from_response(self, response: str) -> str:
        """Extract code from AI response, removing markdown if present."""
        response = response.strip()

        # Check if response is wrapped in markdown code blocks
        if response.startswith("```"):
            lines = response.split("\n")
            # Remove first line (```language)
            lines = lines[1:]
            # Remove last line if it's ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            return "\n".join(lines)

        return response
