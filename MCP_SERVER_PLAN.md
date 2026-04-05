# Meshloom MCP Server Plan

This document provides a comprehensive technical plan for building a Model Context Protocol (MCP) server that exposes the Meshloom system to Kilo, an AI coding assistant.

---

## 1. MCP Overview

### What is MCP (Model Context Protocol)

MCP is an open protocol that enables AI models to interact with external tools, resources, and services in a standardized way. It defines:

- **Resources**: Data that AI can read (files, database records, API responses)
- **Tools**: Actions the AI can invoke (function calls with parameters)
- **Prompts**: Templated messages for common workflows

MCP uses JSON-RPC 2.0 for communication and typically runs over stdio or HTTP with SSE.

### Why Kilo Would Use It to Interact with Meshloom

Kilo is an AI coding assistant that benefits from context about the user's systems. Meshloom appears to be a personal knowledge management and sync system. By exposing Meshloom via MCP:

- **Context-awareness**: Kilo can query peer connections, sync status, installed apps
- **Action capability**: Kilo can trigger syncs, manage apps, modify config
- **Data access**: Kilo can read knowledge nodes, notes, relationships
- **Automation**: Common Meshloom tasks can be automated through natural language

### The Value Proposition

| Capability | Use Case |
|-------------|----------|
| Query peers | "Who am I connected to?" |
| Trigger sync | "Sync my notes with all peers" |
| Manage apps | "Start the markdown editor app" |
| Query database | "Show me all notes from yesterday" |
| Modify config | "Enable end-to-end encryption" |

---

## 2. Architecture

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Kilo     │────▶│  MCP Server │────▶│  Meshloom   │
│   (LLM)     │     │  (Python)   │     │  (Core)     │
└─────────────┘     └─────────────┘     └─────────────┘
       │                   │                   │
       │   JSON-RPC        │   Direct Import   │
       │   over stdio      │   or Unix Socket  │
       │                   │                   │
       ▼                   ▼                   ▼
  User's CLI         Subprocess          Meshloom DB
  or IDE             or Sidecar        + Network
```

### Communication Flow

1. **Kilo** sends a JSON-RPC request (e.g., `tools/call`)
2. **MCP Server** receives and parses the request
3. **MCP Server** calls into **Meshloom** via Python API or socket
4. **Meshloom** processes and returns results
5. **MCP Server** formats response and returns to **Kilo**

---

## 3. MCP Server Design

### Using the Official modelcontextprotocol/python-sdk

The Python SDK provides a base `Server` class and decorators for resources, tools, and prompts.

**Requirements**:
```
modelcontextprotocol>=0.1.0
pydantic>=2.0.0
```

**Server Pattern**:
```python
from mcp.server import Server
from mcp.types import Tool, Resource, Prompt
from mcp.server.stdio import stdio_server

app = Server("meshloom")

@app.tool()
def trigger_sync(peer_ids: list[str] | None = None) -> str:
    """Trigger file sync with specified peers or all peers."""
    ...
```

### Server Deployment Modes

| Mode | Description | Pros | Cons |
|------|-------------|------|------|
| **Subprocess** | Spawned by Kilo on demand | Isolation, simple | Higher latency, no shared state |
| **Sidecar** | Long-running alongside Meshloom | Fast calls, shared state | Coupled lifecycle |
| **Embedded** | Runs in Meshloom main process | Minimal overhead | Complex integration |

**Recommended**: Sidecar mode for production, subprocess for testing.

### Communication with Meshloom

**Option 1: Direct Python Import** (Recommended)
```python
from meshloom.core import Meshloom
from meshloom.sync import SyncEngine
from meshloom.db import Database

class MeshloomClient:
    def __init__(self):
        self.meshloom = Meshloom()
    
    def get_peers(self):
        return self.meshloom.network.peers.list()
```

**Option 2: Unix Socket API**
```python
import socket

class SocketMeshloomClient:
    def __init__(self, socket_path="/run/meshloom.sock"):
        self.socket_path = socket_path
    
    def call(self, method: str, params: dict) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        # Send JSON-RPC request, receive response
```

**Option 3: HTTP REST API** (if Meshloom exposes one)
```python
import requests

class HTTPMeshloomClient:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
    
    def get_peers(self):
        return requests.get(f"{self.base_url}/peers").json()
