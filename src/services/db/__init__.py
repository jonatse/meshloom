"""Database service for Meshloom."""

from .manager import DatabaseManager
from .models import App, Device, Edge, Node, SyncLog

_db_manager: DatabaseManager = None


def get_db(config: dict = None) -> DatabaseManager:
    """Get or create database manager instance."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager(config)
    return _db_manager


def init_db(config: dict = None) -> DatabaseManager:
    """Initialize and return database manager."""
    global _db_manager
    _db_manager = DatabaseManager(config)
    _db_manager.initialize()
    return _db_manager


__all__ = ["DatabaseManager", "get_db", "init_db", "Node", "Edge", "App", "Device", "SyncLog"]
