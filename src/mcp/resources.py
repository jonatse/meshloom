"""MCP Resources for Meshloom."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def register_resources(server, client) -> None:
    """Register all MCP resources."""
    
    @server.list_resources()
    def list_resources() -> list[Any]:
        return [
            Resource(
                uri="meshloom://peers",
                name="Peers",
                description="List of connected mesh peers",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://apps",
                name="Apps",
                description="Installed applications",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://config",
                name="Configuration",
                description="Current Meshloom configuration",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://status",
                name="Status",
                description="System status",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://database/nodes",
                name="Nodes",
                description="Knowledge graph nodes",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://database/edges",
                name="Edges",
                description="Knowledge graph edges",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://sync/status",
                name="SyncStatus",
                description="Current sync state",
                mimeType="application/json"
            ),
            Resource(
                uri="meshloom://network/bridges",
                name="Bridges",
                description="Connected bridges",
                mimeType="application/json"
            ),
        ]
    
    @server.read_resource()
    def read_resource(uri: str) -> bytes:
        if uri == "meshloom://peers":
            return json.dumps(client.get_peers()).encode()
        elif uri == "meshloom://apps":
            return json.dumps(client.get_app_list()).encode()
        elif uri == "meshloom://config":
            return json.dumps(client.get_config()).encode()
        elif uri == "meshloom://status":
            return json.dumps(client.get_status()).encode()
        elif uri == "meshloom://database/nodes":
            return json.dumps(client.get_nodes()).encode()
        elif uri == "meshloom://database/edges":
            return json.dumps(client.get_edges()).encode()
        elif uri == "meshloom://sync/status":
            return json.dumps(client.get_sync_status()).encode()
        elif uri == "meshloom://network/bridges":
            return json.dumps(client.get_bridges()).encode()
        raise ValueError(f"Unknown resource: {uri}")


try:
    from mcp.types import Resource
except ImportError:
    class Resource:
        def __init__(self, uri: str, name: str, description: str, mimeType: str = "application/json"):
            self.uri = uri
            self.name = name
            self.description = description
            self.mimeType = mimeType
