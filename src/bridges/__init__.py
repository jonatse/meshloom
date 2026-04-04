"""Protocol bridges for Meshloom.

Bridges connect Meshloom to external networks:
- XMPP: Connect to XMPP/Jabber networks
- Matrix: Connect to Matrix homeservers  
- Nextcloud: Federation with Nextcloud servers
- ATAK: Tactical messaging (cursor-on-target)
"""

from .base import (
    Bridge,
    BridgeConfig,
    BridgeContact,
    BridgeError,
    BridgeMessage,
    ConnectionError,
    ConnectionState,
    MessageError,
)

from .manager import BridgeManager, BridgeManagerConfig

from .xmpp import XMPPBridge, XMPPConfig

from .matrix import MatrixBridge, MatrixConfig

from .nextcloud import NextcloudBridge, NextcloudConfig, NextcloudUser

from .atak import ATAKBridge, ATAKConfig, ATAKContact, ATAKLocation


__all__ = [
    # Base
    "Bridge",
    "BridgeConfig",
    "BridgeContact",
    "BridgeError",
    "BridgeMessage",
    "ConnectionError",
    "ConnectionState",
    "MessageError",
    # Manager
    "BridgeManager",
    "BridgeManagerConfig",
    # XMPP
    "XMPPBridge",
    "XMPPConfig",
    # Matrix
    "MatrixBridge",
    "MatrixConfig",
    # Nextcloud
    "NextcloudBridge",
    "NextcloudConfig",
    "NextcloudUser",
    # ATAK
    "ATAKBridge",
    "ATAKConfig",
    "ATAKContact",
    "ATAKLocation",
]
