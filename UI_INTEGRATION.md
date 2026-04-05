# Meshloom UI Integration Guide

## Table of Contents

1. [Framework Architecture](#1-framework-architecture)
2. [Core Services](#2-core-services)
3. [App Framework](#3-app-framework)
4. [UI Integration Options](#4-ui-integration-options)
5. [API Communication](#5-api-communication)
6. [Data Flow Example](#6-data-flow-example)
7. [Frontend Structure](#7-frontend-structure)
8. [Getting Started](#8-getting-started)

---

## 1. Framework Architecture

### Layer Model

Meshloom is organized into a layered architecture that separates concerns from networking to application logic:

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATIONS                              │
│     (Files, Notes, Tasks, Calendar, Contacts, Comm, etc.)    │
├─────────────────────────────────────────────────────────────┤
│                    APP MANAGER                               │
│          (Installation, Lifecycle, Permissions)              │
├─────────────────────────────────────────────────────────────┤
│                    CORE SERVICES                              │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐  │
│  │ Network   │ │  Sync     │ │ Database  │ │  Container  │  │
│  │ Service   │ │  Engine   │ │  Manager  │ │  Manager    │  │
│  └───────────┘ └───────────┘ └───────────┘ └─────────────┘  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐                  │
│  │   App     │ │  Bridge   │ │   API     │                  │
│  │ Registry  │ │  Manager  │ │  Server   │                  │
│  └───────────┘ └───────────┘ └───────────┘                  │
├─────────────────────────────────────────────────────────────┤
│              RETICULUM NETWORK STACK (RNS)                   │
│       (Peer Discovery, Encryption, Mesh Routing)              │
├─────────────────────────────────────────────────────────────┤
│              TRANSPORT LAYER                                 │
│      (LoRa, Bluetooth, WiFi Direct, HaLow, Internet)        │
└─────────────────────────────────────────────────────────────┘
```

### Core Components and Their Responsibilities

| Component | Responsibility |
|-----------|----------------|
| **NetworkService** | RNS initialization, peer discovery, link creation, identity management |
| **SyncEngine** | File manifest generation, peer comparison, file transfer, conflict resolution |
| **DatabaseManager** | MariaDB lifecycle, connection pooling, schema management |
| **ContainerManager** | App isolation, resource limits, environment management |
| **AppRegistry** | App discovery, installation, lifecycle management, permissions |
| **BridgeManager** | External protocol bridges (XMPP, Matrix, Nextcloud, ATAK) |
| **APIServer** | Unix socket API, command routing, response formatting |

### Data Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│   UI     │────▶│  Socket  │────▶│Command   │────▶│  Service │
│  Client  │     │   API    │     │ Handler  │     │  Layer   │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                                                            │
                                                            ▼
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Remote  │◀───▶│   RNS    │◀───▶│  Sync    │◀───▶│ Database  │
│   Peers  │     │  Network │     │  Engine  │     │  Manager  │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
```

---

## 2. Core Services

### 2.1 NetworkService (`src/services/network.py`)

The NetworkService provides peer-to-peer networking using Reticulum Network Stack (RNS).

**Key Responsibilities:**
- Identity management (load or create Ed25519 key pairs)
- Peer discovery via periodic announces
- Request handlers for status, file index, and file data
- Link creation for direct peer communication

**Key Methods:**
```python
# Start/stop
async def start() -> None
async def stop() -> None

# Peer management
def get_peers() -> List[Peer]
def get_peer(peer_id: str) -> Optional[Peer]
def get_peer_count() -> int
def register_peer_callback(callback: Callable[[Peer], None]) -> None

# Link creation
def create_link(peer_id: str) -> Optional[RNS.Link]

# Status
def get_status() -> Dict[str, Any]
```

**Configuration:**
- `reticulum.announce_interval`: Seconds between peer announces (default: 30)
- `reticulum.identity_path`: Path to stored identity (default: `~/.meshloom/storage/identities/meshloom`)
- Default socket: `~/.reticulum/config`

---

### 2.2 SyncEngine (`src/services/sync/engine.py`)

The SyncEngine handles file synchronization between devices via RNS.

**Key Responsibilities:**
- Scan local sync directory and build file manifest
- Compare with remote peers to determine sync operations
- Transfer files via RNS links
- Last-writer-wins conflict resolution

**Key Methods:**
```python
# Start/stop
async def start() -> None
async def stop() -> None

# Sync operations
def trigger_sync() -> None
def get_local_manifest() -> FileManifest

# Status
def get_status() -> Dict[str, Any]
```

**Configuration:**
- `sync.sync_dir`: Local sync directory (default: `~/MeshloomSync`)
- `sync.sync_interval`: Seconds between sync checks (default: 60)
- `sync.auto_sync`: Enable automatic sync (default: True)

---

### 2.3 DatabaseManager (`src/services/db/manager.py`)

The DatabaseManager provides MariaDB database access for apps.

**Key Responsibilities:**
- Embedded MariaDB server lifecycle (start/stop)
- Connection pooling and management
- Schema initialization
- CRUD operations for entities (nodes, edges, apps, devices)

**Key Methods:**
```python
# Lifecycle
def initialize() -> bool
def shutdown() -> None

# Connections
@contextmanager
def get_connection() -> Generator

# Operations
def execute(query: str, params: tuple = None) -> Any
def insert_node(node: Node) -> bool
def get_node(node_id: str) -> Optional[Node]
def list_nodes(limit: int = 100, offset: int = 0) -> List[Node]
def update_node(node: Node) -> bool
def delete_node(node_id: str) -> bool

# Status
def health_check() -> Dict[str, Any]
def status() -> Dict[str, Any]
```

**Configuration:**
- `database.backend`: Database type (default: "mariadb")
- `database.host`: Database host (default: "localhost")
- `database.port`: Database port (default: 3306)
- `database.user`: Database user (default: "meshloom")

**Database Location:**
- Data: `~/.meshloom/data/mariadb/`
- Socket: `~/.meshloom/run/mariadb.sock`

---

### 2.4 ContainerManager (`src/services/container/manager.py`)

The ContainerManager provides isolated environments for apps.

**Key Responsibilities:**
- App container creation and lifecycle
- Resource limits (CPU, memory, storage)
- Environment variable management
- Volume mounting

---

### 2.5 AppRegistry (`src/apps/registry.py`)

The AppRegistry manages app lifecycle and discovery.

**Key Responsibilities:**
- App discovery from directory scanning
- App installation/uninstallation
- App start/stop lifecycle
- App metadata management

**Key Methods:**
```python
def register(metadata: AppMetadata, app_class: type) -> None
def install(app_id: str) -> bool
def uninstall(app_id: str) -> bool
def start(app_id: str) -> bool
def stop(app_id: str) -> bool
def list_apps() -> List[Dict[str, Any]]
def get_app(app_id: str) -> Optional[App]
```

---

### 2.6 BridgeManager (`src/bridges/manager.py`)

The BridgeManager manages external protocol bridges for federation.

**Supported Bridges:**
| Bridge | Protocol | Purpose |
|--------|----------|---------|
| **XMPP** | RFC 6120 | Unified messaging |
| **Matrix** | Matrix Protocol | Decentralized chat |
| **Nextcloud** | WebDAV/Sabre | File sync |
| **ATAK** | CO-TOP | Tactical messaging |

**Key Methods:**
```python
def register_bridge(bridge: Bridge) -> None
def start() -> None
def stop() -> None
def list_bridges() -> List[Bridge]
def get_status() -> Dict[str, Any]
```

---

### 2.7 APIServer (`src/api/server.py`)

The APIServer provides the Unix socket control interface.

**Key Responsibilities:**
- Unix socket server lifecycle
- JSON request/response handling
- Command routing to CommandHandler
- Client connection management

**Default Socket Path:** `~/.local/run/meshloom/api.sock`

**Key Methods:**
```python
async def start() -> None
async def stop() -> None

@property
def is_running(self) -> bool
@property
def socket_path(self) -> str
```

---

## 3. App Framework

### 3.1 Base App Class Structure (`src/apps/base.py`)

All Meshloom apps inherit from the `App` base class:

```python
from src.apps.base import App, AppContext
from src.apps.metadata import AppMetadata, AppCategory, AppState

class MyApp(App):
    def __init__(self, metadata: AppMetadata, db=None) -> None:
        super().__init__(metadata, db)
        # Initialize database schema
        self._init_db(self.DEFAULT_SCHEMA)
    
    def on_start(self) -> bool:
        """Called when app starts"""
        return True
    
    def on_stop(self) -> bool:
        """Called when app stops"""
        return True
```

**AppContext Properties:**
```python
@dataclass
class AppContext:
    app_id: str                    # Unique app identifier
    app_dir: Path                  # App directory
    data_dir: Path                 # App data directory
    sync_dir: Path                 # Sync directory
    config: Dict[str, Any]         # App configuration
    db_manager: Any                # Database manager
```

**Database Access:**
```python
# Using the db property (context manager)
with self.db as conn:
    with conn.cursor() as cursor:
        cursor.execute("SELECT * FROM table")
```

---

### 3.2 App Categories

| Category | Description | Apps |
|----------|-------------|------|
| **PRODUCTIVITY** | Core productivity tools | files, deck, calendar, contacts, notes, tasks |
| **KNOWLEDGE** | Knowledge management | collectives, cookbook, universal |
| **LIFE** | Personal management | vault, books, media, health |
| **COMMUNICATION** | Messaging and calls | comm, talk |
| **INTELLIGENCE** | AI and documents | ai, office |
| **LOCATION** | Maps and social | map, social |

---

### 3.3 Lifecycle Methods

| Method | When Called | Purpose |
|--------|-------------|---------|
| `on_install()` | App is installed | Initialize database, default data |
| `on_uninstall()` | App is uninstalled | Clean up data, remove schema |
| `on_start()` | App starts | Load data, start background tasks |
| `on_stop()` | App stops | Save data, stop tasks |

---

## 4. UI Integration Options

### 4.1 Web UI (Recommended)

The recommended approach for most use cases.

**Architecture:**
```
┌──────────────────────────────────────────────┐
│              Web Browser                      │
│  ┌────────────────────────────────────────┐  │
│  │        React/Vue Application           │  │
│  │   (State Management, Components)       │  │
│  └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
                    │
                    ▼
┌──────────────────────────────────────────────┐
│           Web Server (Flask/FastAPI)         │
│    - Serves HTML/JS/CSS                       │
│  - REST API endpoints                        │
│  - WebSocket for real-time                   │
└──────────────────────────────────────────────┘
                    │
                    ▼ (Unix Socket)
┌──────────────────────────────────────────────┐
│              Meshloom Backend                 │
└──────────────────────────────────────────────┘
```

**Implementation:**
```python
# Example Flask integration
from flask import Flask, jsonify
import socket

app = Flask(__name__)

MESHLOOM_SOCKET = os.path.expanduser("~/.local/run/meshloom/api.sock")

def call_meshloom(command: str, args: dict) -> dict:
    """Send command to Meshloom via Unix socket"""
    client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client.connect(MESHLOOM_SOCKET)
    client.send(json.dumps({"command": command, "args": args}).encode())
    response = client.recv(4096)
    return json.loads(response.decode())

@app.route("/api/status")
def status():
    return jsonify(call_meshloom("status", {}))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

---

### 4.2 Desktop UI

**Electron:**
- Embed Web UI in Electron shell
- Native system tray
- Desktop notifications
- File system access

**Native:**
- Use platform-specific toolkits (Qt, GTK, SwiftUI)
- Direct socket connection to Meshloom
- Native look and feel

---

### 4.3 Mobile UI

**React Native:**
- Cross-platform mobile
- Reuse web UI components
- Push notifications
- Background sync

**Native:**
- Platform-specific (SwiftUI/Kotlin)
- Best performance
- Full native features

---

### 4.4 CLI (Headless Servers)

```python
# Example CLI client
import socket
import json
import sys

def execute(command: str, args: dict = None) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("/home/user/.local/run/meshloom/api.sock")
    
    request = {"command": command, "args": args or {}}
    sock.send(json.dumps(request).encode())
    
    response = sock.recv(4096)
    return json.loads(response.decode())

# Usage
result = execute("status")
print(json.dumps(result, indent=2))
```

---

## 5. API Communication

### 5.1 Unix Socket API Protocol

The primary API interface uses JSON over Unix domain sockets.

**Request Format:**
```json
{
  "command": "peers",
  "args": {}
}
```

**Response Format:**
```json
{
  "success": true,
  "data": {
    "peers": [...],
    "count": 2
  },
  "error": null
}
```

**Error Response:**
```json
{
  "success": false,
  "data": null,
  "error": "Network service not available"
}
```

---

### 5.2 Available Commands

| Command | Description | Args |
|---------|-------------|------|
| `status` | Get system status | none |
| `peers` | List discovered peers | none |
| `apps` | List installed apps | none |
| `app start` | Start an app | `{"app_id": "notes"}` |
| `app stop` | Stop an app | `{"app_id": "notes"}` |
| `config get` | Get config value | `{"key": "sync.sync_dir"}` |
| `config set` | Set config value | `{"key": "key", "value": "value"}` |
| `sync` | Trigger sync | none |
| `bridges` | List bridges | none |
| `execute` | Execute in container | `{"command": "..."}` |

---

### 5.3 REST Endpoints (Web UI)

When using the web UI approach, expose these REST endpoints:

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | System status |
| `/api/peers` | GET | List peers |
| `/api/apps` | GET | List apps |
| `/api/apps/<id>/start` | POST | Start app |
| `/api/apps/<id>/stop` | POST | Stop app |
| `/api/config/<key>` | GET/POST | Get/set config |
| `/api/sync` | POST | Trigger sync |
| `/api/bridges` | GET | List bridges |

---

### 5.4 WebSocket for Real-time Updates

Use WebSocket for real-time events:

```javascript
// Frontend WebSocket client
const ws = new WebSocket("ws://localhost:5000/ws");

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  switch (data.type) {
    case "peer.discovered":
      console.log("New peer:", data.peer);
      break;
    case "sync.completed":
      console.log("Sync done:", data.result);
      break;
    case "app.started":
      console.log("App started:", data.app);
      break;
  }
};
```

**Events:**
- `peer.discovered`, `peer.updated`, `peer.lost`
- `sync.started`, `sync.completed`, `sync.failed`
- `app.installed`, `app.started`, `app.stopped`
- `bridge.connected`, `bridge.disconnected`

---

## 6. Data Flow Example

### Example: Creating a Note

```
┌─────────────────────────────────────────────────────────────────────┐
│ Step 1: User creates note in UI                                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 2: UI sends request via REST/WebSocket                          │
│ POST /api/apps/notes/create {title: "My Note", content: "..."}       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 3: Web server translates to socket command                     │
│ {"command": "app notes:create", "args": {...}}                      │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 4: Meshloom API server receives command                        │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 5: CommandHandler routes to AppRegistry                        │
│ AppRegistry.get_app("notes").create_note(...)                       │
└─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 6: NotesApp creates note in MariaDB                            │
│ INSERT INTO notes (id, title, content, created_at) VALUES (...)     │
└─────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┴───────────────┐
              ▼                               ▼
┌─────────────────────────┐     ┌─────────────────────────────┐
│ Step 7a: SyncEngine      │     │ Step 7b: Return success     │
│ detects change          │     │ to UI via WebSocket         │
│ - Updates local manifest│     │ {"type": "note.created",   │
│ - Compares with peers   │     │  "data": {"id": "..."}}     │
│ - Queues file sync      │     └─────────────────────────────┘
└─────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────────┐
│ Step 8: File synced to peers via RNS                                │
│ - Notes file updated in ~/MeshloomSync/                            │
│ - RNS link sends file to peer                                       │
│ - Peer receives and updates their database                         │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 7. Frontend Structure

### 7.1 Suggested Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Frontend Architecture                      │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────────────────────────────────────────────┐   │
│  │                   UI Components                        │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │ Sidebar │ │ Content │ │ Header  │ │ Modals  │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                   │
│                            ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              State Management (Zustand/Redux)          │   │
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐    │   │
│  │  │  Auth   │ │  Apps   │ │  Peers  │ │  Sync   │    │   │
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘    │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                   │
│                            ▼                                   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                 API Layer (Axios/Fetch)               │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │   │
│  │  │   REST API  │ │  WebSocket  │ │  Socket API │     │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘     │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 7.2 State Management

```javascript
// Zustand store example
import { create } from 'zustand';

const useMeshloomStore = create((set, get) => ({
  // Auth state
  deviceId: null,
  isAuthenticated: false,
  
  // Apps state
  apps: [],
  activeApp: null,
  
  // Network state
  peers: [],
  peerCount: 0,
  
  // Sync state
  syncStatus: 'idle',
  lastSync: null,
  
  // Actions
  setDeviceId: (id) => set({ deviceId: id, isAuthenticated: true }),
  
  fetchApps: async () => {
    const response = await fetch('/api/apps');
    const data = await response.json();
    set({ apps: data.data.apps });
  },
  
  fetchPeers: async () => {
    const response = await fetch('/api/peers');
    const data = await response.json();
    set({ peers: data.data.peers, peerCount: data.data.count });
  },
  
  startApp: async (appId) => {
    await fetch(`/api/apps/${appId}/start`, { method: 'POST' });
    get().fetchApps();
  },
  
  // WebSocket event handling
  handleEvent: (event) => {
    switch (event.type) {
      case 'peer.discovered':
        get().fetchPeers();
        break;
      case 'sync.completed':
        set({ syncStatus: 'idle', lastSync: Date.now() });
        break;
    }
  }
}));

export default useMeshloomStore;
```

### 7.3 Component Structure

```
src/
├── components/
│   ├── Layout/
│   │   ├── Sidebar.tsx
│   │   ├── Header.tsx
│   │   └── Layout.tsx
│   ├── Apps/
│   │   ├── AppCard.tsx
│   │   ├── AppList.tsx
│   │   └── AppDetail.tsx
│   ├── Network/
│   │   ├── PeerList.tsx
│   │   └── PeerCard.tsx
│   ├── Sync/
│   │   ├── SyncStatus.tsx
│   │   └── SyncIndicator.tsx
│   └── Common/
│       ├── Button.tsx
│       ├── Modal.tsx
│       └── Loading.tsx
├── pages/
│   ├── Dashboard.tsx
│   ├── AppView.tsx
│   ├── Settings.tsx
│   └── Network.tsx
├── hooks/
│   ├── useMeshloom.ts
│   ├── useWebSocket.ts
│   └── useSync.ts
├── store/
│   └── index.ts
├── api/
│   ├── client.ts
│   └── socket.ts
└── App.tsx
```

### 7.4 Authentication (Local/Device-based)

Since Meshloom is a local-first system, authentication is device-based:

```javascript
// Device-based authentication
const authenticate = async () => {
  // Get or create device identity
  const response = await fetch('/api/status');
  const status = await response.json();
  
  // Use device identity as authentication
  // No username/password needed
  return {
    deviceId: status.services.network.identity,
    isLocal: true
  };
};

// Store authentication in localStorage
localStorage.setItem('meshloom_auth', JSON.stringify({
  deviceId: '...',
  timestamp: Date.now()
}));
```

---

## 8. Getting Started

### 8.1 How to Add a New App

**Step 1: Create App Directory**
```
src/apps/myapp/
├── __init__.py
├── app.py          # Main app class
└── metadata.py     # App metadata
```

**Step 2: Define Metadata**
```python
# src/apps/myapp/metadata.py
from src.apps.metadata import AppMetadata, AppCategory

APP_METADATA = AppMetadata(
    name="My App",
    description="Description of my app",
    category=AppCategory.PRODUCTIVITY,
    version="0.1.0",
    author="Your Name",
    keywords=["keyword1", "keyword2"],
)
```

**Step 3: Implement App Class**
```python
# src/apps/myapp/app.py
from src.apps.base import App
from src.apps.metadata import AppMetadata

class MyApp(App):
    DEFAULT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS items (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        created_at REAL DEFAULT (strftime('%s', 'now'))
    );
    """
    
    def __init__(self, metadata: AppMetadata, db=None) -> None:
        super().__init__(metadata, db)
        self._init_db(self.DEFAULT_SCHEMA)
    
    def on_install(self) -> bool:
        # Initialize default data
        return True
    
    def on_start(self) -> bool:
        return True
    
    def on_stop(self) -> bool:
        return True
    
    def on_uninstall(self) -> bool:
        return True
    
    # App-specific methods
    def create_item(self, name: str) -> str:
        import uuid
        item_id = str(uuid.uuid4())
        with self.db as conn:
            conn.execute("INSERT INTO items (id, name) VALUES (?, ?)", 
                        (item_id, name))
        return item_id
    
    def get_items(self) -> list:
        with self.db as conn:
            cursor = conn.execute("SELECT * FROM items")
            return [dict(row) for row in cursor.fetchall()]
```

**Step 4: Register the App**
```python
# In src/main.py or app registry initialization
from src.apps.myapp.app import MyApp, APP_METADATA

app_registry.register(APP_METADATA, MyApp)
```

---

### 8.2 How to Connect UI to Backend

**Option A: Web UI (Recommended)**

1. **Create Flask/FastAPI server:**
```python
# web_server.py
from flask import Flask, jsonify
import socket
import json
import os

app = Flask(__name__)

SOCKET_PATH = os.path.expanduser("~/.local/run/meshloom/api.sock")

def meshloom_request(command: str, args: dict = None) -> dict:
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(SOCKET_PATH)
    request = json.dumps({"command": command, "args": args or {}})
    sock.send(request.encode())
    response = sock.recv(8192)
    return json.loads(response.decode())

@app.route("/api/status")
def status():
    return jsonify(meshloom_request("status"))

@app.route("/api/peers")
def peers():
    return jsonify(meshloom_request("peers"))

@app.route("/api/apps")
def apps():
    return jsonify(meshloom_request("apps"))

@app.route("/api/apps/<app_id>/start", methods=["POST"])
def start_app(app_id):
    return jsonify(meshloom_request("app start", {"app_id": app_id}))

@app.route("/api/apps/<app_id>/stop", methods=["POST"])
def stop_app(app_id):
    return jsonify(meshloom_request("app stop", {"app_id": app_id}))

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
```

2. **Run both servers:**
```bash
# Terminal 1: Start Meshloom
cd meshloom && python -m src.main

# Terminal 2: Start Web UI
python web_server.py
```

3. **Access UI:** Open `http://localhost:5000` in browser

---

**Option B: Direct Unix Socket Client**

```python
# ui_client.py
import socket
import json

class MeshloomClient:
    def __init__(self, socket_path="~/.local/run/meshloom/api.sock"):
        self.socket_path = os.path.expanduser(socket_path)
    
    def _call(self, command: str, args: dict = None) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(self.socket_path)
        sock.send(json.dumps({"command": command, "args": args or {}}).encode())
        response = sock.recv(8192)
        return json.loads(response.decode())
    
    def status(self):
        return self._call("status")
    
    def peers(self):
        return self._call("peers")
    
    def apps(self):
        return self._call("apps")
    
    def start_app(self, app_id):
        return self._call("app start", {"app_id": app_id})
    
    def stop_app(self, app_id):
        return self._call("app stop", {"app_id": app_id})

# Usage
client = MeshloomClient()
print(client.status())
```

---

**Option C: Python CLI Tool**

```python
#!/usr/bin/env python3
# meshloom-cli
import sys
import socket
import json
import os

def main():
    socket_path = os.path.expanduser("~/.local/run/meshloom/api.sock")
    
    if len(sys.argv) < 2:
        print("Usage: meshloom-cli <command> [args]")
        sys.exit(1)
    
    command = sys.argv[1]
    args = {}
    
    if len(sys.argv) > 2:
        args = json.loads(sys.argv[2])
    
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect(socket_path)
    sock.send(json.dumps({"command": command, "args": args}).encode())
    print(sock.recv(8192).decode())

if __name__ == "__main__":
    main()
```

```bash
# Usage
chmod +x meshloom-cli
./meshloom-cli status
./meshloom-cli peers
./meshloom-cli apps
```

---

## Summary

Meshloom provides a comprehensive framework for building a local-first, peer-to-peer operating system. The UI can connect through:

1. **Web UI** (Recommended): Flask/FastAPI server with REST API + WebSocket
2. **Desktop UI**: Electron or native with socket client
3. **Mobile UI**: React Native or native with socket client
4. **CLI**: Direct Unix socket communication

The core architecture separates concerns through well-defined services (Network, Sync, Database, Container, App, Bridge, API), allowing flexible integration patterns for different UI implementations.

For the best developer experience, use the Web UI approach with a React frontend communicating to a Flask backend that interfaces with Meshloom via Unix sockets.