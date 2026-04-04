"""ATAK Bridge for Meshloom."""

import logging
import socket
import struct
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime

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
class ATAKConfig(BridgeConfig):
    """Configuration for ATAK bridge."""
    multicast_group: str = "239.2.2.1"
    multicast_port: int = 6969
    broadcast_port: int = 7878
    callsign: str = "MESHL"


@dataclass
class ATAKLocation:
    """GPS location from ATAK."""
    latitude: float
    longitude: float
    altitude: float = 0.0
    accuracy: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ATAKContact:
    """ATAK contact with location."""
    callsign: str
    uid: str
    status: str = "unknown"
    location: Optional[ATAKLocation] = None
    last_seen: datetime = field(default_factory=datetime.utcnow)


class ATAKBridge(Bridge):
    """
    Bridge to ATAK (Android Team Awareness Kit).
    
    Connects to cursor-on-target (CoT) tactical messaging.
    Uses Multicast UDP for mesh tactical chat.
    """
    
    def __init__(
        self,
        bridge_id: str = "atak_bridge",
        config: Optional[ATAKConfig] = None,
    ) -> None:
        super().__init__(bridge_id, config or ATAKConfig())
        self._sock: Optional[socket.socket] = None
        self._contacts: Dict[str, ATAKContact] = {}
        self._message_callbacks: List[callable] = []
        self._running = False

    @property
    def config(self) -> ATAKConfig:
        """Get ATAK configuration."""
        return self._config

    def connect(self) -> bool:
        """
        Connect to ATAK network.
        
        Returns:
            True if connection successful
        """
        try:
            self._set_state(ConnectionState.CONNECTING)
            
            self._sock = socket.socket(
                socket.AF_INET,
                socket.SOCK_DGRAM,
                socket.IPPROTO_UDP
            )
            
            self._sock.setsockopt(
                socket.SOL_SOCKET,
                socket.SO_REUSEADDR,
                1
            )
            
            self._sock.bind((
                "",
                self._config.multicast_port
            ))
            
            mreq = struct.pack(
                "4s",
                socket.inet_aton(self._config.multicast_group)
            ) + struct.pack("s", b"\0")
            
            self._sock.setsockopt(
                socket.IPPROTO_IP,
                socket.IP_ADD_MEMBERSHIP,
                mreq
            )
            
            self._sock.settimeout(1.0)
            
            self._running = True
            
            self._set_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            self._last_error = str(e)
            logger.error(f"ATAK connect error: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from ATAK network.
        
        Returns:
            True if disconnection successful
        """
        try:
            self._running = False
            
            if self._sock:
                self._sock.close()
                self._sock = None
            
            self._set_state(ConnectionState.DISCONNECTED)
            return True
        except Exception as e:
            self._last_error = str(e)
            return False

    def send(self, message: BridgeMessage) -> bool:
        """
        Send message via ATAK CoT.
        
        Args:
            message: Message to send
            
        Returns:
            True if send successful
        """
        if not self.is_connected or not self._sock:
            self._last_error = "Not connected"
            return False
        
        try:
            cot_xml = self._build_cot_message(message)
            
            self._sock.sendto(
                cot_xml.encode(),
                (self._config.multicast_group, self._config.multicast_port)
            )
            
            return True
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"ATAK send error: {e}")
            return False

    def receive(self) -> List[BridgeMessage]:
        """
        Receive messages from ATAK network.
        
        Returns:
            List of received messages
        """
        if not self.is_connected or not self._sock:
            return []
        
        messages = []
        
        try:
            while True:
                data, addr = self._sock.recvfrom(4096)
                
                if not data:
                    break
                
                msg = self._parse_cot_message(data)
                if msg:
                    messages.append(msg)
                    
        except socket.timeout:
            pass
        except Exception as e:
            logger.error(f"ATAK receive error: {e}")
        
        return messages

    def get_contacts(self) -> List[BridgeContact]:
        """
        Get ATAK contacts.
        
        Returns:
            List of contacts
        """
        contacts = []
        
        for contact in self._contacts.values():
            contacts.append(BridgeContact(
                user_id=contact.uid,
                display_name=contact.callsign,
                status=contact.status,
            ))
        
        return contacts

    def health_check(self) -> bool:
        """
        Check ATAK connection health.
        
        Returns:
            True if healthy
        """
        if not self.is_connected or not self._sock:
            return False
        
        try:
            test_msg = self._build_test_cot()
            self._sock.sendto(
                test_msg.encode(),
                (self._config.multicast_group, self._config.multicast_port)
            )
            return True
        except Exception:
            return False

    def broadcast_location(self, location: ATAKLocation) -> bool:
        """
        Broadcast location update.
        
        Args:
            location: GPS location
            
        Returns:
            True if broadcast successful
        """
        if not self.is_connected:
            return False
        
        try:
            cot_xml = self._build_location_cot(location)
            
            self._sock.sendto(
                cot_xml.encode(),
                (self._config.multicast_group, self._config.multicast_port)
            )
            
            return True
        except Exception as e:
            logger.error(f"ATAK broadcast location error: {e}")
            return False

    def add_message_callback(self, callback: callable) -> None:
        """Add message callback."""
        self._message_callbacks.append(callback)

    def remove_message_callback(self, callback: callable) -> None:
        """Remove message callback."""
        if callback in self._message_callbacks:
            self._message_callbacks.remove(callback)

    def _build_cot_message(self, message: BridgeMessage) -> str:
        """Build CoT XML message."""
        uid = message.sender.replace("@", "-").replace(".", "-")
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="{uid}" type="b-bf" how="m-g" 
time="{message.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
start="{message.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
stale="{message.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}">
<point lat="0.0" lon="0.0" hae="0.0" ce="9999999" le="9999999"/>
<detail><contact callsign="{message.sender}"/></detail>
</event>'''

    def _build_location_cot(self, location: ATAKLocation) -> str:
        """Build location CoT XML."""
        callsign = self._config.callsign
        uid = f"MESHL-LOC-{int(location.timestamp.timestamp())}"
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="{uid}" type="a-f-G" how="-"
time="{location.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
start="{location.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
stale="{location.timestamp.strftime('%Y-%m-%dT%H:%M:%S.000Z')}">
<point lat="{location.latitude}" lon="{location.longitude}" hae="{location.altitude}" ce="{location.accuracy}" le="{location.accuracy}"/>
<detail><contact callsign="{callsign}"/></detail>
</event>'''

    def _build_test_cot(self) -> str:
        """Build test CoT message."""
        uid = f"MESHL-TEST-{int(datetime.utcnow().timestamp())}"
        
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<event version="2.0" uid="{uid}" type="b-t" how="m-g" 
time="{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
start="{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
stale="{datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.000Z')}">
<point lat="0.0" lon="0.0" hae="0.0" ce="9999999" le="9999999"/>
</event>'''

    def _parse_cot_message(self, data: bytes) -> Optional[BridgeMessage]:
        """Parse CoT XML into BridgeMessage."""
        try:
            import xml.etree.ElementTree as ET
            
            root = ET.fromstring(data)
            
            msg_type = root.get("type", "")
            if not msg_type.startswith("b-"):
                return None
            
            detail = root.find("detail")
            if detail is not None:
                contact = detail.find("contact")
                if contact is not None:
                    sender = contact.get("callsign", "unknown")
                else:
                    sender = root.get("uid", "unknown")
            else:
                sender = root.get("uid", "unknown")
            
            point = root.find("point")
            if point is not None:
                lat = float(point.get("lat", 0))
                lon = float(point.get("lon", 0))
            else:
                lat = lon = 0
            
            time_str = root.get("time", "")
            
            return BridgeMessage(
                message_id=root.get("uid", ""),
                sender=sender,
                recipient=self._config.callsign,
                content=f"CoT:{msg_type} lat={lat} lon={lon}",
            )
            
        except Exception as e:
            logger.error(f"Parse CoT error: {e}")
            return None
