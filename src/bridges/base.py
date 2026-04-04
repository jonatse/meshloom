"""Base bridge classes for Meshloom protocol bridges."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class ConnectionState(Enum):
    """Connection state for bridges."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class BridgeMessage:
    """Message format for bridge communication."""
    message_id: str
    sender: str
    recipient: str
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    thread_id: Optional[str] = None
    attachments: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message_id": self.message_id,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "thread_id": self.thread_id,
            "attachments": self.attachments,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BridgeMessage":
        """Create from dictionary."""
        timestamp = data.get("timestamp")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        return cls(
            message_id=data["message_id"],
            sender=data["sender"],
            recipient=data["recipient"],
            content=data["content"],
            timestamp=timestamp or datetime.utcnow(),
            metadata=data.get("metadata", {}),
            thread_id=data.get("thread_id"),
            attachments=data.get("attachments", []),
        )


@dataclass
class BridgeContact:
    """Contact/member from external network."""
    user_id: str
    display_name: str
    status: str = "offline"
    avatar_url: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "display_name": self.display_name,
            "status": self.status,
            "avatar_url": self.avatar_url,
            "metadata": self.metadata,
        }


@dataclass
class BridgeConfig:
    """Configuration for a bridge."""
    enabled: bool = False
    server: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    tls_enabled: bool = True
    auto_reconnect: bool = True
    reconnect_interval: int = 30
    ping_interval: int = 60
    timeout: int = 30
    metadata: Dict[str, Any] = field(default_factory=dict)


class BridgeError(Exception):
    """Base exception for bridge errors."""
    pass


class ConnectionError(BridgeError):
    """Connection-related errors."""
    pass


class MessageError(BridgeError):
    """Message-related errors."""
    pass


class Bridge(ABC):
    """
    Abstract base class for protocol bridges.
    
    Bridges connect Meshloom to external networks (XMPP, Matrix, etc.)
    and handle message translation between formats.
    """

    def __init__(self, bridge_id: str, config: BridgeConfig) -> None:
        self._bridge_id = bridge_id
        self._config = config
        self._state = ConnectionState.DISCONNECTED
        self._last_error: Optional[str] = None
        self._connected_at: Optional[datetime] = None

    @property
    def bridge_id(self) -> str:
        """Get bridge ID."""
        return self._bridge_id

    @property
    def config(self) -> BridgeConfig:
        """Get bridge configuration."""
        return self._config

    @property
    def state(self) -> ConnectionState:
        """Get connection state."""
        return self._state

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._state == ConnectionState.CONNECTED

    @property
    def last_error(self) -> Optional[str]:
        """Get last error message."""
        return self._last_error

    def _set_state(self, state: ConnectionState) -> None:
        """Set connection state."""
        self._state = state
        if state == ConnectionState.CONNECTED:
            self._connected_at = datetime.utcnow()
        elif state == ConnectionState.DISCONNECTED:
            self._connected_at = None

    def update_config(self, config: BridgeConfig) -> None:
        """Update bridge configuration."""
        self._config = config

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to external network.
        
        Returns:
            True if connection successful
        """
        raise NotImplementedError

    @abstractmethod
    def disconnect(self) -> bool:
        """
        Disconnect from external network.
        
        Returns:
            True if disconnection successful
        """
        raise NotImplementedError

    @abstractmethod
    def send(self, message: BridgeMessage) -> bool:
        """
        Send message to external network.
        
        Args:
            message: Message to send
            
        Returns:
            True if send successful
        """
        raise NotImplementedError

    @abstractmethod
    def receive(self) -> List[BridgeMessage]:
        """
        Receive messages from external network.
        
        Returns:
            List of received messages
        """
        raise NotImplementedError

    @abstractmethod
    def get_contacts(self) -> List[BridgeContact]:
        """
        Get connected members/contacts.
        
        Returns:
            List of contacts
        """
        raise NotImplementedError

    @abstractmethod
    def health_check(self) -> bool:
        """
        Check connection health.
        
        Returns:
            True if connection is healthy
        """
        raise NotImplementedError
