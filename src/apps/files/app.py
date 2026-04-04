"""Files app for Meshloom.

File sync and sharing app leveraging the sync engine.
"""

from src.apps.base import App
from src.apps.metadata import AppMetadata, AppCategory


APP_METADATA = AppMetadata(
    name="Files",
    description="File sync and sharing",
    category=AppCategory.PRODUCTIVITY,
    version="0.1.0",
    author="Meshloom",
    keywords=["files", "sync", "sharing"],
)


class Files(App):
    """Files app for managing file sync and sharing."""
    
    DEFAULT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS files (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        path TEXT NOT NULL,
        size INTEGER,
        hash TEXT,
        modified REAL,
        synced REAL,
        created REAL DEFAULT (strftime('%s', 'now'))
    );
    
    CREATE TABLE IF NOT EXISTS shares (
        id TEXT PRIMARY KEY,
        file_id TEXT NOT NULL,
        peer_id TEXT,
        created REAL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (file_id) REFERENCES files(id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_files_path ON files(path);
    CREATE INDEX IF NOT EXISTS idx_shares_file ON shares(file_id);
    """
    
    def __init__(self, metadata: AppMetadata, db=None) -> None:
        super().__init__(metadata, db)
        self._init_db(self.DEFAULT_SCHEMA)
    
    def on_install(self) -> bool:
        """Initialize the files database."""
        return True
    
    def on_start(self) -> bool:
        """Start the files app."""
        return True
    
    def on_stop(self) -> bool:
        """Stop the files app."""
        return True
    
    def on_uninstall(self) -> bool:
        """Uninstall the files app."""
        return True
    
    def add_file(self, path: str, name: str) -> str:
        """Add a file to track."""
        import uuid
        import os
        
        file_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO files (id, name, path, size, modified) VALUES (?, ?, ?, ?, ?)",
                (file_id, name, path, os.path.getsize(path) if os.path.exists(path) else 0, os.path.getmtime(path) if os.path.exists(path) else 0)
            )
        
        return file_id
    
    def remove_file(self, file_id: str) -> bool:
        """Remove a file from tracking."""
        with self.db() as conn:
            conn.execute("DELETE FROM files WHERE id = ?", (file_id,))
        return True
    
    def list_files(self) -> list:
        """List all tracked files."""
        with self.db() as conn:
            cursor = conn.execute("SELECT * FROM files ORDER BY created DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def share_file(self, file_id: str, peer_id: str = None) -> str:
        """Share a file with peers."""
        import uuid
        
        share_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO shares (id, file_id, peer_id) VALUES (?, ?, ?)",
                (share_id, file_id, peer_id)
            )
        
        return share_id
