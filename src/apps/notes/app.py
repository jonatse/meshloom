"""Notes app for Meshloom.

Rich text notes app.
"""

from src.apps.base import App
from src.apps.metadata import AppMetadata, AppCategory


APP_METADATA = AppMetadata(
    name="Notes",
    description="Rich text notes",
    category=AppCategory.PRODUCTIVITY,
    version="0.1.0",
    author="Meshloom",
    keywords=["notes", "rich text", "writing"],
)


class Notes(App):
    """Notes app for managing rich text notes."""
    
    DEFAULT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT,
        format TEXT DEFAULT 'plain',
        tags TEXT,
        pinned INTEGER DEFAULT 0,
        modified REAL,
        created REAL DEFAULT (strftime('%s', 'now'))
    );
    
    CREATE INDEX IF NOT EXISTS idx_notes_title ON notes(title);
    CREATE INDEX IF NOT EXISTS idx_notes_modified ON notes(modified);
    CREATE INDEX IF NOT EXISTS idx_notes_pinned ON notes(pinned);
    """
    
    def __init__(self, metadata: AppMetadata, db=None) -> None:
        super().__init__(metadata, db)
        self._init_db(self.DEFAULT_SCHEMA)
    
    def on_install(self) -> bool:
        """Initialize the notes database."""
        return True
    
    def on_start(self) -> bool:
        """Start the notes app."""
        return True
    
    def on_stop(self) -> bool:
        """Stop the notes app."""
        return True
    
    def on_uninstall(self) -> bool:
        """Uninstall the notes app."""
        return True
    
    def create_note(self, title: str, content: str = "", format: str = "plain", tags: list = None) -> str:
        """Create a new note."""
        import uuid
        import time
        
        note_id = str(uuid.uuid4())
        tags_str = ",".join(tags) if tags else ""
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO notes (id, title, content, format, tags, modified) VALUES (?, ?, ?, ?, ?, ?)",
                (note_id, title, content, format, tags_str, time.time())
            )
        
        return note_id
    
    def update_note(self, note_id: str, title: str = None, content: str = None, tags: list = None) -> bool:
        """Update a note."""
        import time
        
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if tags is not None:
            updates.append("tags = ?")
            params.append(",".join(tags))
        
        if updates:
            updates.append("modified = ?")
            params.append(time.time())
            params.append(note_id)
            
            with self.db() as conn:
                conn.execute(
                    f"UPDATE notes SET {', '.join(updates)} WHERE id = ?",
                    params
                )
        
        return True
    
    def delete_note(self, note_id: str) -> bool:
        """Delete a note."""
        with self.db() as conn:
            conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
        return True
    
    def get_note(self, note_id: str) -> dict:
        """Get a note by ID."""
        with self.db() as conn:
            cursor = conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def list_notes(
        self,
        search: str = None,
        tag: str = None,
        pinned: bool = None,
        limit: int = 100,
    ) -> list:
        """List notes with optional filters."""
        query = "SELECT * FROM notes WHERE 1=1"
        params = []
        
        if search:
            query += " AND (title LIKE ? OR content LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])
        
        if tag:
            query += " AND tags LIKE ?"
            params.append(f"%{tag}%")
        
        if pinned is not None:
            query += " AND pinned = ?"
            params.append(1 if pinned else 0)
        
        query += " ORDER BY pinned DESC, modified DESC LIMIT ?"
        params.append(limit)
        
        with self.db() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def pin_note(self, note_id: str, pinned: bool = True) -> bool:
        """Pin or unpin a note."""
        with self.db() as conn:
            conn.execute(
                "UPDATE notes SET pinned = ? WHERE id = ?",
                (1 if pinned else 0, note_id)
            )
        return True
