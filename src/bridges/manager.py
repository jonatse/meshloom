"""Bridge manager for Meshloom."""

import logging
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable

from .base import (
    Bridge,
    BridgeConfig,
    BridgeContact,
    BridgeMessage,
    ConnectionState,
)

logger = logging.getLogger(__name__)


@dataclass
class BridgeManagerConfig:
    """Configuration for bridge manager."""
    enabled: bool = True
    health_check_interval: int = 60
    auto_reconnect: bool = True
    max_reconnect_attempts: int = 5
    message_queue_size: int = 100


class BridgeManager:
    """
    Manages protocol bridges for Meshloom.
    
    Handles bridge lifecycle, message routing, and health monitoring.
    """
    
    def __init__(self, config: Optional[BridgeManagerConfig] = None) -> None:
        self._config = config or BridgeManagerConfig()
        self._bridges: Dict[str, Bridge] = {}
        self._message_handlers: List[Callable[[BridgeMessage, str], None]] = []
        self._running = False
        self._health_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

    @property
    def bridges(self) -> Dict[str, Bridge]:
        """Get all bridges."""
        return self._bridges.copy()

    def register_bridge(self, bridge: Bridge) -> None:
        """
        Register a bridge with the manager.
        
        Args:
            bridge: Bridge to register
        """
        with self._lock:
            self._bridges[bridge.bridge_id] = bridge
            logger.info(f"Registered bridge: {bridge.bridge_id}")

    def unregister_bridge(self, bridge_id: str) -> None:
        """
        Unregister a bridge.
        
        Args:
            bridge_id: Bridge ID to unregister
        """
        with self._lock:
            if bridge_id in self._bridges:
                del self._bridges[bridge_id]
                logger.info(f"Unregistered bridge: {bridge_id}")

    def get_bridge(self, bridge_id: str) -> Optional[Bridge]:
        """
        Get a bridge by ID.
        
        Args:
            bridge_id: Bridge ID
            
        Returns:
            Bridge or None
        """
        return self._bridges.get(bridge_id)

    def get_bridge_by_type(self, protocol: str) -> Optional[Bridge]:
        """
        Get a bridge by protocol type.
        
        Args:
            protocol: Protocol name (xmpp, matrix, etc.)
            
        Returns:
            Bridge or None
        """
        bridge_id = f"{protocol}_bridge"
        return self._bridges.get(bridge_id)

    def add_message_handler(
        self, handler: Callable[[BridgeMessage, str], None]
    ) -> None:
        """
        Add a message handler.
        
        Args:
            handler: Callback function (message, bridge_id)
        """
        self._message_handlers.append(handler)

    def remove_message_handler(
        self, handler: Callable[[BridgeMessage, str], None]
    ) -> None:
        """
        Remove a message handler.
        
        Args:
            handler: Handler to remove
        """
        if handler in self._message_handlers:
            self._message_handlers.remove(handler)

    def _handle_received_message(
        self, message: BridgeMessage, bridge_id: str
    ) -> None:
        """Process received message through handlers."""
        for handler in self._message_handlers:
            try:
                handler(message, bridge_id)
            except Exception as e:
                logger.error(f"Message handler error: {e}")

    def connect_all(self) -> Dict[str, bool]:
        """
        Connect all enabled bridges.
        
        Returns:
            Dict of bridge_id to success
        """
        results = {}
        for bridge_id, bridge in self._bridges.items():
            if bridge.config.enabled:
                try:
                    results[bridge_id] = bridge.connect()
                except Exception as e:
                    logger.error(f"Bridge {bridge_id} connect error: {e}")
                    results[bridge_id] = False
        return results

    def disconnect_all(self) -> Dict[str, bool]:
        """
        Disconnect all bridges.
        
        Returns:
            Dict of bridge_id to success
        """
        results = {}
        for bridge_id, bridge in self._bridges.items():
            try:
                results[bridge_id] = bridge.disconnect()
            except Exception as e:
                logger.error(f"Bridge {bridge_id} disconnect error: {e}")
                results[bridge_id] = False
        return results

    def send_message(
        self, message: BridgeMessage, bridge_id: Optional[str] = None
    ) -> bool:
        """
        Send a message through a bridge.
        
        Args:
            message: Message to send
            bridge_id: Optional specific bridge, otherwise uses recipient
            
        Returns:
            True if send successful
        """
        if bridge_id:
            bridge = self._bridges.get(bridge_id)
            if bridge:
                return bridge.send(message)
            return False
        
        return False

    def receive_all(self) -> Dict[str, List[BridgeMessage]]:
        """
        Receive messages from all connected bridges.
        
        Returns:
            Dict of bridge_id to messages
        """
        results = {}
        for bridge_id, bridge in self._bridges.items():
            if bridge.is_connected:
                try:
                    messages = bridge.receive()
                    if messages:
                        results[bridge_id] = messages
                        for msg in messages:
                            self._handle_received_message(msg, bridge_id)
                except Exception as e:
                    logger.error(f"Bridge {bridge_id} receive error: {e}")
        return results

    def get_all_contacts(self) -> Dict[str, List[BridgeContact]]:
        """
        Get contacts from all connected bridges.
        
        Returns:
            Dict of bridge_id to contacts
        """
        results = {}
        for bridge_id, bridge in self._bridges.items():
            if bridge.is_connected:
                try:
                    contacts = bridge.get_contacts()
                    if contacts:
                        results[bridge_id] = contacts
                except Exception as e:
                    logger.error(f"Bridge {bridge_id} get_contacts error: {e}")
        return results

    def start(self) -> None:
        """Start bridge manager."""
        if self._running:
            return
        
        self._running = True
        self.connect_all()
        
        if self._config.health_check_interval > 0:
            self._health_thread = threading.Thread(
                target=self._health_monitor,
                daemon=True
            )
            self._health_thread.start()
        
        logger.info("Bridge manager started")

    def stop(self) -> None:
        """Stop bridge manager."""
        self._running = False
        self.disconnect_all()
        
        if self._health_thread:
            self._health_thread.join(timeout=5)
        
        logger.info("Bridge manager stopped")

    def _health_monitor(self) -> None:
        """Background health monitoring."""
        import time
        
        while self._running:
            time.sleep(self._config.health_check_interval)
            
            for bridge_id, bridge in self._bridges.items():
                if not bridge.config.enabled:
                    continue
                
                if bridge.is_connected:
                    try:
                        if not bridge.health_check():
                            logger.warning(
                                f"Bridge {bridge_id} health check failed, reconnecting"
                            )
                            if self._config.auto_reconnect:
                                bridge.connect()
                    except Exception as e:
                        logger.error(f"Bridge {bridge_id} health check error: {e}")

    def get_status(self) -> Dict[str, dict]:
        """
        Get status of all bridges.
        
        Returns:
            Dict of bridge_id to status info
        """
        results = {}
        for bridge_id, bridge in self._bridges.items():
            results[bridge_id] = {
                "state": bridge.state.value,
                "connected": bridge.is_connected,
                "last_error": bridge.last_error,
            }
        return results