```

---

## 4. MCP Resources (Data Kilo Can Read)

Resources expose read-only data from Meshloom. Each resource has a URI and optional schema.

| URI | Description | Schema |
|-----|-------------|--------|
| `meshloom://peers` | List of discovered mesh peers | `Peer[]` |
| `meshloom://apps` | Installed apps and their state | `App[]` |
| `meshloom://config` | Current configuration | `Config` |
| `meshloom://status` | System status | `Status` |
| `meshloom://database/nodes` | Knowledge nodes | `Node[]` |
| `meshloom://database/edges` | Node relationships | `Edge[]` |
| `meshloom://sync/status` | Current sync state | `SyncStatus` |
| `meshloom://network/bridges` | Connected bridges | `Bridge[]` |

### Resource Definitions

```python
# src/mcp/resources.py
from mcp.types import Resource, ResourceTemplate
from mcp.server import Server

def register_resources(server: Server, client: MeshloomClient):
    
    @server.list_resources()
    def list_resources() -> list[Resource]:
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
        ]
    
    @server.read_resource()
    def read_resource(uri: str) -> bytes:
        if uri == "meshloom://peers":
            import json
            return json.dumps(client.get_peers()).encode()
        elif uri == "meshloom://apps":
            return json.dumps(client.get_apps()).encode()
        # ... handle other resources
        raise ValueError(f"Unknown resource: {uri}")
```

---

## 5. MCP Tools (Actions Kilo Can Trigger)

Tools are functions Kilo can call with parameters.

| Tool | Parameters | Return | Description |
|------|-------------|--------|--------------|
| `sync.trigger` | `peer_ids?: string[]` | `SyncResult` | Trigger file sync |
| `sync.status` | `sync_id?: string` | `SyncStatus` | Get sync status |
| `app.install` | `name: string` | `App` | Install an app |
| `app.start` | `name: string` | `App` | Start an app |
| `app.stop` | `name: string` | `App` | Stop an app |
| `app.list` | - | `App[]` | List installed apps |
| `db.query` | `sql: string` | `Row[]` | Execute SQL query |
| `db.nodes.create` | `content: string, metadata?: dict` | `Node` | Create a node |
| `db.nodes.search` | `query: string` | `Node[]` | Search nodes |
| `network.peers` | - | `Peer[]` | List peers |
| `network.connect` | `peer_id: string` | `Peer` | Connect to peer |
| `network.disconnect` | `peer_id: string` | void | Disconnect from peer |
| `config.get` | `key: string` | `any` | Get config value |
| `config.set` | `key: string, value: any` | void | Set config value |
| `bridge.connect` | `type: string, config: dict` | `Bridge` | Connect a bridge |
| `bridge.disconnect` | `bridge_id: string` | void | Disconnect a bridge |

### Tool Definitions

```python
# src/mcp/tools.py
from mcp.types import Tool, TextContent
from mcp.server import Server
from pydantic import BaseModel

class SyncTriggerInput(BaseModel):
    peer_ids: list[str] | None = None

class SyncTriggerResult(BaseModel):
    sync_id: str
    status: str
    peers_involved: int

class AppInstallInput(BaseModel):
    name: str

class AppInstallResult(BaseModel):
    name: str
    version: str
    status: str

class DbQueryInput(BaseModel):
    sql: str

class ConfigGetInput(BaseModel):
    key: str

class ConfigSetInput(BaseModel):
    key: str
    value: str

def register_tools(server: Server, client: MeshloomClient):
    
    @server.tool(
        name="sync.trigger",
        description="Trigger file sync with specified peers or all peers"
    )
    def sync_trigger(input: SyncTriggerInput) -> SyncTriggerResult:
        result = client.trigger_sync(input.peer_ids)
        return SyncTriggerResult(**result)
    
    @server.tool(
        name="sync.status",
        description="Get the status of a sync operation"
    )
    def sync_status(sync_id: str | None = None) -> dict:
        return client.get_sync_status(sync_id)
    
    @server.tool(
        name="app.install",
        description="Install an application from the app registry"
    )
    def app_install(input: AppInstallInput) -> AppInstallResult:
        result = client.install_app(input.name)
        return AppInstallResult(**result)
    
    @server.tool(
        name="app.start",
        description="Start an installed application"
    )
    def app_start(name: str) -> dict:
        return client.start_app(name)
    
    @server.tool(
        name="app.stop",
        description="Stop a running application"
    )
    def app_stop(name: str) -> dict:
        return client.stop_app(name)
    
    @server.tool(
        name="db.query",
        description="Execute a SQL query on the knowledge database"
    )
    def db_query(input: DbQueryInput) -> list[dict]:
        return client.query(input.sql)
    
    @server.tool(
        name="network.peers",
        description="List all known mesh peers"
    )
    def network_peers() -> list[dict]:
        return client.get_peers()
    
    @server.tool(
        name="network.connect",
        description="Connect to a mesh peer"
    )
    def network_connect(peer_id: str) -> dict:
        return client.connect_peer(peer_id)
    
    @server.tool(
        name="config.get",
        description="Get a configuration value"
    )
    def config_get(input: ConfigGetInput) -> str:
        return client.get_config(input.key)
    
    @server.tool(
        name="config.set",
        description="Set a configuration value"
    )
    def config_set(input: ConfigSetInput) -> None:
        client.set_config(input.key, input.value)
```

