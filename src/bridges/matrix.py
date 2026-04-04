"""Matrix Bridge for Meshloom."""

import logging
import asyncio
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
class MatrixConfig(BridgeConfig):
    """Configuration for Matrix bridge."""
    device_id: str = "Meshloom"
    sync_filter: Optional[str] = None


class MatrixBridge(Bridge):
    """
    Bridge to Matrix homeservers.
    
    Connects to Matrix servers for decentralized chat.
    """
    
    def __init__(
        self,
        bridge_id: str = "matrix_bridge",
        config: Optional[MatrixConfig] = None,
    ) -> None:
        super().__init__(bridge_id, config or MatrixConfig())
        self._client = None
        self._rooms: Dict[str, Any] = {}
        self._room_callbacks: Dict[str, List[callable]] = {}
        self._task: Optional[asyncio.Task] = None

    @property
    def config(self) -> MatrixConfig:
        """Get Matrix configuration."""
        return self._config

    def connect(self) -> bool:
        """
        Connect to Matrix homeserver.
        
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
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            from aiohttp import ClientSession
            from matrixclient import Client
            
            server = f"https://{self._config.server}"
            self._client = Client(server)
            
            loop.run_until_complete(
                self._client.login(self._config.password)
            )
            
            self._task = loop.create_task(self._sync_loop(loop))
            
            self._set_state(ConnectionState.CONNECTED)
            return True
            
        except Exception as e:
            self._set_state(ConnectionState.ERROR)
            self._last_error = str(e)
            logger.error(f"Matrix connect error: {e}")
            return False

    def disconnect(self) -> bool:
        """
        Disconnect from Matrix homeserver.
        
        Returns:
            True if disconnection successful
        """
        try:
            if self._task:
                self._task.cancel()
            
            if self._client:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._client.close())
            
            self._set_state(ConnectionState.DISCONNECTED)
            return True
        except Exception as e:
            self._last_error = str(e)
            return False

    def send(self, message: BridgeMessage) -> bool:
        """
        Send message via Matrix.
        
        Args:
            message: Message to send
            
        Returns:
            True if send successful
        """
        if not self.is_connected:
            self._last_error = "Not connected"
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            room_id = self._resolve_room(message.recipient)
            if not room_id:
                self._last_error = "Room not found"
                return False
            
            loop.run_until_complete(
                self._client.room_send_message(room_id, message.content)
            )
            
            return True
            
        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Matrix send error: {e}")
            return False

    def receive(self) -> List[BridgeMessage]:
        """
        Receive messages from Matrix.
        
        Returns:
            List of received messages
        """
        return []

    def get_contacts(self) -> List[BridgeContact]:
        """
        Get joined members from Matrix.
        
        Returns:
            List of contacts
        """
        contacts = []
        
        try:
            for room in self._client.rooms:
                for member in room.get_joined_members():
                    contacts.append(BridgeContact(
                        user_id=member.user_id,
                        display_name=member.display_name or member.user_id,
                    ))
        except Exception as e:
            logger.error(f"Get contacts error: {e}")
        
        return contacts

    def health_check(self) -> bool:
        """
        Check Matrix connection health.
        
        Returns:
            True if healthy
        """
        if not self.is_connected or not self._client:
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            loop.run_until_complete(self._client.sync())
            return True
        except Exception:
            return False

    def join_room(self, room_alias: str) -> bool:
        """
        Join a Matrix room.
        
        Args:
            room_alias: Room alias or ID
            
        Returns:
            True if successful
        """
        if not self.is_connected:
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            room = loop.run_until_complete(
                self._client.join_room(room_alias)
            )
            
            self._rooms[room_alias] = room
            return True
        except Exception as e:
            logger.error(f"Join room error: {e}")
            return False

    def leave_room(self, room_alias: str) -> bool:
        """
        Leave a Matrix room.
        
        Args:
            room_alias: Room alias or ID
            
        Returns:
            True if successful
        """
        if room_alias not in self._rooms:
            return False
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            room = self._rooms[room_alias]
            loop.run_until_complete(room.leave())
            
            del self._rooms[room_alias]
            return True
        except Exception as e:
            logger.error(f"Leave room error: {e}")
            return False

    async def _sync_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Background sync loop."""
        while self._client and self.is_connected:
            try:
                await self._client.sync()
                await asyncio.sleep(self._config.ping_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Sync error: {e}")

    def _resolve_room(self, recipient: str) -> Optional[str]:
        """Resolve room alias to ID."""
        if recipient in self._rooms:
            return recipient
        
        for room_id, room in self._rooms.items():
            if hasattr(room, 'alias') and room.alias == recipient:
                return room_id
        
        return None
