"""Event bus for inter-service communication in Meshloom."""

import time
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import threading


@dataclass
class Event:
    """An event in the Meshloom event system."""
    type: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = "unknown"
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return {
            "type": self.type,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
        }


class EventBus:
    """
    Event bus for inter-service communication.
    
    Allows components to publish and subscribe to events.
    Events are processed asynchronously.
    """
    
    EVENT_TYPES = [
        # Peer events
        "peer.discovered",
        "peer.updated",
        "peer.lost",
        
        # Reticulum events
        "reticulum.started",
        "reticulum.stopped",
        "reticulum.error",
        
        # Sync events
        "sync.started",
        "sync.completed",
        "sync.failed",
        "sync.progress",
        
        # App events
        "app.installed",
        "app.started",
        "app.stopped",
        "app.uninstalled",
        
        # Storage events
        "storage.full",
        "storage.low",
        
        # Identity events
        "identity.created",
        "identity.loaded",
        
        # Bridge events
        "bridge.connected",
        "bridge.disconnected",
        "bridge.error",
        
        # Network events
        "network.online",
        "network.offline",
        "network.transport_added",
        "network.transport_removed",
    ]
    
    def __init__(self, history_size: int = 100) -> None:
        self._subscribers: Dict[str, List[Callable[[Event], None]]] = defaultdict(list)
        self._history: List[Event] = []
        self._history_size = history_size
        self._lock = threading.Lock()
    
    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to an event type."""
        with self._lock:
            self._subscribers[event_type].append(callback)
    
    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type."""
        with self._lock:
            if callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
    
    def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        with self._lock:
            self._history.append(event)
            if len(self._history) > self._history_size:
                self._history.pop(0)
            
            subscribers = list(self._subscribers.get(event.type, []))
            global_subscribers = list(self._subscribers.get("*", []))
        
        for callback in subscribers + global_subscribers:
            try:
                callback(event)
            except Exception as e:
                print(f"[ERROR] EventBus: Callback failed for {event.type}: {e}")
    
    def publish_type(
        self, 
        event_type: str, 
        data: Optional[Dict[str, Any]] = None,
        source: str = "unknown"
    ) -> None:
        """Publish an event by type shorthand."""
        event = Event(
            type=event_type,
            data=data or {},
            source=source,
            timestamp=time.time()
        )
        self.publish(event)
    
    def get_history(
        self, 
        event_type: Optional[str] = None, 
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get event history."""
        with self._lock:
            history = list(self._history)
        
        if event_type:
            history = [e for e in history if e.type == event_type]
        
        history = history[-limit:]
        return [e.to_dict() for e in history]
    
    def clear_history(self) -> None:
        """Clear event history."""
        with self._lock:
            self._history.clear()
    
    def get_subscribers(self, event_type: str) -> int:
        """Get number of subscribers for an event type."""
        with self._lock:
            return len(self._subscribers.get(event_type, []))


event_bus = EventBus()
