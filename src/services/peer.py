"""Peer dataclass for Meshloom network service."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from RNS.Destination import Destination


@dataclass
class Peer:
    """
    Represents a discovered peer in the Meshloom network.
    
    Attributes:
        id: Unique identifier (destination hash hex string)
        name: Human-readable name from announce app_data
        destination: RNS.Destination for outbound communication
        last_seen: Timestamp of last announcement received
    """
    id: str
    name: str
    destination: Destination
    last_seen: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> dict:
        """Convert peer to dictionary representation."""
        return {
            "id": self.id,
            "name": self.name,
            "last_seen": self.last_seen.isoformat(),
        }
    
    def __hash__(self) -> int:
        """Hash based on peer ID."""
        return hash(self.id)
    
    def __eq__(self, other: object) -> bool:
        """Equality based on peer ID."""
        if not isinstance(other, Peer):
            return NotImplemented
        return self.id == other.id