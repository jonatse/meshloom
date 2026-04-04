"""
Sync protocol definitions for Meshloom file synchronization.

Wire protocol: JSON over RNS
Message types:
  REQUEST_FILELIST (1): Request file list from peer
  FILELIST (2): Respond with file manifest
  REQUEST_FILE (3): Request specific file
  FILE_DATA (4): Transfer file chunks
  FILE_COMPLETE (5): Confirm transfer complete
  DELETE_FILE (6): Delete file notification
"""

import json
import hashlib
from typing import Any, Dict, Optional
from dataclasses import dataclass, field
from enum import IntEnum


class MessageType(IntEnum):
    """Sync protocol message types."""
    REQUEST_FILELIST = 1
    FILELIST = 2
    REQUEST_FILE = 3
    FILE_DATA = 4
    FILE_COMPLETE = 5
    DELETE_FILE = 6


@dataclass
class FileEntry:
    """A file entry in the sync manifest."""
    path: str
    size: int
    mtime: float
    hash: str
    deleted: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "hash": self.hash,
            "deleted": self.deleted,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileEntry":
        return cls(
            path=data["path"],
            size=data["size"],
            mtime=data["mtime"],
            hash=data["hash"],
            deleted=data.get("deleted", False),
        )


@dataclass
class FileManifest:
    """A collection of file entries representing a peer's file state."""
    files: Dict[str, FileEntry] = field(default_factory=dict)
    timestamp: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "files": {path: entry.to_dict() for path, entry in self.files.items()},
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FileManifest":
        files = {
            path: FileEntry.from_dict(entry_data)
            for path, entry_data in data.get("files", {}).items()
        }
        return cls(
            files=files,
            timestamp=data.get("timestamp", 0.0),
        )
    
    def add_file(self, path: str, size: int, mtime: float, hash: str) -> None:
        self.files[path] = FileEntry(path=path, size=size, mtime=mtime, hash=hash)
    
    def remove_file(self, path: str) -> None:
        if path in self.files:
            self.files[path].deleted = True
    
    def get_file(self, path: str) -> Optional[FileEntry]:
        return self.files.get(path)


@dataclass
class SyncMessage:
    """A sync protocol message."""
    type: MessageType
    payload: Dict[str, Any]
    request_id: Optional[str] = None
    
    def to_bytes(self) -> bytes:
        data = {
            "type": int(self.type),
            "payload": self.payload,
        }
        if self.request_id:
            data["request_id"] = self.request_id
        return json.dumps(data).encode("utf-8")
    
    @classmethod
    def from_bytes(cls, data: bytes) -> Optional["SyncMessage"]:
        try:
            parsed = json.loads(data.decode("utf-8"))
            msg_type = MessageType(parsed.get("type", 0))
            return cls(
                type=msg_type,
                payload=parsed.get("payload", {}),
                request_id=parsed.get("request_id"),
            )
        except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
            return None


class SyncProtocol:
    """Protocol helpers for sync operations."""
    
    @staticmethod
    def create_filelist_request(request_id: Optional[str] = None) -> SyncMessage:
        return SyncMessage(
            type=MessageType.REQUEST_FILELIST,
            payload={},
            request_id=request_id,
        )
    
    @staticmethod
    def create_filelist_response(manifest: FileManifest, request_id: Optional[str] = None) -> SyncMessage:
        return SyncMessage(
            type=MessageType.FILELIST,
            payload=manifest.to_dict(),
            request_id=request_id,
        )
    
    @staticmethod
    def create_file_request(path: str, request_id: Optional[str] = None) -> SyncMessage:
        return SyncMessage(
            type=MessageType.REQUEST_FILE,
            payload={"path": path},
            request_id=request_id,
        )
    
    @staticmethod
    def create_file_data(path: str, data: bytes, offset: int, total: int, request_id: Optional[str] = None) -> SyncMessage:
        import base64
        return SyncMessage(
            type=MessageType.FILE_DATA,
            payload={
                "path": path,
                "data": base64.b64encode(data).decode("utf-8"),
                "offset": offset,
                "total": total,
            },
            request_id=request_id,
        )
    
    @staticmethod
    def create_file_complete(path: str, hash: str, request_id: Optional[str] = None) -> SyncMessage:
        return SyncMessage(
            type=MessageType.FILE_COMPLETE,
            payload={"path": path, "hash": hash},
            request_id=request_id,
        )
    
    @staticmethod
    def create_delete_notification(path: str, request_id: Optional[str] = None) -> SyncMessage:
        return SyncMessage(
            type=MessageType.DELETE_FILE,
            payload={"path": path},
            request_id=request_id,
        )


def compute_file_hash(file_path: str) -> str:
    """Compute SHA256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def compute_data_hash(data: bytes) -> str:
    """Compute SHA256 hash of bytes."""
    return hashlib.sha256(data).hexdigest()
