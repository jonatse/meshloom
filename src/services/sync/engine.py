"""
Sync Engine for Meshloom.

Provides file synchronization between devices via shared directory:
- Scans local sync directory and builds file manifest
- Compares with remote peers to determine sync operations
- Transfers files via RNS links
- Uses last-writer-wins conflict resolution
"""

import asyncio
import hashlib
import json
import os
import shutil
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

vendor_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

import RNS

from ..peer import Peer
from .protocol import (
    FileEntry,
    FileManifest,
    MessageType,
    SyncMessage,
    SyncProtocol,
    compute_data_hash,
    compute_file_hash,
)


class SyncStatus:
    """Status constants for sync operations."""
    IDLE = "idle"
    SCANNING = "scanning"
    SYNCING = "syncing"
    ERROR = "error"


class TransferProgress:
    """Tracks progress of a file transfer."""
    def __init__(self, path: str, size: int, peer_id: str) -> None:
        self.path = path
        self.size = size
        self.transferred = 0
        self.peer_id = peer_id
        self.start_time = time.time()
        self.status = "pending"
    
    @property
    def percent(self) -> float:
        if self.size == 0:
            return 100.0
        return (self.transferred / self.size) * 100
    
    @property
    def speed(self) -> float:
        elapsed = time.time() - self.start_time
        if elapsed == 0:
            return 0
        return self.transferred / elapsed


