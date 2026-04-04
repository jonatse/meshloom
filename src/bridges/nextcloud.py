"""Nextcloud Bridge for Meshloom."""

import logging
import base64
import json
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
class NextcloudConfig(BridgeConfig):
    """Configuration for Nextcloud bridge."""
    protocol: str = "https"


@dataclass
class NextcloudUser:
    """Nextcloud user information."""
    uid: str
    display_name: str
    email: Optional[str] = None
    groups: List[str] = field(default_factory=list)


class NextcloudBridge(Bridge):
    """
    Bridge to Nextcloud servers.
    
    Connects to Nextcloud for file sync, contacts, calendar, and Talk.
    """
    
    def __init__(
        self,
        bridge_id: str = "nextcloud_bridge",
        config: Optional[NextcloudConfig] = None,
    ) -> None:
        super().__init__(bridge_id, config or NextcloudConfig())
        self._session = None
        self._user: Optional[NextcloudUser] = None
        self._capabilities: Dict[str, Any] = {}

    @property
    def config(self) -> NextcloudConfig:
        """Get Nextcloud configuration."""
        return self._config

    def connect(self) -> bool:
        """
        Connect to Nextcloud server.
        
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
            
            import requests
            from requests.auth import HTTPBasicAuth
            
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            self._session = requests.Session()
            self._session.auth = HTTPBasicAuth(
                self._config.username,
                self._config.password
            )
            
            response = self._session.get(
                f"{base_url}/ocs/v1.php/cloud/capabilities",
                headers={"OCS-APIREQUEST": "true"},
                timeout=self._config.timeout,
            )
            
            if response.status_code != 200:
                self._set_state(ConnectionState.ERROR)
                self._last_error = "Authentication failed"
                return False
            
            data = response.json()
            self._capabilities = data.get("ocs", {}).get("data", {})
            
            self._fetch_user()
            
            self._set_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            self._last_error = str(e)
            logger.error(f"Nextcloud connect error: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from Nextcloud server.
        
        Returns:
            True if disconnection successful
        """
        if self._session:
            self._session.close()
        
        self._set_state(ConnectionState.DISCONNECTED)
        return True

    def send(self, message: BridgeMessage) -> bool:
        """
        Send message via Nextcloud Talk.
        
        Args:
            message: Message to send
            
        Returns:
            True if send successful
        """
        if not self.is_connected:
            self._last_error = "Not connected"
            return False
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            room_id = self._get_or_create_room(message.recipient)
            if not room_id:
                self._last_error = "Could not get or create room"
                return False
            
            response = self._session.post(
                f"{base_url}/ocs/v2.php/apps/siren/{room_id}/message",
                json={"message": message.content},
                headers={"OCS-APIREQUEST": "true"},
            )
            
            return response.status_code == 200
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Nextcloud send error: {e}")
            return False

    def receive(self) -> List[BridgeMessage]:
        """
        Receive messages from Nextcloud Talk.
        
        Returns:
            List of received messages
        """
        if not self.is_connected:
            return []
        
        messages = []
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            response = self._session.get(
                f"{base_url}/ocs/v2.php/apps/siren/",
                params={"limit": 50},
                headers={"OCS-APIREQUEST": "true"},
            )
            
            if response.status_code == 200:
                data = response.json()
                for msg in data.get("ocs", {}).get("data", []):
                    messages.append(BridgeMessage(
                        message_id=str(msg.get("id", "")),
                        sender=msg.get("actor", {}).get("id", ""),
                        recipient=self._user.uid if self._user else "",
                        content=msg.get("message", ""),
                    ))
                    
        except Exception as e:
            logger.error(f"Nextcloud receive error: {e}")
        
        return messages

    def get_contacts(self) -> List[BridgeContact]:
        """
        Get Nextcloud contacts.
        
        Returns:
            List of contacts
        """
        if not self.is_connected:
            return []
        
        contacts = []
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            response = self._session.get(
                f"{base_url}/ocs/v1.php/cloud/users",
                headers={"OCS-APIREQUEST": "true"},
            )
            
            if response.status_code == 200:
                data = response.json()
                for user in data.get("ocs", {}).get("data", []):
                    contacts.append(BridgeContact(
                        user_id=user.get("id", ""),
                        display_name=user.get("id", ""),
                    ))
                    
        except Exception as e:
            logger.error(f"Get contacts error: {e}")
        
        return contacts

    def health_check(self) -> bool:
        """
        Check Nextcloud connection health.
        
        Returns:
            True if healthy
        """
        if not self.is_connected or not self._session:
            return False
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            response = self._session.get(
                f"{base_url}/status.php",
                timeout=10,
            )
            
            return response.status_code == 200
        except Exception:
            return False

    def _fetch_user(self) -> None:
        """Fetch current user info."""
        if not self._session:
            return
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            response = self._session.get(
                f"{base_url}/ocs/v1.php/cloud/user",
                headers={"OCS-APIREQUEST": "true"},
            )
            
            if response.status_code == 200:
                data = response.json()
                user_data = data.get("ocs", {}).get("data", {})
                self._user = NextcloudUser(
                    uid=user_data.get("id", ""),
                    display_name=user_data.get("display-name", ""),
                    email=user_data.get("email"),
                )
                
        except Exception as e:
            logger.error(f"Fetch user error: {e}")

    def _get_or_create_room(self, recipient: str) -> Optional[str]:
        """Get or create a Talk room."""
        if not self._session:
            return None
        
        try:
            server = self._config.server
            protocol = self._config.protocol
            base_url = f"{protocol}://{server}"
            
            response = self._session.get(
                f"{base_url}/ocs/v2.php/apps/siren/",
                headers={"OCS-APIREQUEST": "true"},
            )
            
            if response.status_code == 200:
                data = response.json()
                for room in data.get("ocs", {}).get("data", []):
                    if room.get("name") == recipient:
                        return room.get("id")
            
            response = self._session.post(
                f"{base_url}/ocs/v2.php/apps/siren/",
                json={"roomType": 1, "invite": {"u": recipient}},
                headers={"OCS-APIREQUEST": "true"},
            )
            
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("ocs", {}).get("data", {}).get("token")
                
        except Exception as e:
            logger.error(f"Get or create room error: {e}")
        
        return None
