"""
Network Service for Meshloom.

Uses RNS (Reticulum Network Stack) for peer-to-peer networking:
- Identity management (load or create cryptographic identity)
- Peer discovery via announces
- Request handlers for sync operations
- Thread-based announcement loop
"""

import json
import os
import socket
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import RNS
from RNS.Destination import Destination

from .peer import Peer


APP_NAME = "meshloom"
PEER_ASPECT = "peers"
PATH_STATUS = "/status"
PATH_SYNC_INDEX = "/sync/index"
PATH_SYNC_FILE = "/sync/file"


class NetworkService:
    """
    Network service for Meshloom using RNS (Reticulum Network Stack).
    
    Provides:
    - Identity management (load from file or create new)
    - Peer discovery via announces
    - Request handlers for status, file index, and file data
    - Thread-safe peer storage
    - Event publishing for peer updates
    
    Args:
        config: Configuration object with RNS settings
        diagnostics: Diagnostics instance for logging
    """
    
    def __init__(self, config: Any, diagnostics: Any) -> None:
        self._config = config
        self._diag = diagnostics
        
        self._reticulum: Optional[Any] = None
        self._identity: Optional[RNS.Identity] = None
        self._destination: Optional[Destination] = None
        
        self._peers: Dict[str, Peer] = {}
        self._peers_lock = threading.Lock()
        
        self._running = False
        self._event_loop: Optional[Any] = None
        
        self._announce_interval = config.get("reticulum.announce_interval", 30)
        self._peer_timeout = 300
        
        self._identity_path = os.path.expanduser(
            config.get("reticulum.identity_path", "~/.meshloom/storage/identities/meshloom")
        )
        
        self._peer_callbacks: List[Callable[[Peer], None]] = []
        
        self._index_generator: Optional[Callable[[], dict]] = None
        self._file_generator: Optional[Callable[[str], Optional[bytes]]] = None
    
    def register_peer_callback(self, callback: Callable[[Peer], None]) -> None:
        """Register a callback for peer discovery events."""
        self._peer_callbacks.append(callback)
    
    def register_index_handler(self, generator: Callable[[], dict]) -> None:
        """Register a function that returns the current file index."""
        self._index_generator = generator
    
    def register_file_handler(self, generator: Callable[[str], Optional[bytes]]) -> None:
        """Register a function that returns file data by path."""
        self._file_generator = generator
    
    async def start(self) -> None:
        """
        Start the network service.
        
        Initializes RNS, loads/creates identity, creates destination,
        registers announce handler, and starts announcement loop.
        """
        self._diag.info("network", "Starting network service")
        self._diag.checkpoint("network.start")
        
        try:
            await self._init_rns()
            self._diag.checkpoint("network.identity")
            
            threading.Thread(
                target=self._announce_loop,
                daemon=True,
                name="meshloom-announce"
            ).start()
            threading.Thread(
                target=self._peer_expiry_loop,
                daemon=True,
                name="meshloom-peer-expiry"
            ).start()
            
            self._running = True
            self._diag.info(
                "network",
                f"Network ready - identity: {self._identity.hash.hex()[:16]}..."
            )
            self._diag.checkpoint("network.ready")
            
        except Exception as e:
            self._diag.error("network", f"Failed to start network service: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the network service."""
        self._diag.info("network", "Stopping network service")
        self._running = False
    
    def is_running(self) -> bool:
        """Check if the network service is running."""
        return self._running
    
    async def _init_rns(self) -> None:
        """Initialize RNS and set up identity and destination."""
        config_path = os.path.expanduser("~/.reticulum")
        self._reticulum = RNS.Reticulum(config_path)
        
        self._load_or_create_identity()
        
        self._destination = Destination(
            self._identity,
            Destination.IN,
            Destination.SINGLE,
            APP_NAME,
            PEER_ASPECT,
        )
        self._destination.set_proof_strategy(Destination.PROVE_ALL)
        
        self._register_request_handlers()
        self._register_announce_handler()
        
        self._diag.info(
            "network",
            f"Destination created: {self._destination.hash.hex()[:16]}..."
        )
    
    def _load_or_create_identity(self) -> None:
        """Load existing identity or create a new one."""
        if os.path.exists(self._identity_path):
            self._identity = RNS.Identity.from_file(self._identity_path)
            self._diag.info(
                "network",
                f"Loaded identity: {self._identity.hash.hex()[:16]}..."
            )
        else:
            self._identity = RNS.Identity()
            os.makedirs(os.path.dirname(self._identity_path), exist_ok=True)
            self._identity.to_file(self._identity_path)
            self._diag.info("network", "Created new identity")
    
    def _register_request_handlers(self) -> None:
        """Register handlers for inbound requests."""
        self._destination.register_request_handler(
            path=PATH_STATUS,
            response_generator=self._handle_status_request,
            allow=Destination.ALLOW_ALL,
        )
        self._destination.register_request_handler(
            path=PATH_SYNC_INDEX,
            response_generator=self._handle_index_request,
            allow=Destination.ALLOW_ALL,
        )
        self._destination.register_request_handler(
            path=PATH_SYNC_FILE,
            response_generator=self._handle_file_request,
            allow=Destination.ALLOW_ALL,
        )
        self._diag.info(
            "network",
            "Request handlers registered: /status, /sync/index, /sync/file"
        )
    
    def _register_announce_handler(self) -> None:
        """Register handler for peer announcements."""
        class _AnnounceHandler:
            aspect_filter = None
            
            def __init__(self, service: "NetworkService") -> None:
                self.service = service
            
            def received_announce(
                self,
                destination_hash: Optional[Any] = None,
                announced_identity: Optional[RNS.Identity] = None,
                app_data: Optional[bytes] = None
            ) -> None:
                self.service._on_announce(
                    destination_hash, announced_identity, app_data
                )
        
        RNS.Transport.register_announce_handler(_AnnounceHandler(self))
        self._diag.info(
            "network",
            f"Announce handler registered for {APP_NAME}.{PEER_ASPECT}"
        )
    
    def _handle_status_request(
        self,
        path: str,
        data: Optional[bytes],
        req_id: Any,
        link_id: Any,
        remote_identity: Optional[RNS.Identity],
        requested_at: float
    ) -> bytes:
        """Handle /status request - return device status info."""
        try:
            hostname = socket.gethostname()
            status = {
                "hostname": hostname,
                "app": "Meshloom",
                "version": self._config.get("app.version", "0.1.0"),
                "peer_count": self.get_peer_count(),
                "uptime": self._get_uptime(),
            }
            return json.dumps(status).encode("utf-8")
        except Exception as e:
            self._diag.error("network", f"Status handler error: {e}")
            return json.dumps({"error": "internal_error"}).encode()
    
    def _handle_index_request(
        self,
        path: str,
        data: Optional[bytes],
        req_id: Any,
        link_id: Any,
        remote_identity: Optional[RNS.Identity],
        requested_at: float
    ) -> bytes:
        """Handle /sync/index request - return file list."""
        try:
            if self._index_generator:
                index = self._index_generator()
                return json.dumps(index).encode("utf-8")
            return json.dumps({}).encode("utf-8")
        except Exception as e:
            self._diag.error("network", f"Index handler error: {e}")
            return json.dumps({"error": "internal_error"}).encode()
    
    def _handle_file_request(
        self,
        path: str,
        data: Optional[bytes],
        req_id: Any,
        link_id: Any,
        remote_identity: Optional[RNS.Identity],
        requested_at: float
    ) -> Optional[bytes]:
        """Handle /sync/file request - return file data by path."""
        try:
            req_path = None
            if data:
                try:
                    req_data = json.loads(data.decode("utf-8"))
                    req_path = req_data.get("path")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
            
            if not req_path:
                return json.dumps({"error": "missing_path"}).encode()
            
            if self._file_generator:
                file_data = self._file_generator(req_path)
                if file_data is not None:
                    return file_data
                return json.dumps({"error": "file_not_found"}).encode()
            
            return json.dumps({"error": "no_handler"}).encode()
        except Exception as e:
            self._diag.error("network", f"File handler error: {e}")
            return json.dumps({"error": "internal_error"}).encode()
    
    def _on_announce(
        self,
        destination_hash: Any,
        announced_identity: Optional[RNS.Identity],
        app_data: Optional[bytes]
    ) -> None:
        """
        Handle incoming peer announcement.
        
        Args:
            destination_hash: Hash of announcing destination
            announced_identity: Identity of the peer
            app_data: Application data from announce (hostname, etc.)
        """
        if not announced_identity:
            return
        
        if announced_identity.hash == self._identity.hash:
            return
        
        peer_hash = (
            destination_hash.hex()
            if hasattr(destination_hash, "hex")
            else str(destination_hash)
        )
        
        expected_dest = Destination(
            announced_identity,
            Destination.OUT,
            Destination.SINGLE,
            APP_NAME,
            PEER_ASPECT,
        )
        expected_hash = (
            expected_dest.hash.hex()
            if hasattr(expected_dest.hash, "hex")
            else str(expected_dest.hash)
        )
        
        if peer_hash != expected_hash:
            return
        
        name = "unknown"
        if app_data:
            try:
                name = json.loads(app_data).get("name", "unknown")
            except (json.JSONDecodeError, UnicodeDecodeError):
                name = str(app_data)[:20]
        
        with self._peers_lock:
            is_new = peer_hash not in self._peers
            
            if is_new:
                out_dest = Destination(
                    announced_identity,
                    Destination.OUT,
                    Destination.SINGLE,
                    APP_NAME,
                    PEER_ASPECT,
                )
                self._peers[peer_hash] = Peer(
                    id=peer_hash,
                    name=name,
                    destination=out_dest,
                )
                self._diag.info("network", f"Peer discovered: {name}")
            else:
                self._peers[peer_hash].last_seen = time.time()
                self._peers[peer_hash].name = name
        
        if is_new:
            for callback in self._peer_callbacks:
                try:
                    with self._peers_lock:
                        peer = self._peers.get(peer_hash)
                    if peer:
                        callback(peer)
                except Exception as e:
                    self._diag.error("network", f"Peer callback error: {e}")
    
    def _announce_loop(self) -> None:
        """Periodically announce presence to the mesh."""
        hostname = socket.gethostname()
        app_data = json.dumps({
            "name": hostname,
            "status": "online",
        }).encode("utf-8")
        
        while self._running:
            try:
                if self._destination:
                    self._destination.announce(app_data=app_data)
                    self._diag.debug("network", f"Announced as {hostname}")
            except Exception as e:
                self._diag.error("network", f"Announce error: {e}")
            
            for _ in range(self._announce_interval * 10):
                if not self._running:
                    break
                time.sleep(0.1)
    
    def _peer_expiry_loop(self) -> None:
        """Remove peers that haven't announced recently."""
        while self._running:
            time.sleep(self._peer_timeout / 2)
            
            expired_ids = []
            with self._peers_lock:
                now = time.time()
                for pid, peer in list(self._peers.items()):
                    age = now - peer.last_seen.timestamp if hasattr(peer.last_seen, 'timestamp') else 0
                    if age > self._peer_timeout:
                        expired_ids.append(pid)
            
            for pid in expired_ids:
                with self._peers_lock:
                    peer = self._peers.pop(pid, None)
                if peer:
                    self._diag.info("network", f"Peer expired: {peer.name}")
    
    def get_peers(self) -> List[Peer]:
        """Get list of all known peers."""
        with self._peers_lock:
            return list(self._peers.values())
    
    def get_peer(self, peer_id: str) -> Optional[Peer]:
        """Get a specific peer by ID."""
        with self._peers_lock:
            return self._peers.get(peer_id)
    
    def get_peer_count(self) -> int:
        """Get the number of known peers."""
        with self._peers_lock:
            return len(self._peers)
    
    def get_status(self) -> Dict[str, Any]:
        """Get network service status."""
        return {
            "running": self._running,
            "peer_count": self.get_peer_count(),
            "identity": (
                self._identity.hash.hex()[:16] + "..."
                if self._identity else None
            ),
            "destination": (
                self._destination.hash.hex()[:16] + "..."
                if self._destination else None
            ),
        }
    
    def _get_uptime(self) -> str:
        """Get service uptime (placeholder)."""
        return "unknown"
    
    def create_link(self, peer_id: str) -> Optional[Any]:
        """
        Create an outbound RNS link to a peer.
        
        Args:
            peer_id: Hex string of peer destination hash
            
        Returns:
            RNS.Link object or None if peer not found
        """
        with self._peers_lock:
            peer = self._peers.get(peer_id)
        
        if not peer:
            self._diag.warn("network", f"create_link: peer {peer_id[:16]} not found")
            return None
        
        try:
            link = RNS.Link(peer.destination)
            self._diag.info("network", f"Created link to {peer.name}")
            return link
        except Exception as e:
            self._diag.error("network", f"create_link error: {e}")
            return None