class SyncEngine:
    """
    File synchronization engine for Meshloom.
    
    Syncs files between devices via shared directory using RNS for transfer.
    Last-writer-wins conflict resolution.
    
    Args:
        config: Configuration object with sync settings
        diagnostics: Diagnostics instance for logging
        network_service: NetworkService for peer communication
    """
    
    CHUNK_SIZE = 65536  # 64KB chunks for file transfer
    
    def __init__(
        self,
        config: Any,
        diagnostics: Any,
        network_service: Any,
    ) -> None:
        self._config = config
        self._diag = diagnostics
        self._network = network_service
        
        self._sync_dir = os.path.expanduser(
            config.get("sync.sync_dir", "~/MeshloomSync")
        )
        self._sync_interval = config.get("sync.sync_interval", 60)
        self._auto_sync = config.get("sync.auto_sync", True)
        
        self._running = False
        self._status = SyncStatus.IDLE
        self._last_sync: float = 0
        
        self._local_manifest = FileManifest()
        self._remote_manifests: Dict[str, FileManifest] = {}
        
        self._active_transfers: Dict[str, TransferProgress] = {}
        self._transfer_lock = threading.Lock()
        
        self._sync_callbacks: List[Callable[[str, Any], None]] = []
        self._sync_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
    
    @property
    def sync_dir(self) -> str:
        return self._sync_dir
    
    @property
    def status(self) -> str:
        return self._status
    
    @property
    def last_sync(self) -> float:
        return self._last_sync
    
    def register_sync_callback(self, callback: Callable[[str, Any], None]) -> None:
        """Register callback for sync events."""
        self._sync_callbacks.append(callback)
    
    def _notify_sync(self, event_type: str, data: Dict[str, Any]) -> None:
        """Notify sync callbacks of events."""
        for callback in self._sync_callbacks:
            try:
                callback(event_type, data)
            except Exception as e:
                self._diag.error("sync", f"Sync callback error: {e}")
    
    async def start(self) -> None:
        """
        Start the sync engine.
        
        Creates sync directory if needed, registers with network service,
        and starts background sync loop.
        """
        self._diag.info("sync", f"Starting sync engine (dir: {self._sync_dir})")
        self._diag.checkpoint("sync.start")
        
        os.makedirs(self._sync_dir, exist_ok=True)
        
        self._network.register_peer_callback(self._on_peer_discovered)
        self._network.register_index_handler(self._get_local_manifest)
        
        self._running = True
        
        self._scan_local_files()
        self._diag.checkpoint("sync.local_scan")
        
        if self._auto_sync:
            self._sync_thread = threading.Thread(
                target=self._sync_loop,
                daemon=True,
                name="meshloom-sync"
            )
            self._sync_thread.start()
            self._diag.info("sync", f"Background sync started (interval: {self._sync_interval}s)")
        
        self._status = SyncStatus.IDLE
        self._diag.checkpoint("sync.ready")
        self._diag.info("sync", "Sync engine ready")
    
    async def stop(self) -> None:
        """Stop the sync engine."""
        self._diag.info("sync", "Stopping sync engine")
        self._running = False
        self._stop_event.set()
        
        if self._sync_thread and self._sync_thread.is_alive():
            self._sync_thread.join(timeout=5)
        
        self._status = SyncStatus.IDLE
        self._diag.info("sync", "Sync engine stopped")
    
    def _on_peer_discovered(self, peer: Peer) -> None:
        """Handle discovered peer - request their file list."""
        self._diag.info("sync", f"Peer discovered: {peer.name}, requesting file list")
        asyncio.create_task(self._request_filelist(peer))
    
    def _get_local_manifest(self) -> Dict[str, Any]:
        """Get local file manifest for network service."""
        return self._local_manifest.to_dict()
    
    def _scan_local_files(self) -> None:
        """Scan local sync directory and build manifest."""
        self._status = SyncStatus.SCANNING
        self._diag.debug("sync", "Scanning local files")
        
        self._local_manifest = FileManifest(timestamp=time.time())
        
        if not os.path.exists(self._sync_dir):
            return
        
        for root, dirs, files in os.walk(self._sync_dir):
            for filename in files:
                filepath = os.path.join(root, filename)
                rel_path = os.path.relpath(filepath, self._sync_dir)
                
                try:
                    stat = os.stat(filepath)
                    file_hash = compute_file_hash(filepath)
                    
                    self._local_manifest.add_file(
                        path=rel_path,
                        size=stat.st_size,
                        mtime=stat.st_mtime,
                        hash=file_hash,
                    )
                except Exception as e:
                    self._diag.warn("sync", f"Error scanning {rel_path}: {e}")
        
        self._diag.info("sync", f"Local scan complete: {len(self._local_manifest.files)} files")
    
    def _sync_loop(self) -> None:
        """Background sync loop."""
        while self._running and not self._stop_event.is_set():
            try:
                self._diag.debug("sync", "Background sync tick")
                asyncio.run(self.sync_now())
            except Exception as e:
                self._diag.error("sync", f"Sync loop error: {e}")
            
            for _ in range(self._sync_interval * 10):
                if self._stop_event.is_set():
                    break
                time.sleep(0.1)
    
    async def sync_now(self) -> None:
        """
        Trigger a sync operation immediately.
        
        Scans local files, compares with all known peers,
        and performs necessary transfers.
        """
        if not self._running:
            return
        
        self._status = SyncStatus.SYNCING
        self._notify_sync("sync.started", {"timestamp": time.time()})
        self._diag.info("sync", "Starting sync operation")
        
        try:
            self._scan_local_files()
            
            peers = self._network.get_peers()
            self._diag.info("sync", f"Syncing with {len(peers)} peers")
            
            for peer in peers:
                await self._sync_with_peer(peer)
            
            self._last_sync = time.time()
            self._status = SyncStatus.IDLE
            self._notify_sync("sync.completed", {"timestamp": self._last_sync})
            self._diag.info("sync", "Sync operation completed")
            
        except Exception as e:
            self._status = SyncStatus.ERROR
            self._notify_sync("sync.failed", {"error": str(e)})
            self._diag.error("sync", f"Sync failed: {e}")
    
    async def _sync_with_peer(self, peer: Peer) -> None:
        """Sync files with a specific peer."""
        await self._request_filelist(peer)
        
        remote_manifest = self._remote_manifests.get(peer.id)
        if not remote_manifest:
            return
        
        to_download: List[FileEntry] = []
        to_upload: List[FileEntry] = []
        
        for path, remote_entry in remote_manifest.files.items():
            if remote_entry.deleted:
                continue
            
            local_entry = self._local_manifest.get_file(path)
            
            if local_entry is None:
                to_download.append(remote_entry)
            elif local_entry.hash != remote_entry.hash:
                if remote_entry.mtime > local_entry.mtime:
                    to_download.append(remote_entry)
                else:
                    to_upload.append(local_entry)
        
        for entry in to_download:
            await self._download_file(peer, entry.path)
        
        for entry in to_upload:
            await self._upload_file(peer, entry.path)
        
        for path, remote_entry in remote_manifest.files.items():
            if remote_entry.deleted:
                local_entry = self._local_manifest.get_file(path)
                if local_entry and not local_entry.deleted:
                    self._delete_local_file(path)
    
    async def _request_filelist(self, peer: Peer) -> None:
        """Request file manifest from a peer."""
        self._diag.debug("sync", f"Requesting filelist from {peer.name}")
        
        try:
            link = self._network.create_link(peer.id)
            if not link:
                self._diag.warn("sync", f"Failed to create link to {peer.name}")
                return
            
            request = SyncProtocol.create_filelist_request()
            link.send(request.to_bytes())
            
            response = link.receive(timeout=10)
            if response:
                message = SyncMessage.from_bytes(response)
                if message and message.type == MessageType.FILELIST:
                    manifest = FileManifest.from_dict(message.payload)
                    self._remote_manifests[peer.id] = manifest
                    self._diag.info(
                        "sync",
                        f"Received filelist from {peer.name}: {len(manifest.files)} files"
                    )
            
            link.close()
            
        except Exception as e:
            self._diag.error("sync", f"Failed to get filelist from {peer.name}: {e}")
    
    async def _download_file(self, peer: Peer, path: str) -> None:
        """Download a file from a peer."""
        self._diag.info("sync", f"Downloading {path} from {peer.name}")
        
        try:
            link = self._network.create_link(peer.id)
            if not link:
                return
            
            remote_manifest = self._remote_manifests.get(peer.id)
            if not remote_manifest:
                link.close()
                return
            
            entry = remote_manifest.get_file(path)
            if not entry:
                link.close()
                return
            
            request = SyncProtocol.create_file_request(path)
            link.send(request.to_bytes())
            
            dest_path = os.path.join(self._sync_dir, path)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            progress = TransferProgress(path, entry.size, peer.id)
            with self._transfer_lock:
                self._active_transfers[path] = progress
            
            received_data = b""
            
            while True:
                response = link.receive(timeout=30)
                if not response:
                    break
                
                message = SyncMessage.from_bytes(response)
                if not message:
                    break
                
                if message.type == MessageType.FILE_DATA:
                    import base64
                    data = base64.b64decode(message.payload["data"])
                    received_data += data
                    
                    progress.transferred = len(received_data)
                    self._notify_sync(
                        "sync.progress",
                        {"path": path, "percent": progress.percent}
                    )
                
                elif message.type == MessageType.FILE_COMPLETE:
                    break
            
            if received_data:
                with open(dest_path, "wb") as f:
                    f.write(received_data)
                
                self._diag.info("sync", f"Downloaded {path}")
            
            with self._transfer_lock:
                self._active_transfers.pop(path, None)
            
            link.close()
            
        except Exception as e:
            self._diag.error("sync", f"Download failed for {path}: {e}")
            with self._transfer_lock:
                self._active_transfers.pop(path, None)
    
    async def _upload_file(self, peer: Peer, path: str) -> None:
        """Upload a file to a peer."""
        self._diag.info("sync", f"Uploading {path} to {peer.name}")
        
        try:
            link = self._network.create_link(peer.id)
            if not link:
                return
            
            local_entry = self._local_manifest.get_file(path)
            if not local_entry:
                link.close()
                return
            
            filepath = os.path.join(self._sync_dir, path)
            if not os.path.exists(filepath):
                link.close()
                return
            
            with open(filepath, "rb") as f:
                data = f.read()
            
            progress = TransferProgress(path, len(data), peer.id)
            with self._transfer_lock:
                self._active_transfers[path] = progress
            
            offset = 0
            while offset < len(data):
                chunk = data[offset:offset + self.CHUNK_SIZE]
                msg = SyncProtocol.create_file_data(
                    path=path,
                    data=chunk,
                    offset=offset,
                    total=len(data),
                )
                link.send(msg.to_bytes())
                offset += self.CHUNK_SIZE
                progress.transferred = offset
                
                self._notify_sync(
                    "sync.progress",
                    {"path": path, "percent": progress.percent}
                )
            
            complete_msg = SyncProtocol.create_file_complete(
                path=path,
                hash=local_entry.hash,
            )
            link.send(complete_msg.to_bytes())
            
            with self._transfer_lock:
                self._active_transfers.pop(path, None)
            
            link.close()
            self._diag.info("sync", f"Uploaded {path}")
            
        except Exception as e:
            self._diag.error("sync", f"Upload failed for {path}: {e}")
            with self._transfer_lock:
                self._active_transfers.pop(path, None)
    
    def _delete_local_file(self, path: str) -> None:
        """Delete a local file."""
        try:
            filepath = os.path.join(self._sync_dir, path)
            if os.path.exists(filepath):
                os.remove(filepath)
                self._diag.info("sync", f"Deleted local file: {path}")
        except Exception as e:
            self._diag.error("sync", f"Failed to delete {path}: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get sync engine status."""
        return {
            "running": self._running,
            "status": self._status,
            "sync_dir": self._sync_dir,
            "last_sync": self._last_sync,
            "local_file_count": len(self._local_manifest.files),
            "peer_count": len(self._remote_manifests),
            "active_transfers": len(self._active_transfers),
        }
    
    def get_active_transfers(self) -> List[Dict[str, Any]]:
        """Get list of active file transfers."""
        with self._transfer_lock:
            return [
                {
                    "path": t.path,
                    "size": t.size,
                    "transferred": t.transferred,
                    "percent": t.percent,
                    "speed": t.speed,
                    "peer_id": t.peer_id,
                    "status": t.status,
                }
                for t in self._active_transfers.values()
            ]
    
    def get_local_manifest(self) -> Dict[str, Any]:
        """Get local file manifest."""
        return self._local_manifest.to_dict()
    
    def get_remote_manifests(self) -> Dict[str, Dict[str, Any]]:
        """Get remote file manifests by peer."""
        return {
            peer_id: manifest.to_dict()
            for peer_id, manifest in self._remote_manifests.items()
        }
    
    def add_local_file(self, filepath: str) -> None:
        """Add or update a local file in the manifest."""
        abs_path = os.path.join(self._sync_dir, filepath)
        
        if not os.path.exists(abs_path):
            return
        
        try:
            stat = os.stat(abs_path)
            file_hash = compute_file_hash(abs_path)
            
            self._local_manifest.add_file(
                path=filepath,
                size=stat.st_size,
                mtime=stat.st_mtime,
                hash=file_hash,
            )
            self._diag.info("sync", f"Added local file: {filepath}")
            
        except Exception as e:
            self._diag.error("sync", f"Failed to add file {filepath}: {e}")
    
    def remove_local_file(self, filepath: str) -> None:
        """Remove a local file from the manifest (mark as deleted)."""
        self._local_manifest.remove_file(filepath)
        self._diag.info("sync", f"Removed local file: {filepath}")
    
    def trigger_sync(self) -> None:
        """Manually trigger a sync operation."""
        if self._running:
            threading.Thread(
                target=lambda: asyncio.run(self.sync_now()),
                daemon=True,
                name="meshloom-sync-manual"
            ).start()
