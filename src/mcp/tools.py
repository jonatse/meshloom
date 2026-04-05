"""MCP Tools for Meshloom."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SyncTriggerInput:
    def __init__(self, peer_ids: list[str] = None):
        self.peer_ids = peer_ids


class AppInstallInput:
    def __init__(self, name: str):
        self.name = name


class DbQueryInput:
    def __init__(self, sql: str):
        self.sql = sql


class ConfigGetInput:
    def __init__(self, key: str = None):
        self.key = key


class ConfigSetInput:
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value


class BridgeConnectInput:
    def __init__(self, bridge_type: str, config: dict = None):
        self.bridge_type = bridge_type
        self.config = config or {}


def register_tools(server, client) -> None:
    """Register all MCP tools."""
    
    @server.tool(name="sync_trigger", description="Trigger file sync with specified peers or all peers")
    def sync_trigger(peer_ids: list[str] = None) -> str:
        result = client.trigger_sync(peer_ids)
        return f"Sync started with sync_id={result.get('sync_id', 'unknown')}, status={result.get('status', 'unknown')}, peers_involved={result.get('peers_involved', 0)}"
    
    @server.tool(name="sync_status", description="Get the status of a sync operation")
    def sync_status(sync_id: str = None) -> str:
        status = client.get_sync_status(sync_id)
        return str(status)
    
    @server.tool(name="app_install", description="Install an application from the app registry")
    def app_install(name: str) -> str:
        result = client.install_app(name)
        return f"App {name}: {result.get('status', 'unknown')}"
    
    @server.tool(name="app_start", description="Start an installed application")
    def app_start(name: str) -> str:
        result = client.start_app(name)
        return f"App {name}: {result.get('status', 'unknown')}"
    
    @server.tool(name="app_stop", description="Stop a running application")
    def app_stop(name: str) -> str:
        result = client.stop_app(name)
        return f"App {name}: {result.get('status', 'unknown')}"
    
    @server.tool(name="app_list", description="List all installed applications")
    def app_list() -> str:
        apps = client.get_apps()
        return str(apps)
    
    @server.tool(name="db_query", description="Execute a SQL query on the knowledge database")
    def db_query(sql: str) -> str:
        results = client.query(sql)
        return str(results)
    
    @server.tool(name="network_peers", description="List all known mesh peers")
    def network_peers() -> str:
        peers = client.get_peers()
        return str(peers)
    
    @server.tool(name="network_connect", description="Connect to a mesh peer")
    def network_connect(peer_id: str) -> str:
        result = client.connect_peer(peer_id)
        return f"Peer {peer_id}: {result.get('status', 'unknown')}"
    
    @server.tool(name="config_get", description="Get a configuration value")
    def config_get(key: str = None) -> str:
        value = client.get_config(key)
        return str(value)
    
    @server.tool(name="config_set", description="Set a configuration value")
    def config_set(key: str, value: str) -> str:
        client.set_config(key, value)
        return f"Config {key} set to {value}"
    
    @server.tool(name="bridge_connect", description="Connect a bridge")
    def bridge_connect(bridge_type: str, config: str = "{}") -> str:
        import json
        try:
            config_dict = json.loads(config)
        except:
            config_dict = {}
        result = {"bridge_type": bridge_type, "status": "unavailable", "config": config_dict}
        return f"Bridge {bridge_type}: {result.get('status', 'unknown')}"
    
    @server.tool(name="system_status", description="Get system status")
    def system_status() -> str:
        status = client.get_status()
        return str(status)
    
    @server.tool(name="list_bridges", description="List all connected bridges")
    def list_bridges() -> str:
        bridges = client.get_bridges()
        return str(bridges)