---

## 6. MCP Prompts (Templates)

Prompts provide templated messages for common workflows.

| Prompt | Template |
|--------|----------|
| `review-sync-status` | Generate a comprehensive sync status report |
| `list-apps` | Show all installed apps with their states |
| `check-peer-connectivity` | Display peer connection status |
| `search-knowledge` | Search the knowledge base |
| `app-management` | Manage installed applications |

### Prompt Definitions

```python
# src/mcp/prompts.py
from mcp.types import Prompt, PromptMessage
from mcp.server import Server

def register_prompts(server: Server):
    
    @server.list_prompts()
    def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="review-sync-status",
                description="Generate a comprehensive sync status report",
                arguments=[
                    PromptArgument(
                        name="include_history",
                        description="Include recent sync history",
                        required=False
                    )
                ]
            ),
            Prompt(
                name="list-apps",
                description="Show all installed applications with their current state"
            ),
            Prompt(
                name="check-peer-connectivity",
                description="Display the connection status of all known peers"
            ),
        ]
    
    @server.get_prompt()
    def get_prompt(name: str, arguments: dict | None = None) -> list[PromptMessage]:
        if name == "review-sync-status":
            include_history = arguments.get("include_history", False) if arguments else False
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text=f"""Please review the current sync status of Meshloom. 
                        
Include the following information:
- Current sync state (idle/syncing/error)
- Pending changes
- Last successful sync time
- Connected peers and their sync status
{f'- Recent sync history (last 10 syncs)' if include_history else ''}

If there are any issues, please recommend fixes."""
                    )
                )
            ]
        elif name == "list-apps":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""Please list all installed Meshloom applications.

For each app, show:
- Application name
- Version
- Status (installed/running/stopped)
- Resource usage if running

If any apps have issues, please suggest solutions."""
                    )
                )
            ]
        elif name == "check-peer-connectivity":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        type="text",
                        text="""Please check the connectivity status of all mesh peers.

For each peer, show:
- Peer ID
- Connection status (connected/disconnected/connecting)
- Last seen timestamp
- Latency
- Pending sync items

If any peers are disconnected, please help troubleshoot."""
                    )
                )
            ]
        
        raise ValueError(f"Unknown prompt: {name}")
```

---

## 7. Implementation Steps

### Step 1: Add MCP SDK to Vendor

```bash
# Add to requirements.txt or pyproject.toml
modelcontextprotocol>=0.1.0
pydantic>=2.0.0
```

### Step 2: Create MCP Server Class

```python
# src/mcp/server.py
from mcp.server import Server
from mcp.types import Tool, Resource, Prompt
import asyncio

class MeshloomMCPServer:
    def __init__(self, client: MeshloomClient):
        self.server = Server("meshloom")
        self.client = client
        self._register_handlers()
    
    def _register_handlers(self):
        from .resources import register_resources
        from .tools import register_tools
        from .prompts import register_prompts
        
        register_resources(self.server, self.client)
        register_tools(self.server, self.client)
        register_prompts(self.server)
    
    async def run(self):
        from mcp.server.stdio import stdio_server
        async with stdio_server() as streams:
            await self.server.run(
                streams[0],
                streams[1],
                self.server.create_initialization_options()
            )
```

