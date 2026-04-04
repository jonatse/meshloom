# Meshloom

A decentralized mesh-networked personal cloud platform that runs as an application on any host OS.

## Vision

Meshloom is a **data-centric operating system** built on the principles of:

- **Node-based**: Runs on any host OS (Linux, macOS, Windows, Android, iOS), not as an OS itself
- **Local-first**: Data stays on device, sync is opt-in, maximum privacy
- **Mesh networking**: Works over LoRa, Bluetooth, WiFi Direct, HaLow, Internet via Reticulum
- **Resource sharing**: Share GPU, CPU, storage, bandwidth with the network
- **Protocol bridges**: Connect to XMPP, Matrix, Nextcloud, ATAK

## Core Features

### Data-Centric Architecture
All state lives in the mesh, not local disk. Data is synchronized using CRDTs for conflict-free merging.

### Reticulum Network Stack
- Peer discovery over any transport medium
- End-to-end encryption
- DNS-free addressing
- Works offline

### Local-First Design
- Works without internet
- Data stays on device by default
- Sync is explicit opt-in
- User controls what leaves their device

### Rich Application Suite
- **Productivity**: files, deck, calendar, contacts, notes, tasks
- **Knowledge**: collectives, cookbook, universal
- **Life**: vault, books, media, health
- **Communication**: comm, talk
- **Intelligence**: ai, office
- **Location**: map, social

## Quick Start

```bash
# Clone the repository
git clone https://github.com/jonatse/meshloom.git
cd meshloom

# Install dependencies
pip install rns

# Run the node
python -m meshloom

# View configuration
python -c "from src.core.config import config; print(config.get('app.name'))"
```

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture documentation.

### Component Overview

- **Identity Manager**: Cryptographic identity from seed phrase
- **Network Manager**: RNS integration, peer discovery
- **Sync Engine**: CRDT-based synchronization
- **Storage Manager**: Local filesystem interface
- **Resource Manager**: Shared resource tracking
- **App Manager**: Application lifecycle
- **Permission Manager**: Access controls
- **Bridge Manager**: Protocol bridges

### Deployment Modes

| Mode | Description |
|------|-------------|
| local_only | Single device, no network |
| mesh | Multiple devices form mesh |
| hybrid | Local mesh + optional cloud |
| cloud_primary | Cloud main, local edge |

## Technical Stack

| Component | Technology |
|-----------|------------|
| Sync | pycrdt (Yjs) |
| Networking | Reticulum (RNS) |
| Database | MariaDB |
| AI | Ollama |
| Identity | Ed25519 |

## License

MIT
