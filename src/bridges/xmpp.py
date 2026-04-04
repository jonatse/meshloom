"""XMPP Bridge for Meshloom."""

import logging
import threading
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

from .base import (
    Bridge,
    BridgeConfig,
    BridgeContact,
    BridgeError,
    BridgeMessage,
    ConnectionError,
    ConnectionState,
)

logger = logging.getLogger(__name__)


@dataclass
class XMPPConfig(BridgeConfig):
    """Configuration for XMPP bridge."""
    resource: str = "meshloom"
    priority: int = 5
    legacy_ssl: bool = False


class XMPPBridge(Bridge):
    """
    Bridge to XMPP networks.
    
    Connects to XMPP servers (Jabber) for instant messaging.
    """
    
    def __init__(
        self,
        bridge_id: str = "xmpp_bridge",
        config: Optional[XMPPConfig] = None,
    ) -> None:
        super().__init__(bridge_id, config or XMPPConfig())
        self._client = None
        self._roster: Dict[str, BridgeContact] = {}
        self._message_callbacks: List[callable] = []
        self._ready = threading.Event()

    @property
    def config(self) -> XMPPConfig:
        """Get XMPP configuration."""
        return self._config

    def connect(self) -> bool:
        """
        Connect to XMPP server.
        
        Returns:
            True if connection successful
        """
        if not self._config.server:
            self._last_error = "No server configured"
            return False
        
        if not self._config.username or not self._config.password:
            self._last_error = "No credentials configured"
            return False
        
        try:
            self._set_state(ConnectionState.CONNECTING)
            
            self._client = self._create_client()
            
            self._client.add_event_handler(
                "session_start", self._on_session_start
            )
            self._client.add_event_handler(
                "message", self._on_message
            )
            self._client.add_event_handler(
                "presence", self._on_presence
            )
            self._client.add_event_handler(
                "connection_failed", self._on_connection_failed
            )
            self._client.add_event_handler(
                "disconnected", self._on_disconnected
            )
            
            self._client.connect()
            
            timeout = self._config.timeout
            if not self._ready.wait(timeout=timeout):
                self._set_state(ConnectionState.ERROR)
                self._last_error = "Connection timeout"
                return False
            
            self._set_state(ConnectionState.CONNECTED)
            self._fetch_roster()
            
            return True
            
        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            self._last_error = str(e)
            logger.error(f"XMPP connect error: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from XMPP server.
        
        Returns:
            True if disconnection successful
        """
        try:
            if self._client:
                self._client.disconnect()
            self._set_state(ConnectionState.DISCONNECTED)
            return True
        except Exception as e:
            self._last_error = str(e)
            return False

    def send(self, message: BridgeMessage) -> bool:
        """
        Send message via XMPP.
        
        Args:
            message: Message to send
            
        Returns:
            True if send successful
        """
        if not self.is_connected:
            self._last_error = "Not connected"
            return False
        
        try:
            msg = self._create_message(
                mto=message.recipient,
                mtype="chat",
                mbody=message.content,
            )
            
            if message.thread_id:
                msg["thread"] = message.thread_id
            
            self._client.send_message(msg)
            return True
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"XMPP send error: {e}")
            return False

    def receive(self) -> List[BridgeMessage]:
        """
        Receive messages from XMPP.
        
        Returns:
            List of received messages
        """
        return []

    def get_contacts(self) -> List[BridgeContact]:
        """
        Get XMPP roster.
        
        Returns:
            List of contacts
        """
        return list(self._roster.values())

    def health_check(self) -> bool:
        """
        Check XMPP connection health.
        
        Returns:
            True if healthy
        """
        if not self.is_connected or not self._client:
            return False
        
        try:
            if self._client.is_connected():
                self._client.send_presence()
                return True
        except Exception:
            pass
        
        return False

    def _create_client(self) -> Any:
        """Create XMPP client instance."""
        from sleekxmpp import ClientXMPP
        
        jid = f"{self._config.username}@{self._config.server}"
        if self._config.resource:
            jid += f"/{self._config.resource}"
        
        client = ClientXMPP(jid, self._config.password)
        
        client.register_plugin("xep_0030")
        client.register_plugin("xep_0199")
        
        return client

    def _create_message(self, **kwargs: Any) -> Any:
        """Create XMPP message stanza."""
        return self._client.Message(**kwargs)

    def _on_session_start(self, event: Any) -> None:
        """Handle session start."""
        self._client.send_presence()
        self._ready.set()

    def _on_message(self, event: Any) -> None:
        """Handle incoming message."""
        msg = event["message"]
        
        if msg["type"] in ("chat", "normal"):
            body = msg["body"]
            if body:
                message = BridgeMessage(
                    message_id=msg["id"],
                    sender=str(msg["from"]),
                    recipient=str(msg["to"]),
                    content=body,
                    thread_id=msg.get("thread"),
                )
                
                for callback in self._message_callbacks:
                    try:
                        callback(message)
                    except Exception as e:
                        logger.error(f"Message callback error: {e}")

    def _on_presence(self, event: Any) -> None:
        """Handle presence updates."""
        pass

    def _on_connection_failed(self, event: Any) -> None:
        """Handle connection failure."""
        self._set_state(ConnectionState.ERROR)
        self._last_error = "Connection failed"
        self._ready.set()

    def _on_disconnected(self, event: Any) -> None:
        """Handle disconnection."""
        self._set_state(ConnectionState.DISCONNECTED)

    def _fetch_roster(self) -> None:
        """Fetch roster from server."""
        if not self._client:
            return
        
        try:
            roster = self._client.client_roster
            for jid in roster:
                contacts = roster.getContacts(jid)
                for contact in contacts:
                    self._roster[jid] = BridgeContact(
                        user_id=jid,
                        display_name=contact.get("name", jid),
                        status=contact.get("show", "offline"),
                    )
        except Exception as e:
            logger.error(f"Fetch roster error: {e}")

    def add_message_callback(self, callback: callable) -> None:
        """Add message callback."""
        self._message_callbacks.append(callback)

    def remove_message_callback(self, callback: callable) -> None:
        """Remove message callback."""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)