### Step 3: Define Resources

- Implement all resource URIs listed in Section 4
- Add proper error handling for missing data
- Consider caching for frequently accessed resources

### Step 4: Define Tools

- Implement all tools listed in Section 5
- Add input validation using Pydantic
- Handle errors gracefully with meaningful messages

### Step 5: Integrate with Meshloom

```python
# Integration options
# Option A: Direct import (recommended for sidecar)
from meshloom import Meshloom

client = MeshloomClient(Meshloom())

# Option B: Unix socket (for subprocess)
client = SocketMeshloomClient("/run/meshloom.sock")

# Option C: HTTP (if REST API available)
client = HTTPMeshloomClient("http://localhost:8080")
```

### Step 6: Test with Kilo

```bash
# Test the MCP server standalone
cd meshloom
python -m mcp.server

# Or test with Kilo configuration
kilo config set mcp.servers.meshloom "python /path/to/meshloom/src/mcp/server.py"
```

---

## 8. Code Structure

```
src/mcp/
├── __init__.py          # Package initialization
├── server.py           # MCP server implementation
├── resources.py       # Resource definitions
├── tools.py            # Tool definitions
├── prompts.py          # Prompt templates
├── client.py           # Meshloom client wrapper
└── types.py           # Pydantic type definitions
```

### File: `src/mcp/__init__.py`

```python
"""Meshloom MCP Server - Exposes Meshloom to AI assistants via MCP."""
from .server import MeshloomMCPServer
from .client import MeshloomClient

__all__ = ["MeshloomMCPServer", "MeshloomClient"]
__version__ = "0.1.0"
```

### File: `src/mcp/client.py`

```python
"""Meshloom client for MCP server."""
from typing import Any
import logging

logger = logging.getLogger(__name__)

class MeshloomClient:
    """Wrapper for Meshloom API."""
    
    def __init__(self, meshloom_instance=None):
        self._ml = meshloom_instance
        self._connected = False
    
    def _ensure_connected(self):
        """Lazy connection to Meshloom."""
        if not self._connected:
            # Initialize connection
            self._connected = True
    
    def get_peers(self) -> list[dict]:
        """Get list of mesh peers."""
        self._ensure_connected()
        # return self._ml.network.peers.list()
        return []
    
    def get_apps(self) -> list[dict]:
        """Get list of installed apps."""
        self._ensure_connected()
        # return self._ml.apps.list()
        return []
    
    def get_config(self, key: str) -> Any:
        """Get configuration value."""
        self._ensure_connected()
        # return self._ml.config.get(key)
        return None
    
    def set_config(self, key: str, value: Any) -> None:
        """Set configuration value."""
        self._ensure_connected()
        # self._ml.config.set(key, value)
    
    def trigger_sync(self, peer_ids: list[str] | None = None) -> dict:
        """Trigger sync with peers."""
        self._ensure_connected()
        # return self._ml.sync.trigger(peer_ids)
        return {"sync_id": "test", "status": "started", "peers_involved": 0}
    
    def get_sync_status(self, sync_id: str | None = None) -> dict:
        """Get sync status."""
        self._ensure_connected()
        # return self._ml.sync.status(sync_id)
        return {}
    
    def install_app(self, name: str) -> dict:
        """Install an app."""
        self._ensure_connected()
        # return self._ml.apps.install(name)
        return {}
    
    def start_app(self, name: str) -> dict:
        """Start an app."""
        self._ensure_connected()
        # return self._ml.apps.start(name)
        return {}
    
    def stop_app(self, name: str) -> dict:
        """Stop an app."""
        self._ensure_connected()
        # return self._ml.apps.stop(name)
        return {}
    
    def query(self, sql: str) -> list[dict]:
        """Execute database query."""
        self._ensure_connected()
        # return self._ml.db.query(sql)
        return []
    
    def connect_peer(self, peer_id: str) -> dict:
        """Connect to a peer."""
        self._ensure_connected()
        # return self._ml.network.connect(peer_id)
        return {}
    
    def get_nodes(self) -> list[dict]:
        """Get knowledge nodes."""
        self._ensure_connected()
        # return self._ml.db.nodes.list()
        return []
    
    def get_edges(self) -> list[dict]:
        """Get knowledge edges."""
        self._ensure_connected()
        # return self._ml.db.edges.list()
        return []
```

