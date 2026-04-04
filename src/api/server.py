"""Async Unix socket server for Meshloom API."""

import asyncio
import json
import logging
import os
import stat
from typing import Any, Dict, Optional

from .commands import CommandHandler


logger = logging.getLogger(__name__)


class APIServer:
    """Async Unix socket API server for Meshloom control."""

    DEFAULT_SOCKET_PATH = os.path.expanduser("~/.local/run/meshloom/api.sock")

    def __init__(
        self,
        socket_path: Optional[str] = None,
        command_handler: Optional[CommandHandler] = None,
    ) -> None:
        self._socket_path = socket_path or self.DEFAULT_SOCKET_PATH
        self._command_handler = command_handler
        self._server: Optional[asyncio.Server] = None
        self._running = False

    def set_command_handler(self, handler: CommandHandler) -> None:
        """Set the command handler."""
        self._command_handler = handler

    async def start(self) -> None:
        """Start the API server."""
        if self._running:
            logger.warning("API server already running")
            return

        socket_dir = os.path.dirname(self._socket_path)
        os.makedirs(socket_dir, exist_ok=True)

        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self._socket_path,
        )

        os.chmod(self._socket_path, stat.S_IRUSR | stat.S_IWUSR)

        self._running = True
        logger.info(f"API server started on {self._socket_path}")

    async def stop(self) -> None:
        """Stop the API server."""
        if not self._running:
            return

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        if os.path.exists(self._socket_path):
            os.unlink(self._socket_path)

        self._running = False
        logger.info("API server stopped")

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Handle a client connection."""
        client_addr = writer.get_extra_info("peername")
        logger.debug(f"Client connected: {client_addr}")

        try:
            data = await reader.read(4096)
            if not data:
                return

            request = json.loads(data.decode("utf-8"))
            response = self._process_request(request)

            response_json = json.dumps(response)
            writer.write(response_json.encode("utf-8"))
            await writer.drain()

        except json.JSONDecodeError as e:
            error_response = {
                "success": False,
                "data": None,
                "error": f"Invalid JSON: {str(e)}"
            }
            writer.write(json.dumps(error_response).encode("utf-8"))
            await writer.drain()

        except Exception as e:
            logger.error(f"Error handling client: {e}")
            error_response = {
                "success": False,
                "data": None,
                "error": str(e)
            }
            writer.write(json.dumps(error_response).encode("utf-8"))
            await writer.drain()

        finally:
            writer.close()
            await writer.wait_closed()

    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an API request."""
        if not isinstance(request, dict):
            return {
                "success": False,
                "data": None,
                "error": "Request must be a JSON object"
            }

        command = request.get("command")
        if not command:
            return {
                "success": False,
                "data": None,
                "error": "No command specified"
            }

        args = request.get("args", {})

        if self._command_handler is None:
            return {
                "success": False,
                "data": None,
                "error": "Command handler not configured"
            }

        return self._command_handler.handle(command, args)

    @property
    def is_running(self) -> bool:
        """Check if server is running."""
        return self._running

    @property
    def socket_path(self) -> str:
        """Get the socket path."""
        return self._socket_path
