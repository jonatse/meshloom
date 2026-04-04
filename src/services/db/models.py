"""Data models for Meshloom database."""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class Node:
    """Graph node representing a piece of content."""
    id: str
    title: str
    content: str = ""
    summary: str = ""
    interest_level: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    source_url: str = ""
    source_type: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["metadata"] = json.dumps(self.metadata)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Node":
        """Create from dictionary."""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if isinstance(data.get("metadata"), str):
            data["metadata"] = json.loads(data["metadata"])
        return cls(**data)


@dataclass
class Edge:
    """Graph edge representing relationship between nodes."""
    id: str
    source_id: str
    target_id: str
    relationship_type: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Edge":
        """Create from dictionary."""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class App:
    """App registry entry."""
    id: str
    name: str
    category: str = ""
    state: str = "installed"
    config: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["config"] = json.dumps(self.config)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "App":
        """Create from dictionary."""
        if isinstance(data.get("created_at"), str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if isinstance(data.get("updated_at"), str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if isinstance(data.get("config"), str):
            data["config"] = json.loads(data["config"])
        return cls(**data)


@dataclass
class Device:
    """Device registration entry."""
    id: str
    name: str
    hostname: str = ""
    identity_hash: str = ""
    hardware_json: Dict[str, Any] = field(default_factory=dict)
    last_seen: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["hardware_json"] = json.dumps(self.hardware_json)
        if self.last_seen:
            data["last_seen"] = self.last_seen.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Device":
        """Create from dictionary."""
        if isinstance(data.get("last_seen"), str):
            data["last_seen"] = datetime.fromisoformat(data["last_seen"])
        if isinstance(data.get("hardware_json"), str):
            data["hardware_json"] = json.loads(data["hardware_json"])
        return cls(**data)


@dataclass
class SyncLog:
    """Sync operation log entry."""
    id: str
    entity_type: str
    entity_id: str
    action: str
    timestamp: datetime = field(default_factory=datetime.now)
    peer_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SyncLog":
        """Create from dictionary."""
        if isinstance(data.get("timestamp"), str):
            data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        return cls(**data)
