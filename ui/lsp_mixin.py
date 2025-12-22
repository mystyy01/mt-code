"""LSP (Language Server Protocol) mixin for CodeEditor.

This module contains all LSP-related functionality including:
- Server initialization and lifecycle
- Completion requests and display
- Document synchronization (didOpen, didChange)
"""

import asyncio
import logging
import re
from pathlib import Path

from lsp.pyright import PyrightServer
from lsp.completion_filter import CompletionFilter
from ui.completions_overlay import CompletionsOverlay
from core.paths import LOG_FILE_STR

logging.basicConfig(
    filename=LOG_FILE_STR,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


class LSPMixin:
    """Mixin class providing LSP functionality to CodeEditor."""

    def _init_lsp_state(self):
        """Initialize LSP-related state variables. Call from __init__."""
        self.lsp = None
        self._completion_task: asyncio.Task | None = None
        self._completion_delay = 0.3
        self._lsp_initialized = False
        self._completions_overlay = None
        self._last_completion_cursor = None
        self._current_completions = []

    def _get_project_root(self) -> Path:
        """Get the project root directory for LSP initialization."""
        # Try to get project root from workspace
        try:
            from workspace.workspace import Workspace
            workspace = self.app.query_one(Workspace)
            if workspace and workspace.project_root:
                return Path(workspace.project_root).resolve()
        except Exception:
            pass

        # Fallback: look for common project markers
        file_dir = Path(self.file_path).resolve().parent
        for parent in [file_dir] + list(file_dir.parents):
            markers = ['.git', 'pyproject.toml', 'setup.py', 'setup.cfg', 'pyrightconfig.json']
            if any((parent / marker).exists() for marker in markers):
                return parent

        # Last fallback: file's parent directory
        return file_dir

    def _get_python_interpreter(self) -> str | None:
        """Get the configured Python interpreter path."""
        try:
            from core.python_config import get_python_config
            python_config = get_python_config()
            project_root = self._get_project_root()

            # First try the effective interpreter (handles auto-detection)
            interpreter = python_config.get_effective_interpreter(str(project_root))

            # If we got python3, try to find venv manually
            if interpreter == "python3":
                # Check for venv in project root
                for venv_name in ("venv", ".venv", "env", ".env"):
                    venv_python = project_root / venv_name / "bin" / "python"
                    if venv_python.exists():
                        interpreter = str(venv_python)
                        logging.info(f"Found venv Python at: {interpreter}")
                        break

            # Handle relative paths by resolving against project root
            if interpreter and not Path(interpreter).is_absolute():
                resolved = project_root / interpreter
                if resolved.exists():
                    interpreter = str(resolved)
                    logging.info(f"Resolved relative interpreter path to: {interpreter}")

            if interpreter and interpreter != "python3" and Path(interpreter).exists():
                return interpreter

        except Exception as e:
            logging.warning(f"Could not get Python interpreter: {e}")
        return None

    async def _init_lsp(self):
        """Initialize LSP server for Python files. Call from on_mount."""
        if self.language == "python" and self.file_path:
            logging.info(f"Initializing LSP for {self.file_path}")
            try:
                project_root = self._get_project_root()
                logging.info(f"Using project root for LSP: {project_root}")

                # Get Python interpreter for pyright
                python_path = self._get_python_interpreter()
                logging.info(f"Using Python interpreter for LSP: {python_path}")

                self.lsp = PyrightServer(project_root)
                await self.lsp.start()

                # Build initialization options with Python path if available
                init_options = {}
                if python_path:
                    init_options["python"] = {
                        "pythonPath": python_path
                    }

                init_response = await self.lsp.send_request(
                    "initialize",
                    {
                        "processId": None,
                        "rootUri": project_root.as_uri(),
                        "initializationOptions": init_options,
                        "capabilities": {
                            "textDocument": {
                                "completion": {
                                    "completionItem": {
                                        "snippetSupport": True
                                    }
                                },
                                "definition": {
                                    "linkSupport": True
                                },
                                "hover": {},
                                "signatureHelp": {}
                            }
                        }
                    }
                )
                logging.info(f"LSP initialized: {init_response}")

                await self.lsp.send_notification("initialized", {})
                self._lsp_initialized = True

                # Send Python configuration to pyright
                if python_path:
                    await self._send_python_config(python_path)

                await self._lsp_did_open()

                # Warmup: Send a completion request to trigger pyright to analyze the file
                # This ensures definition lookups work immediately after initialization
                await self._lsp_warmup()
            except Exception as e:
                logging.error(f"Failed to initialize LSP: {e}", exc_info=True)
                self.lsp = None
                self._lsp_initialized = False

    async def _send_python_config(self, python_path: str):
        """Send Python configuration to pyright via workspace/didChangeConfiguration."""
        if not self.lsp or not self._lsp_initialized:
            return

        logging.info(f"Sending Python config to pyright: {python_path}")
        try:
            # Pyright accepts pythonPath in settings
            # Also try to find venv path for better package resolution
            venv_path = None
            venv_name = None
            python_path_obj = Path(python_path).resolve()

            # Check if this is a venv Python
            venv_names = ("venv", ".venv", "env", ".env")
            for parent in python_path_obj.parents:
                if parent.name in venv_names:
                    venv_name = parent.name
                    venv_path = str(parent.parent)
                    logging.info(f"Detected venv: name={venv_name}, path={venv_path}")
                    break

            settings = {
                "python": {
                    "pythonPath": python_path,
                    "analysis": {
                        "autoSearchPaths": True,
                        "useLibraryCodeForTypes": True,
                        "diagnosticMode": "openFilesOnly"
                    }
                }
            }

            # Pyright needs both venvPath (parent dir) and venv (folder name)
            if venv_path and venv_name:
                settings["python"]["venvPath"] = venv_path
                settings["python"]["venv"] = venv_name
                logging.info(f"Set venvPath={venv_path}, venv={venv_name}")

            await self.lsp.send_notification(
                "workspace/didChangeConfiguration",
                {"settings": settings}
            )
            logging.info("Python config sent to pyright")
        except Exception as e:
            logging.warning(f"Failed to send Python config: {e}")

    async def _lsp_did_open(self):
        """Send didOpen notification to LSP server."""
        if self.lsp and self.file_path and self._lsp_initialized:
            logging.info(f"Sending didOpen for {self.file_path}")
            try:
                await self.lsp.send_notification(
                    "textDocument/didOpen",
                    {
                        "textDocument": {
                            "uri": Path(self.file_path).resolve().as_uri(),
                            "languageId": self.language,
                            "version": 1,
                            "text": self.text
                        }
                    }
                )
            except Exception as e:
                logging.error(f"Failed to send didOpen: {e}", exc_info=True)

    async def _lsp_warmup(self):
        """Send a warmup request to ensure pyright has analyzed the file.

        This triggers pyright's file analysis so that definition lookups
        work immediately without needing a completion request first.
        """
        if not self.lsp or not self.file_path or not self._lsp_initialized:
            return

        logging.info("Sending LSP warmup request")
        try:
            # Give pyright time to start analyzing after didOpen
            # This delay matches the completion debounce delay
            await asyncio.sleep(0.3)

            # Send a completion request to trigger/wait for analysis
            await self.lsp.send_request(
                "textDocument/completion",
                {
                    "textDocument": {"uri": Path(self.file_path).resolve().as_uri()},
                    "position": {"line": 0, "character": 0}
                }
            )
            logging.info("LSP warmup complete")
        except Exception as e:
            logging.warning(f"LSP warmup failed (non-critical): {e}")

    async def _lsp_did_change(self):
        """Send didChange notification to LSP server."""
        if self.lsp and self.file_path and self._lsp_initialized:
            logging.info("Text changed, notifying LSP")
            try:
                await self.lsp.send_notification(
                    "textDocument/didChange",
                    {
                        "textDocument": {
                            "uri": Path(self.file_path).resolve().as_uri(),
                            "version": 1
                        },
                        "contentChanges": [{"text": self.text}]
                    }
                )
            except Exception as e:
                logging.error(f"Failed to send didChange: {e}", exc_info=True)

    async def _debounced_completions(self):
        """Debounce completion requests to avoid overwhelming the LSP server."""
        try:
            await asyncio.sleep(self._completion_delay)
            await self.show_completions()
        except asyncio.CancelledError:
            pass

    async def request_completions(self):
        """Request completions from LSP server at current cursor position."""
        if not self.lsp or not self.file_path or not self._lsp_initialized:
            logging.info(
                f"Cannot request completions: lsp={bool(self.lsp)}, "
                f"file={bool(self.file_path)}, init={self._lsp_initialized}"
            )
            return []

        line, col = self.cursor_location
        logging.info(f"Requesting completions at line={line}, col={col}")

        try:
            resp = await self.lsp.send_request(
                "textDocument/completion",
                {
                    "textDocument": {"uri": Path(self.file_path).resolve().as_uri()},
                    "position": {"line": line, "character": col}
                }
            )
            logging.info(f"Completion response: {resp}")

            result = resp.get("result", [])
            if isinstance(result, dict) and "items" in result:
                return result["items"]
            return result if isinstance(result, list) else []
        except Exception as e:
            logging.error(f"Error requesting completions: {e}", exc_info=True)
            return []

    def _get_cursor_screen_position(self):
        """Calculate the screen position (x, y) of the cursor."""
        try:
            region = self.region
            cursor_line, cursor_col = self.cursor_location
            scroll_y = self.scroll_offset.y
            scroll_x = self.scroll_offset.x
            line_number_width = len(str(self.document.line_count)) + 2

            visible_line = cursor_line - scroll_y
            visible_col = cursor_col - scroll_x + line_number_width

            screen_x = region.x + visible_col
            screen_y = region.y + visible_line

            logging.info(f"Cursor screen position: x={screen_x}, y={screen_y}")
            return (screen_x, screen_y)
        except Exception as e:
            logging.error(f"Error calculating cursor position: {e}", exc_info=True)
            return None

    async def show_completions(self):
        """Show completion suggestions in an overlay near the cursor."""
        raw_items = await self.request_completions()
        logging.info(f"Got {len(raw_items) if raw_items else 0} raw completion items")

        if not raw_items:
            self._close_completions_overlay()
            return

        # Get text before cursor for context
        line, col = self.cursor_location
        current_line = str(self.get_line(line))
        text_before_cursor = current_line[:col]

        # Filter and sort completions based on relevance
        items = CompletionFilter.filter_and_sort(raw_items, text_before_cursor)

        if not items:
            logging.info("No relevant completions after filtering")
            self._close_completions_overlay()
            return

        # Log filtered items
        for i, item in enumerate(items[:5]):
            logging.info(f"Filtered completion {i}: {item.get('label', '')}")

        if self._completions_overlay:
            self._completions_overlay.remove()

        self._current_completions = items[:5]
        self._last_completion_cursor = self.cursor_location

        cursor_pos = self._get_cursor_screen_position()

        self._completions_overlay = CompletionsOverlay(items, id="completions_overlay")

        screen = self.screen
        await screen.mount(self._completions_overlay)

        if cursor_pos:
            x, y = cursor_pos
            self._completions_overlay.styles.offset = (x, max(0, y + 2))
            logging.info(f"Positioned overlay at x={x}, y={y + 2}")

        labels = [item.get("label", "") for item in items[:5]]
        logging.info(f"Showing completions: {labels}")

    def _close_completions_overlay(self):
        """Close the completions overlay if open."""
        if self._completions_overlay:
            self._completions_overlay.remove()
            self._completions_overlay = None
            self._last_completion_cursor = None
            self._current_completions = []

    def _handle_tab_completion(self):
        """Handle tab key press for completion insertion. Returns True if handled."""
        if self._completions_overlay and self._current_completions:
            # Get the highlighted index from overlay, default to 0
            highlighted_index = 0
            if hasattr(self._completions_overlay, 'completions_list'):
                highlighted = self._completions_overlay.completions_list.highlighted
                if highlighted is not None:
                    highlighted_index = highlighted

            completion = self._current_completions[highlighted_index]
            label = completion.get("label", "")
            insert_text = completion.get("insertText", label)

            # Log the full completion item to understand auto-import structure
            logging.info(f"Full completion item: {completion}")

            line, col = self.cursor_location
            current_line = str(self.get_line(line))
            text_before_cursor = current_line[:col]

            # Use regex to find partial word - handles brackets, dots, etc.
            match = re.search(r'(\w+)$', text_before_cursor)
            if match:
                partial = match.group(1)
                # Delete the partial word first, then insert full completion
                for _ in range(len(partial)):
                    self.action_delete_left()
                self.insert(insert_text)
                logging.info(
                    f"Tab completion: deleted '{partial}', inserted '{insert_text}'"
                )
            else:
                self.insert(insert_text)
                logging.info(f"Tab completion: inserted '{insert_text}'")

            # Handle auto-imports
            self._handle_auto_import(completion)

            self._close_completions_overlay()
            return True
        return False

    def _handle_auto_import(self, completion):
        """Handle auto-import by adding import statement at the top of the file."""
        label = completion.get("label", "")
        label_details = completion.get("labelDetails", {})
        description = label_details.get("description", "") if label_details else ""

        # Check if this is an auto-import completion
        is_auto_import = (
            label.endswith("- Auto-import") or
            "Auto-import" in description or
            completion.get("additionalTextEdits")
        )

        if not is_auto_import:
            return

        logging.info(f"Handling auto-import for: {label}")

        # Check for additionalTextEdits (standard LSP way)
        additional_edits = completion.get("additionalTextEdits", [])
        if additional_edits:
            logging.info(f"Additional text edits: {additional_edits}")
            for edit in additional_edits:
                self._apply_text_edit(edit)
            return

        # Fallback: parse the description to construct import statement
        # Description is typically like "(from module_name)"
        if description and description.startswith("(") and description.endswith(")"):
            # Extract module path, e.g., "(from os.path)" -> "os.path"
            import_source = description[1:-1]  # Remove parentheses
            if import_source.startswith("from "):
                module = import_source[5:]  # Remove "from "
                # Get the actual symbol name (remove "- Auto-import" suffix if present)
                symbol = label.replace(" - Auto-import", "").strip()
                import_statement = f"from {module} import {symbol}\n"
                self._add_import_to_file(import_statement)

    def _apply_text_edit(self, edit):
        """Apply a single LSP text edit."""
        try:
            range_info = edit.get("range", {})
            start = range_info.get("start", {})
            end = range_info.get("end", {})
            new_text = edit.get("newText", "")

            start_loc = (start.get("line", 0), start.get("character", 0))
            end_loc = (end.get("line", 0), end.get("character", 0))

            logging.info(f"Applying text edit: {start_loc} -> {end_loc}, text: {repr(new_text)}")
            self.replace(new_text, start=start_loc, end=end_loc)
        except Exception as e:
            logging.error(f"Failed to apply text edit: {e}", exc_info=True)

    def _add_import_to_file(self, import_statement):
        """Add an import statement at the top of the file (after existing imports)."""
        try:
            # Find the best location to insert the import
            lines = self.text.split("\n")
            insert_line = 0

            # Skip shebang, docstrings, and find the import section
            in_docstring = False
            docstring_char = None

            for i, line in enumerate(lines):
                stripped = line.strip()

                # Handle docstrings
                if not in_docstring:
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        docstring_char = stripped[:3]
                        if stripped.count(docstring_char) >= 2:
                            # Single line docstring
                            continue
                        in_docstring = True
                        continue
                else:
                    if docstring_char in stripped:
                        in_docstring = False
                    continue

                # Skip comments and empty lines at the top
                if stripped.startswith("#") or stripped == "":
                    insert_line = i + 1
                    continue

                # Track import lines
                if stripped.startswith("import ") or stripped.startswith("from "):
                    insert_line = i + 1
                    continue

                # Stop at first non-import code
                break

            # Insert the import
            logging.info(f"Inserting import at line {insert_line}: {repr(import_statement)}")
            self.replace(import_statement, start=(insert_line, 0), end=(insert_line, 0))
        except Exception as e:
            logging.error(f"Failed to add import: {e}", exc_info=True)

    def _check_cursor_moved_from_completion(self):
        """Check if cursor moved away from completion position and close if so."""
        if self._completions_overlay and self._last_completion_cursor:
            current_cursor = self.cursor_location
            if (current_cursor[0] != self._last_completion_cursor[0] or
                    abs(current_cursor[1] - self._last_completion_cursor[1]) > 10):
                logging.info("Cursor moved away, closing completions")
                self._close_completions_overlay()
                return True
        return False

    def _disable_lsp(self):
        """Disable LSP (e.g., when changing to non-Python language)."""
        self.lsp = None
        self._lsp_initialized = False

    # === Go to Definition Methods ===

    def _post_to_workspace(self, message):
        """Post message directly to workspace to ensure it's received."""
        from workspace.workspace import Workspace
        try:
            logging.info(f"Attempting to post {type(message).__name__} to workspace")
            workspace = self.app.query_one(Workspace)
            logging.info(f"Found workspace: {workspace}")
            workspace.post_message(message)
            logging.info(f"Successfully posted {type(message).__name__} to workspace")
        except Exception as e:
            logging.error(f"Failed to post message to workspace: {e}", exc_info=True)

    def _click_to_document_position(self, event) -> tuple[int, int] | None:
        """Convert click screen coordinates to document (line, col) position."""
        logging.info(f"_click_to_document_position called with event x={event.x}, y={event.y}")
        try:
            scroll_y = self.scroll_offset.y
            scroll_x = self.scroll_offset.x
            line_number_width = len(str(self.document.line_count)) + 2
            logging.info(f"Scroll offset: x={scroll_x}, y={scroll_y}, line_number_width={line_number_width}")

            # event.x and event.y are relative to the widget
            doc_line = int(event.y + scroll_y)
            doc_col = int(event.x - line_number_width + scroll_x)
            logging.info(f"Calculated doc_line={doc_line}, doc_col={doc_col}")

            # Validate bounds
            if doc_line < 0 or doc_line >= self.document.line_count:
                logging.warning(f"doc_line {doc_line} out of bounds (0-{self.document.line_count-1})")
                return None
            if doc_col < 0:
                logging.info(f"doc_col {doc_col} was negative, clamping to 0")
                doc_col = 0

            # Clamp column to line length
            line_text = str(self.get_line(doc_line))
            original_col = doc_col
            doc_col = min(doc_col, len(line_text))
            if original_col != doc_col:
                logging.info(f"Clamped doc_col from {original_col} to {doc_col} (line length: {len(line_text)})")

            logging.info(f"Final document position: ({doc_line}, {doc_col}), line text: '{line_text[:50]}...'")
            return (doc_line, doc_col)
        except Exception as e:
            logging.error(f"Error converting click to position: {e}", exc_info=True)
            return None

    async def _goto_definition(self, position: tuple[int, int]):
        """Request definition location from LSP and navigate to it."""
        logging.info(f"_goto_definition called with position={position}")
        logging.info(f"LSP state: lsp={bool(self.lsp)}, file_path={self.file_path}, initialized={self._lsp_initialized}")

        if not self.lsp or not self.file_path or not self._lsp_initialized:
            logging.warning("LSP not available for goto definition - aborting")
            return

        line, col = position
        uri = Path(self.file_path).resolve().as_uri()
        logging.info(f"Sending textDocument/definition request: uri={uri}, line={line}, col={col}")

        try:
            resp = await self.lsp.send_request(
                "textDocument/definition",
                {
                    "textDocument": {"uri": uri},
                    "position": {"line": line, "character": col}
                }
            )
            logging.info(f"LSP response received: {resp}")

            result = resp.get("result")
            if not result:
                logging.info("No definition found in LSP response (result is empty)")
                return

            logging.info(f"Raw result from LSP: {result}")

            # Normalize result to list of locations
            locations = self._normalize_definition_result(result)
            logging.info(f"Normalized locations: {locations}")

            if not locations:
                logging.info("No locations after normalization")
                return

            logging.info(f"Got {len(locations)} definition location(s)")

            if len(locations) == 1:
                logging.info(f"Single location, navigating directly to: {locations[0]}")
                await self._navigate_to_location(locations[0])
            else:
                logging.info(f"Multiple locations ({len(locations)}), showing overlay")
                await self._show_references_overlay(locations)

        except Exception as e:
            logging.error(f"Error requesting definition: {e}", exc_info=True)

    def _normalize_definition_result(self, result) -> list[dict]:
        """Normalize definition result to list of Location objects."""
        if isinstance(result, dict):
            # Single Location or LocationLink
            if "targetUri" in result:
                # LocationLink format
                return [{
                    "uri": result["targetUri"],
                    "range": result.get("targetSelectionRange", result.get("targetRange", {}))
                }]
            else:
                # Location format
                return [result]
        elif isinstance(result, list):
            locations = []
            for item in result:
                if "targetUri" in item:
                    locations.append({
                        "uri": item["targetUri"],
                        "range": item.get("targetSelectionRange", item.get("targetRange", {}))
                    })
                else:
                    locations.append(item)
            return locations
        return []

    async def _navigate_to_location(self, location: dict):
        """Navigate to a location, opening file if needed."""
        logging.info(f"_navigate_to_location called with location={location}")
        from commands.messages import GotoFileLocation

        uri = location.get("uri", "")
        range_info = location.get("range", {})
        start = range_info.get("start", {})
        target_line = start.get("line", 0)
        target_col = start.get("character", 0)

        logging.info(f"Parsed location: uri={uri}, target_line={target_line}, target_col={target_col}")

        # Convert file:// URI to path
        if uri.startswith("file://"):
            file_path = uri[7:]
            logging.info(f"Converted file:// URI to path: {file_path}")
        else:
            file_path = uri
            logging.info(f"URI was not file://, using as-is: {file_path}")

        current_file = str(Path(self.file_path).resolve())
        target_file = str(Path(file_path).resolve())

        logging.info(f"Current file: {current_file}")
        logging.info(f"Target file: {target_file}")

        if current_file == target_file:
            # Same file - just move cursor
            logging.info(f"Same file - moving cursor to ({target_line}, {target_col})")
            self.move_cursor((target_line, target_col))
            self.scroll_cursor_visible()
            logging.info("Cursor moved and scrolled into view")
        else:
            # Different file - post message directly to workspace
            logging.info(f"Different file - posting GotoFileLocation to workspace")
            self._post_to_workspace(GotoFileLocation(target_file, target_line, target_col))
            logging.info("GotoFileLocation message posted to workspace")

    async def _show_references_overlay(self, locations: list[dict]):
        """Show overlay for selecting from multiple definition locations."""
        from ui.references_overlay import ReferencesOverlay

        overlay = ReferencesOverlay(locations, id="references_overlay")
        await self.screen.mount(overlay)
