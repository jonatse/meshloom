"""Command handlers for the Meshloom API."""

import os
from typing import Any, Dict, Optional

from ..core.config import Config


class CommandHandler:
    """Handles API commands for Meshloom control."""

    def __init__(
        self,
        config: Config,
        network_service: Optional[Any] = None,
        sync_service: Optional[Any] = None,
        container_service: Optional[Any] = None,
        app_registry: Optional[Any] = None,
        bridge_manager: Optional[Any] = None,
    ) -> None:
        self._config = config
        self._network = network_service
        self._sync = sync_service
        self._container = container_service
        self._app_registry = app_registry
        self._bridge_manager = bridge_manager

    def set_services(
        self,
        network_service: Optional[Any] = None,
        sync_service: Optional[Any] = None,
        container_service: Optional[Any] = None,
        app_registry: Optional[Any] = None,
        bridge_manager: Optional[Any] = None,
    ) -> None:
        """Update service references after initialization."""
        self._network = network_service
        self._sync = sync_service
        self._container = container_service
        self._app_registry = app_registry
        self._bridge_manager = bridge_manager

    def handle(self, command: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Route command to appropriate handler."""
        if command == "peers":
            return self._peers(args)
        elif command == "status":
            return self._status(args)
        elif command == "execute":
            return self._execute(args)
        elif command == "apps":
            return self._apps(args)
        elif command.startswith("app "):
            return self._app_command(command[4:], args)
        elif command.startswith("config "):
            return self._config_command(command[7:], args)
        elif command == "sync":
            return self._sync_trigger(args)
        elif command == "bridges":
            return self._bridges(args)
        else:
            return {
                "success": False,
                "data": None,
                "error": f"Unknown command: {command}"
            }

    def _peers(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get list of discovered peers."""
        try:
            if self._network is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "Network service not available"
                }
            
            peer_list = []
            for peer_id, peer in self._network.get_peers().items():
                peer_list.append({
                    "id": peer_id,
                    "name": peer.name if hasattr(peer, 'name') else peer_id[:8],
                    "last_seen": peer.last_seen if hasattr(peer, 'last_seen') else None,
                })
            
            return {
                "success": True,
                "data": {"peers": peer_list, "count": len(peer_list)},
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _status(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Get system status."""
        try:
            status: Dict[str, Any] = {
                "network": self._get_network_status(),
                "sync": self._get_sync_status(),
                "container": self._get_container_status(),
                "apps": self._get_apps_status(),
            }
            
            return {
                "success": True,
                "data": status,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _get_network_status(self) -> Dict[str, Any]:
        """Get network subsystem status."""
        if self._network is None:
            return {"available": False, "error": "Network service not initialized"}
        
        try:
            return {
                "available": True,
                "peers": len(self._network.get_peers()),
                "identity_loaded": self._network.identity_loaded() if hasattr(self._network, 'identity_loaded') else True,
            }
        except Exception as e:
            return {"available": True, "error": str(e)}

    def _get_sync_status(self) -> Dict[str, Any]:
        """Get sync subsystem status."""
        if self._sync is None:
            return {"available": False, "error": "Sync service not initialized"}
        
        try:
            return {
                "available": True,
                "sync_dir": self._config.get("sync.sync_dir"),
                "auto_sync": self._config.get("sync.auto_sync"),
            }
        except Exception as e:
            return {"available": True, "error": str(e)}

    def _get_container_status(self) -> Dict[str, Any]:
        """Get container subsystem status."""
        if self._container is None:
            return {"available": False, "error": "Container service not initialized"}
        
        try:
            return {
                "available": True,
                "running": self._container.is_running() if hasattr(self._container, 'is_running') else False,
            }
        except Exception as e:
            return {"available": True, "error": str(e)}

    def _get_apps_status(self) -> Dict[str, Any]:
        """Get apps subsystem status."""
        if self._app_registry is None:
            return {"available": False, "error": "App registry not initialized"}
        
        try:
            return {
                "available": True,
                "app_count": len(self._app_registry.list_apps()) if hasattr(self._app_registry, 'list_apps') else 0,
            }
        except Exception as e:
            return {"available": True, "error": str(e)}

    def _execute(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a command in container."""
        try:
            if self._container is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "Container service not available"
                }
            
            command = args.get("command")
            if not command:
                return {
                    "success": False,
                    "data": None,
                    "error": "No command specified"
                }
            
            result = self._container.execute(command)
            
            return {
                "success": True,
                "data": {"output": result},
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _apps(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List installed apps."""
        try:
            if self._app_registry is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "App registry not available"
                }
            
            app_list = []
            for app in self._app_registry.list_apps():
                app_list.append({
                    "id": app.id if hasattr(app, 'id') else str(app),
                    "name": app.name if hasattr(app, 'name') else str(app),
                    "running": app.running if hasattr(app, 'running') else False,
                })
            
            return {
                "success": True,
                "data": {"apps": app_list, "count": len(app_list)},
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _app_command(self, subcommand: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle app start/stop commands."""
        try:
            if self._app_registry is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "App registry not available"
                }
            
            app_id = args.get("app_id")
            if not app_id:
                return {
                    "success": False,
                    "data": None,
                    "error": "No app_id specified"
                }
            
            if subcommand == "start":
                result = self._app_registry.start_app(app_id)
                return {
                    "success": result,
                    "data": {"message": f"App {app_id} started" if result else "Failed to start app"},
                    "error": None
                }
            elif subcommand == "stop":
                result = self._app_registry.stop_app(app_id)
                return {
                    "success": result,
                    "data": {"message": f"App {app_id} stopped" if result else "Failed to stop app"},
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown app subcommand: {subcommand}"
                }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _config_command(self, subcommand: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Handle config get/set commands."""
        try:
            if subcommand == "get":
                key = args.get("key")
                if not key:
                    return {
                        "success": False,
                        "data": None,
                        "error": "No key specified"
                    }
                
                value = self._config.get(key)
                return {
                    "success": True,
                    "data": {"key": key, "value": value},
                    "error": None
                }
            elif subcommand == "set":
                key = args.get("key")
                value = args.get("value")
                if key is None:
                    return {
                        "success": False,
                        "data": None,
                        "error": "No key specified"
                    }
                
                self._config.set(key, value)
                self._config.save()
                return {
                    "success": True,
                    "data": {"message": f"Config {key} set to {value}"},
                    "error": None
                }
            else:
                return {
                    "success": False,
                    "data": None,
                    "error": f"Unknown config subcommand: {subcommand}"
                }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _sync_trigger(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger sync."""
        try:
            if self._sync is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "Sync service not available"
                }
            
            self._sync.trigger_sync()
            
            return {
                "success": True,
                "data": {"message": "Sync triggered"},
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }

    def _bridges(self, args: Dict[str, Any]) -> Dict[str, Any]:
        """List bridge connections."""
        try:
            if self._bridge_manager is None:
                return {
                    "success": False,
                    "data": None,
                    "error": "Bridge manager not available"
                }
            
            bridge_list = []
            for bridge in self._bridge_manager.list_bridges():
                bridge_list.append({
                    "id": bridge.id if hasattr(bridge, 'id') else str(bridge),
                    "type": bridge.type if hasattr(bridge, 'type') else "unknown",
                    "connected": bridge.connected if hasattr(bridge, 'connected') else False,
                })
            
            return {
                "success": True,
                "data": {"bridges": bridge_list, "count": len(bridge_list)},
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "data": None,
                "error": str(e)
            }
