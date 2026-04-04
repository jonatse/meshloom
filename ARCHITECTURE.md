# Meshloom Architecture

## Core Concepts

### Local-First
Data stays on the local device by default. Sync is opt-in and user-controlled. This ensures:
- Works offline
- Maximum privacy
- User controls what leaves the device
- No lock-in to any cloud service

### Mesh Networking
Meshloom uses the Reticulum Network Stack (RNS) for all networking:
- Peer discovery over any transport medium
- End-to-end encryption
- DNS-free addressing
- Works over LoRa, Bluetooth, WiFi Direct, HaLow, and Internet

### Resource Sharing
Devices can share resources with the mesh network:
- GPU compute for AI workloads
- CPU for distributed processing
- Storage for backup and sync
- Bandwidth for relay
- All sharing is explicit opt-in, revocable at any time

### Protocol Bridges
Connect to external networks and ecosystems:
- XMPP networks
- Matrix homeservers
- Nextcloud servers
- ATAK/cursor-on-target for tactical messaging

---

## Layer Model

```
┌─────────────────────────────────────────────────────────────┐
│                    APPLICATIONS                              │
│  (files, deck, calendar, contacts, notes, tasks, comm)   │
├─────────────────────────────────────────────────────────────┤
│                    APP MANAGER                              │
│  (installation, lifecycle, permissions)                   │
├─────────────────────────────────────────────────────────────┤
│                    CORE SERVICES                             │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  Identity   │ │  Sync       │ │  Storage    │          │
│  │  Manager    │ │  Engine     │ │  Manager    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │  Resource   │ │  Permission │ │  Bridge     │          │
│  │  Manager    │ │  Manager    │ │  Manager    │          │
│  └─────────────┘ └─────────────┘ └─────────────┘          │
├─────────────────────────────────────────────────────────────┤
│                    NETWORK MANAGER                           │
│  (RNS integration, transport selection, peer management)  │
├─────────────────────────────────────────────────────────────┤
│              RETICULUM NETWORK STACK (RNS)                  │
│  (加密, peer discovery, routing over any medium)          │
├─────────────────────────────────────────────────────────────┤
│              TRANSPORT LAYER                                │
│  (LoRa, Bluetooth, WiFi Direct, HaLow, Internet)          │
└─────────────────────────────────────────────────────────────┘
```

Meshloom provides the services layer while RNS handles the networking layer.

---

## Component Breakdown

### Identity Manager
- Cryptographic identity derived from seed phrase
- Ed25519 key pairs (RNS-native)
- Manages keys, signatures, and verification

### Network Manager
- Handles RNS interface initialization
- Transport selection and management
- Peer discovery and connection management
- Announce/listen for services

### Sync Engine
- CRDT-based synchronization (pycrdt/Yjs)
- Conflict-free merging
- Selective sync with filters
- Offline-first operation

### Storage Manager
- Interfaces with local filesystem
- Manages data directories
- Handles backup and restore
- Data lifecycle management

### Resource Manager
- Tracks available resources (CPU, GPU, storage, bandwidth)
- Manages resource offers to mesh
- Allocates resources for requests
- QoS and fairness

### App Manager
- Installs, runs, manages applications
- Dependency resolution
- Lifecycle (install, start, stop, uninstall)
- App registry

### Permission Manager
- Enforces access controls
- Manages app permissions
- User consent flows
- Audit logging

### Bridge Manager
- Manages protocol bridges
- XMPP, Matrix, Nextcloud, ATAK
- Bidirectional message sync
- Federation policies

---

## Application Categories

### Productivity
- **files**: File sync, sharing, versioning
- **deck**: Kanban-style task management
- **calendar**: Events and scheduling
- **contacts**: Address book with relationships
- **notes**: Rich text notes
- **tasks**: Todo lists and reminders

### Knowledge
- **collectives**: Wiki/knowledge base
- **cookbook**: Recipes with inventory linking
- **universal**: Knowledge base, technical docs

### Life
- **vault**: Inventory management - track anything
- **books**: Accounting (Beancount)
- **media**: Media server
- **health**: Health and wellness tracking

### Communication
- **comm**: Unified messaging, video, audio
- **talk**: Video calls

### Intelligence
- **ai**: Local AI (Ollama) for organization
- **office**: Document editing

### Location
- **map**: Maps and navigation (OpenStreetMap)
- **social**: Profiles, trust levels, community feeds

---

## Deployment Modes

### local_only
- Single device, no network
- Use case: Maximum privacy, emergency, air-gapped

### mesh
- Multiple devices form mesh, no internet
- Use case: Home, office, local community

### hybrid
- Local mesh + optional cloud node (recommended)
- Use case: Best of both worlds - local-first with optional remote access

### cloud_primary
- Cloud node main, local for edge
- Use case: Always accessible, remote teams

---

## Network Transports

| Transport | Range | Bandwidth | Use Case |
|-----------|-------|-----------|----------|
| LoRa | 2-15 km | 0.3-50 kbps | Emergency, rural, off-grid |
| Bluetooth | ~100 m | 1-2 Mbps | Personal device sync |
| WiFi Direct | ~200 m | 100+ Mbps | Local mesh |
| HaLow | ~500 m | 10+ Mbps | Neighborhood mesh |
| Internet | Global | 100+ Mbps | Remote sync |

---

## Technical Stack

| Component | Technology |
|-----------|------------|
| Sync | pycrdt (Yjs) - Offline-first, conflict-free |
| Networking | Reticulum - DNS-free, encrypted, mesh-native |
| Database | SQLite - Reliable, local, embedded |
| AI | Ollama - Local, GPU-accelerated |
| UI | React + TypeScript |
| Identity | Ed25519 - Reticulum-native |

---

## Event System

Meshloom uses an event bus for inter-service communication:

- `peer.discovered`: New peer found on network
- `peer.updated`: Peer info changed
- `peer.lost`: Peer disconnected
- `reticulum.started`: Network stack initialized
- `reticulum.stopped`: Network stack stopped
- `sync.started`: Sync operation started
- `sync.completed`: Sync operation completed
- `sync.failed`: Sync operation failed
- `app.installed`: New app installed
- `app.started`: App started
- `app.stopped`: App stopped

---

## Development Phases

1. **Months 1-6**: Core node, sync, networking
2. **Months 6-12**: Tiered networking, device verification
3. **Months 12-18**: Hub apps (Files, Deck, Calendar, Contacts, Notes, Tasks)
4. **Months 18-24**: Comm (messaging, video), Map
5. **Months 24-30**: Media, AI, Office
6. **Months 30-36**: Vault, Universal, Social, Mobile