---

## 9. Example Usage

### Example 1: Query Peers

**User (via Kilo):** "What peers are connected?"

**Kilo sends:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "method": "tools/call",
  "params": {
    "name": "network.peers",
    "arguments": {}
  }
}
```

**MCP Server responds:**
```json
{
  "jsonrpc": "2.0",
  "id": 1,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "[{\"peer_id\": \"alice\", \"status\": \"connected\", ...}]"
      }
    ]
  }
}
```

### Example 2: Trigger Sync

**User:** "Trigger a sync with all peers"

**Kilo sends:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "method": "tools/call",
  "params": {
    "name": "sync.trigger",
    "arguments": {}
  }
}
```

**MCP Server responds:**
```json
{
  "jsonrpc": "2.0",
  "id": 2,
  "result": {
    "content": [
      {
        "type": "text",
        "text": "Sync started with sync_id=abc123, involving 3 peers"
      }
    ]
  }
}
```

### Example 3: Query Notes

**User:** "Show me all notes"

**Kilo sends:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "method": "resources/read",
  "params": {
    "uri": "meshloom://database/nodes"
  }
}
```

**MCP Server responds:**
```json
{
  "jsonrpc": "2.0",
  "id": 3,
  "result": {
    "contents": [
      {
        "uri": "meshloom://database/nodes",
        "mimeType": "application/json",
        "text": "[{\"id\": 1, \"content\": \"Note 1\", ...}, ...]"
      }
    ]
  }
}
```

---

## 10. Integration Points

### How MCP Server Connects to Meshloom

| Integration Point | Description |
|------------------|-------------|
| **Database** | SQLite/PostgreSQL connection for `db.query` |
| **Network Layer** | Peer connection state via `network.*` tools |
| **App Manager** | App lifecycle via `app.*` tools |
| **Sync Engine** | Sync operations via `sync.*` tools |
| **Config Store** | Configuration read/write |

### Shared Meshloom Instance vs Separate Process

**Option A: Shared Instance (Embedded)**
- MCP server imports Meshloom directly
- Direct API calls without serialization
- Fast but tight coupling

**Option B: Separate Process (Sidecar)**
- Meshloom runs as daemon
- MCP server connects via socket/HTTP
- Loose coupling, better isolation
- Recommended for production

### Authentication Considerations

| Concern | Solution |
|---------|----------|
| **Unauthorized Access** | Require authentication token for tool calls |
| **Network Exposure** | Bind to localhost or use UNIX socket |
| **Config Modification** | Separate read/write tool permissions |
| **Audit Logging** | Log all tool invocations |

### Minimal Auth Implementation

```python
class AuthenticatedMeshloomClient(MeshloomClient):
    def __init__(self, api_key: str, meshloom_instance=None):
        super().__init__(meshloom_instance)
        self._api_key = api_key
    
    def _check_auth(self):
        # Verify API key for sensitive operations
        pass
    
    def set_config(self, key: str, value: Any) -> None:
        self._check_auth()
        super().set_config(key, value)
```

---

## Appendix: Error Handling

All tools should return structured error responses:

```python
from mcp.types import TextContent, ToolError

@server.tool(name="sync.trigger")
def sync_trigger(input: SyncTriggerInput) -> SyncTriggerResult:
    try:
        result = client.trigger_sync(input.peer_ids)
        return SyncTriggerResult(**result)
    except MeshloomError as e:
        raise ToolError(f"Sync failed: {e}")
    except Exception as e:
        raise ToolError(f"Unexpected error: {e}")
```

---

## Appendix: Testing

```python
# tests/test_mcp_server.py
import pytest
from mcp.client import MeshloomClient
from mcp.server import MeshloomMCPServer

def test_list_peers():
    client = MeshloomClient()
    server = MeshloomMCPServer(client)
    # Test that resources and tools are registered
    assert len(server.server._resources) > 0
    assert len(server.server._tools) > 0
```

---

*Document Version: 0.1.0*
*Generated for Meshloom MCP Server integration with Kilo*
