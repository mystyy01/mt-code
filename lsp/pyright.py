import asyncio
import json
import subprocess
import sys
from pathlib import Path
import logging

logging.basicConfig(filename="editor_view.log", level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s")

class PyrightServer:
    def __init__(self, root_path: Path):
        self.root_path = root_path
        self.proc = None
        self._id = 1
        self.pending_responses = {}
        self._restart_count = 0
        self._max_restarts = 3
        self.last_diagnostics = None  # Store latest diagnostics
    
    async def start(self):
        logging.info("starting pyright server")
        self.proc = await asyncio.create_subprocess_exec(
            "pyright-langserver", "--stdio",
            stdin=subprocess.PIPE, 
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        asyncio.create_task(self._read_loop())
    
    async def restart(self):
        """Restart the LSP server."""
        if self._restart_count >= self._max_restarts:
            logging.error(f"Max restarts ({self._max_restarts}) reached, not restarting")
            return False
        
        self._restart_count += 1
        logging.warning(f"Restarting pyright server (attempt {self._restart_count}/{self._max_restarts})")
        
        # Clean up old process
        if self.proc:
            try:
                self.proc.kill()
                await self.proc.wait()
            except Exception as e:
                logging.error(f"Error killing process: {e}")
        
        # Clear pending responses and diagnostics
        self.pending_responses.clear()
        self.last_diagnostics = None
        
        # Start new process
        try:
            await self.start()
            logging.info("Server restarted successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to restart server: {e}")
            return False
    
    async def _read_loop(self):
        while True:
            try:
                # JSON-RPC uses headers like Content-Length
                headers = {}
                while True:
                    line = (await self.proc.stdout.readline()).decode().strip()
                    if not line:
                        break
                    if ":" not in line:
                        continue
                    key, value = line.split(":", 1)
                    headers[key.strip()] = value.strip()
                
                length = int(headers.get("Content-Length", 0))
                if length == 0:
                    continue
                    
                body_bytes = await self.proc.stdout.readexactly(length)
                body = json.loads(body_bytes.decode())
                await self._handle_message(body)
            except asyncio.InvalidStateError as e:
                logging.error(f"InvalidStateError in read loop: {e}")
                # Try to restart the server
                await self.restart()
                break
            except Exception as e:
                logging.error(f"Error in read loop: {e}", exc_info=True)
                # Try to restart on any error
                await self.restart()
                break
    
    async def _handle_message(self, message):
        try:
            if "id" in message and message["id"] in self.pending_responses:
                fut = self.pending_responses.pop(message["id"])
                # Check if future is not already done before setting result
                if not fut.done():
                    fut.set_result(message)
                else:
                    logging.warning(f"Future already done for message id {message['id']}")
            elif "method" in message:
                # Handle server notifications
                method = message.get('method', 'unknown')
                
                if method == 'textDocument/publishDiagnostics':
                    # This is a diagnostic notification
                    params = message.get('params', {})
                    uri = params.get('uri', '')
                    diagnostics = params.get('diagnostics', [])
                    logging.info(f"Received {len(diagnostics)} diagnostics for {uri}")
                    
                    # Store diagnostics for the editor to retrieve
                    self.last_diagnostics = {
                        'uri': uri,
                        'diagnostics': diagnostics
                    }
                    
                    # Log each diagnostic
                    for diag in diagnostics:
                        severity = diag.get('severity', 1)
                        message_text = diag.get('message', '')
                        range_data = diag.get('range', {})
                        start = range_data.get('start', {})
                        logging.info(
                            f"  Line {start.get('line', 0)}: [{severity}] {message_text}"
                        )
                else:
                    logging.debug(f"Notification from server: {method}")
        except asyncio.InvalidStateError as e:
            logging.error(f"InvalidStateError handling message: {e}")
            # Re-raise to trigger restart in read loop
            raise
        except Exception as e:
            logging.error(f"Error handling message: {e}", exc_info=True)
    
    async def send_request(self, method, params):
        if not self.proc or self.proc.returncode is not None:
            logging.error("Process not running, cannot send request")
            return {"error": "process not running"}
        
        logging.info(f"sending request: {method}")
        msg_id = self._id
        self._id += 1
        message = {"jsonrpc": "2.0", "id": msg_id, "method": method, "params": params}
        data = json.dumps(message)
        content_bytes = data.encode("utf-8")
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n".encode("utf-8")
        
        try:
            self.proc.stdin.write(header + content_bytes)
            await self.proc.stdin.drain()
        except Exception as e:
            logging.error(f"Error sending request: {e}")
            return {"error": str(e)}
        
        fut = asyncio.get_event_loop().create_future()
        self.pending_responses[msg_id] = fut
        
        try:
            # Add timeout to prevent hanging forever
            return await asyncio.wait_for(fut, timeout=10.0)
        except asyncio.TimeoutError:
            logging.error(f"Request {method} timed out")
            self.pending_responses.pop(msg_id, None)
            return {"error": "timeout"}
        except Exception as e:
            logging.error(f"Error waiting for response: {e}")
            self.pending_responses.pop(msg_id, None)
            return {"error": str(e)}
    
    async def send_notification(self, method, params):
        if not self.proc or self.proc.returncode is not None:
            logging.error("Process not running, cannot send notification")
            return
        
        logging.info(f"sending notification: {method}")
        message = {"jsonrpc": "2.0", "method": method, "params": params}
        data = json.dumps(message)
        content_bytes = data.encode("utf-8")
        header = f"Content-Length: {len(content_bytes)}\r\n\r\n".encode("utf-8")
        
        try:
            self.proc.stdin.write(header + content_bytes)
            await self.proc.stdin.drain()
        except Exception as e:
            logging.error(f"Error sending notification: {e}")