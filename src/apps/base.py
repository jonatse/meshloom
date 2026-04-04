"""Base App class for Meshloom apps."""

import os
import sqlite3
from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Generator

from .metadata import AppMetadata, AppState, AppDependency


@dataclass
class AppContext:
    """Context provided to apps for accessing services."""
    app_id: str
    app_dir: Path
    data_dir: Path
    sync_dir: Path
    config: Dict[str, Any] = field(default_factory=dict)


class App(ABC):
    """
    Base class for all Meshloom apps.
    
    Apps inherit from this class and implement lifecycle methods.
    The framework handles:
    - App discovery and loading
    - Lifecycle management (install/uninstall/start/stop)
    - Service access
    - Data storage
    
    Attributes:
        metadata: App metadata
        state: Current app state
    """
    
    def __init__(self, metadata: AppMetadata) -> None:
        self._metadata = metadata
        self._state = AppState.INSTALLED
        self._context: Optional[AppContext] = None
        self._db_path: Optional[Path] = None
    
    @property
    def metadata(self) -> AppMetadata:
        """Get app metadata."""
        return self._metadata
    
    @property
    def state(self) -> AppState:
        """Get current app state."""
        return self._state
    
    @property
    def name(self) -> str:
        """Get app name."""
        return self._metadata.name
    
    @property
    def app_id(self) -> str:
        """Get app ID (lowercase name)."""
        return self._metadata.name.lower().replace(" ", "_")
    
    def _set_context(self, context: AppContext) -> None:
        """Set app context."""
        self._context = context
    
    def get_context(self) -> Optional[AppContext]:
        """Get app context."""
        return self._context
    
    @contextmanager
    def db(self) -> Generator[sqlite3.Connection, None, None]:
        """
        Get database connection for app data.
        
        Yields:
            SQLite connection
            
        Example:
            with self.db() as conn:
                conn.execute("INSERT INTO notes VALUES (?, ?)", (id, content))
        """
        if not self._db_path:
            raise RuntimeError("App not initialized")
        
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_db(self, schema: str) -> None:
        """Initialize app database."""
        if not self._context:
            raise RuntimeError("App context not set")
        
        self._db_path = self._context.data_dir / f"{self.app_id}.db"
        
        os.makedirs(self._context.data_dir, exist_ok=True)
        
        if not self._db_path.exists():
            conn = sqlite3.connect(str(self._db_path))
            try:
                conn.executescript(schema)
            finally:
                conn.close()
    
    def on_install(self) -> bool:
        """
        Called when app is installed.
        
        Override to perform installation tasks:
        - Initialize database schema
        - Set up default data
        - Request permissions
        
        Returns:
            True if installation successful
        """
        return True
    
    def on_uninstall(self) -> bool:
        """
        Called when app is uninstalled.
        
        Override to perform cleanup:
        - Remove database
        - Clean up cached data
        
        Returns:
            True if uninstallation successful
        """
        return True
    
    @abstractmethod
    def on_start(self) -> bool:
        """
        Called when app is started.
        
        Override to perform startup tasks:
        - Load data
        - Start background tasks
        - Register event handlers
        
        Returns:
            True if start successful
        """
        raise NotImplementedError
    
    @abstractmethod
    def on_stop(self) -> bool:
        """
        Called when app is stopped.
        
        Override to perform cleanup:
        - Save data
        - Stop background tasks
        - Unregister event handlers
        
        Returns:
            True if stop successful
        """
        raise NotImplementedError
    
    def get_data(self, key: str, default: Any = None) -> Any:
        """Get app configuration or data."""
        if not self._context:
            return default
        return self._context.config.get(key, default)
    
    def set_data(self, key: str, value: Any) -> None:
        """Set app configuration or data."""
        if self._context:
            self._context.config[key] = value
    
    def _get_version(self) -> str:
        """Get app version."""
        return self._metadata.version
    
    def __repr__(self) -> str:
        """String representation."""
        return f"<{self.__class__.__name__}({self.name}, {self._state.value})>"
