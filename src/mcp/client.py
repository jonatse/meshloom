"""Meshloom client for MCP server."""

import os
import sys
from typing import Any, Optional

vendor_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)


class MeshloomClient:
    """Wrapper for Meshloom API."""
    
    def __init__(self, meshloom_instance: Any = None):
        self._ml = meshloom_instance
        self._connected = False
    
    def _ensure_connected(self) -> None:
        """Lazy connection to Meshloom."""
        if not self._connected:
            self._connected = True
    
    def _get_meshloom(self) -> Any:
        """Get or initialize Meshloom instance."""
        self._ensure_connected()
        return self._ml
    
    def get_peers(self) -> list[dict]:
        """Get list of mesh peers."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_network') and ml._network is not None:
            try:
                return ml._network.get_peers() or []
            except Exception:
                pass
        return []
    
    def get_apps(self) -> list[dict]:
        """Get list of installed apps."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_app_registry') and ml._app_registry is not None:
            try:
                apps = []
                for entry in ml._app_registry.entries:
                    apps.append({
                        "name": entry.metadata.name,
                        "version": entry.metadata.version,
                        "status": "running" if entry.metadata.name in (ml._app_registry.started_apps or []) else "stopped"
                    })
                return apps
            except Exception:
                pass
        return []
    
    def get_app_list(self) -> list[dict]:
        """Get list of all registered apps."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_app_registry') and ml._app_registry is not None:
            try:
                return [
                    {
                        "name": entry.metadata.name,
                        "version": entry.metadata.version,
                        "description": entry.metadata.description,
                    }
                    for entry in ml._app_registry.entries
                ]
            except Exception:
                pass
        return []
    
    def get_config(self, key: str = None) -> Any:
        """Get configuration value(s)."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_config') and ml._config is not None:
            try:
                if key is None:
                    return ml._config._data.copy() if hasattr(ml._config, '_data') else {}
                return ml._config.get(key)
            except Exception:
                pass
        return None
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_config') and ml._config is not None:
            try:
                ml._config.set(key, value)
            except Exception:
                pass
    
    def trigger_sync(self, peer_ids: list[str] = None) -> dict:
        """Trigger sync with peers."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_sync_engine') and ml._sync_engine is not None:
            try:
                sync_id = ml._sync_engine.trigger_sync(peer_ids)
                return {"sync_id": sync_id, "status": "started", "peers_involved": len(peer_ids) if peer_ids else 0}
            except Exception:
                pass
        return {"sync_id": "unknown", "status": "unavailable", "peers_involved": 0}
    
    def get_sync_status(self, sync_id: str = None) -> dict:
        """Get sync status."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_sync_engine') and ml._sync_engine is not None:
            try:
                return ml._sync_engine.get_status(sync_id) or {"status": "idle"}
            except Exception:
                pass
        return {"status": "unavailable"}
    
    def install_app(self, name: str) -> dict:
        """Install an app."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_app_registry') and ml._app_registry is not None:
            try:
                ml._app_registry.install(name)
                return {"name": name, "status": "installed"}
            except Exception as e:
                return {"name": name, "status": "error", "error": str(e)}
        return {"name": name, "status": "unavailable"}
    
    def start_app(self, name: str) -> dict:
        """Start an app."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_app_registry') and ml._app_registry is not None:
            try:
                ml._app_registry.start(name)
                return {"name": name, "status": "running"}
            except Exception as e:
                return {"name": name, "status": "error", "error": str(e)}
        return {"name": name, "status": "unavailable"}
    
    def stop_app(self, name: str) -> dict:
        """Stop an app."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_app_registry') and ml._app_registry is not None:
            try:
                ml._app_registry.stop(name)
                return {"name": name, "status": "stopped"}
            except Exception as e:
                return {"name": name, "status": "error", "error": str(e)}
        return {"name": name, "status": "unavailable"}
    
    def query(self, sql: str) -> list[dict]:
        """Execute database query."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_db_manager') and ml._db_manager is not None:
            try:
                return ml._db_manager.query(sql) or []
            except Exception:
                pass
        return []
    
    def get_nodes(self) -> list[dict]:
        """Get knowledge nodes."""
        return self.query("SELECT * FROM nodes LIMIT 100")
    
    def get_edges(self) -> list[dict]:
        """Get knowledge edges."""
        return self.query("SELECT * FROM edges LIMIT 100")
    
    def connect_peer(self, peer_id: str) -> dict:
        """Connect to a peer."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_network') and ml._network is not None:
            try:
                ml._network.connect_peer(peer_id)
                return {"peer_id": peer_id, "status": "connected"}
            except Exception as e:
                return {"peer_id": peer_id, "status": "error", "error": str(e)}
        return {"peer_id": peer_id, "status": "unavailable"}
    
    def get_status(self) -> dict:
        """Get system status."""
        ml = self._get_meshloom()
        if ml is not None:
            return {
                "running": getattr(ml, '_running', False),
                "uptime": getattr(ml, 'uptime', lambda: 0)(),
                "services": {
                    "network": ml._network is not None if hasattr(ml, '_network') else False,
                    "sync": ml._sync_engine is not None if hasattr(ml, '_sync_engine') else False,
                    "container": ml._container_manager is not None if hasattr(ml, '_container_manager') else False,
                    "apps": ml._app_registry is not None if hasattr(ml, '_app_registry') else False,
                    "bridges": ml._bridge_manager is not None if hasattr(ml, '_bridge_manager') else False,
                    "api": ml._api_server is not None if hasattr(ml, '_api_server') else False,
                }
            }
        return {"running": False, "uptime": 0, "services": {}}
    
    def get_bridges(self) -> list[dict]:
        """Get connected bridges."""
        ml = self._get_meshloom()
        if ml is not None and hasattr(ml, '_bridge_manager') and ml._bridge_manager is not None:
            try:
                bridges = []
                for bridge in ml._bridge_manager.bridges:
                    bridges.append({
                        "name": bridge.name,
                        "type": type(bridge).__name__,
                        "status": "connected" if bridge.connected else "disconnected"
                    })
                return bridges
            except Exception:
                pass
        return []
