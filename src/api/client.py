"""Client for connecting to Meshloom API via Unix socket."""

import json
import os
from typing import Any, Dict, Optional


class APIClient:
    """Client for the Meshloom Unix socket API."""

    DEFAULT_SOCKET_PATH = os.path.expanduser("~/.local/run/meshloom/api.sock")

    def __init__(self, socket_path: Optional[str] = None) -> None:
        self._socket_path = socket_path or self.DEFAULT_SOCKET_PATH

    def _send_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Send a request to the API and return the response."""
        import socket

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        
        try:
            sock.connect(self._socket_path)
            sock.sendall(json.dumps(request).encode("utf-8"))
            
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                try:
                    return json.loads(response_data.decode("utf-8"))
                except json.JSONDecodeError:
                    continue
            
            return {
                "success": False,
                "data": None,
                "error": "Invalid response from server"
            }
        
        except FileNotFoundError:
            return {
                "success": False,
                "data": None,
                "error": f"Socket not found: {self._socket_path}"
            }
        except ConnectionRefusedError:
            return {
                "success": False,
                "data": None,
                "error": "Connection refused - is Meshloom running?"
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
        finally:
            sock.close()

    def peers(self) -> Dict[str, Any]:
        """Get list of discovered peers."""
        return self._send_request({"command": "peers", "args": {}})

    def status(self) -> Dict[str, Any]:
        """Get system status."""
        return self._send_request({"command": "status", "args": {}})

    def execute(self, command: str) -> Dict[str, Any]:
        """Execute a command in container."""
        return self._send_request({"command": "execute", "args": {"command": command}})

    def apps(self) -> Dict[str, Any]:
        """List installed apps."""
        return self._send_request({"command": "apps", "args": {}})

    def app_start(self, app_id: str) -> Dict[str, Any]:
        """Start an app."""
        return self._send_request({"command": "app start", "args": {"app_id": app_id}})

    def app_stop(self, app_id: str) -> Dict[str, Any]:
        """Stop an app."""
        return self._send_request({"command": "app stop", "args": {"app_id": app_id}})

    def config_get(self, key: str) -> Dict[str, Any]:
        """Get config value."""
        return self._send_request({"command": "config get", "args": {"key": key}})

    def config_set(self, key: str, value: Any) -> Dict[str, Any]:
        """Set config value."""
        return self._send_request({"command": "config set", "args": {"key": key, "value": value}})

    def sync(self) -> Dict[str, Any]:
        """Trigger sync."""
        return self._send_request({"command": "sync", "args": {}})

    def bridges(self) -> Dict[str, Any]:
        """List bridge connections."""
        return self._send_request({"command": "bridges", "args": {}})

    def send(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send a custom command."""
        return self._send_request({"command": command, "args": args or {}})
