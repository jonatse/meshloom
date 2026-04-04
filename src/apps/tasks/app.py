"""Tasks app for Meshloom.

Todo lists and reminders app.
"""

from src.apps.base import App
from src.apps.metadata import AppMetadata, AppCategory


APP_METADATA = AppMetadata(
    name="Tasks",
    description="Todo lists and reminders",
    category=AppCategory.PRODUCTIVITY,
    version="0.1.0",
    author="Meshloom",
    keywords=["tasks", "todo", "reminders", "checklist"],
)


class Tasks(App):
    """Tasks app for managing todo lists and reminders."""
    
    DEFAULT_SCHEMA = """
    CREATE TABLE IF NOT EXISTS lists (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        color TEXT,
        icon TEXT,
        modified REAL,
        created REAL DEFAULT (strftime('%s', 'now'))
    );
    
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        list_id TEXT NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        completed INTEGER DEFAULT 0,
        due_date REAL,
        priority INTEGER DEFAULT 0,
        position INTEGER DEFAULT 0,
        completed_at REAL,
        modified REAL,
        created REAL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (list_id) REFERENCES lists(id)
    );
    
    CREATE TABLE IF NOT EXISTS reminders (
        id TEXT PRIMARY KEY,
        task_id TEXT NOT NULL,
        remind_at REAL NOT NULL,
        notified INTEGER DEFAULT 0,
        created REAL DEFAULT (strftime('%s', 'now')),
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    );
    
    CREATE INDEX IF NOT EXISTS idx_tasks_list ON tasks(list_id);
    CREATE INDEX IF NOT EXISTS idx_tasks_due ON tasks(due_date);
    CREATE INDEX IF NOT EXISTS idx_reminders_task ON reminders(task_id);
    CREATE INDEX IF NOT EXISTS idx_reminders_time ON reminders(remind_at);
    """
    
    def __init__(self, metadata: AppMetadata, db=None) -> None:
        super().__init__(metadata, db)
        self._init_db(self.DEFAULT_SCHEMA)
    
    def on_install(self) -> bool:
        """Initialize the tasks database."""
        self._create_default_list()
        return True
    
    def _create_default_list(self) -> str:
        """Create a default inbox list."""
        import uuid
        
        list_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO lists (id, name, description) VALUES (?, ?, ?)",
                (list_id, "Inbox", "Default task list")
            )
        
        return list_id
    
    def on_start(self) -> bool:
        """Start the tasks app."""
        return True
    
    def on_stop(self) -> bool:
        """Stop the tasks app."""
        return True
    
    def on_uninstall(self) -> bool:
        """Uninstall the tasks app."""
        return True
    
    def create_list(self, name: str, description: str = "", color: str = None, icon: str = None) -> str:
        """Create a new task list."""
        import uuid
        import time
        
        list_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO lists (id, name, description, color, icon, modified) VALUES (?, ?, ?, ?, ?, ?)",
                (list_id, name, description, color, icon, time.time())
            )
        
        return list_id
    
    def get_lists(self) -> list:
        """Get all task lists."""
        with self.db() as conn:
            cursor = conn.execute("SELECT * FROM lists ORDER BY created DESC")
            return [dict(row) for row in cursor.fetchall()]
    
    def create_task(
        self,
        list_id: str,
        title: str,
        description: str = "",
        due_date: float = None,
        priority: int = 0,
    ) -> str:
        """Create a new task."""
        import uuid
        import time
        
        task_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO tasks (id, list_id, title, description, due_date, priority, modified) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, list_id, title, description, due_date, priority, time.time())
            )
        
        return task_id
    
    def update_task(
        self,
        task_id: str,
        title: str = None,
        description: str = None,
        completed: bool = None,
        due_date: float = None,
        priority: int = None,
    ) -> bool:
        """Update a task."""
        import time
        
        updates = []
        params = []
        
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        
        if description is not None:
            updates.append("description = ?")
            params.append(description)
        
        if completed is not None:
            updates.append("completed = ?")
            params.append(1 if completed else 0)
            if completed:
                updates.append("completed_at = ?")
                params.append(time.time())
        
        if due_date is not None:
            updates.append("due_date = ?")
            params.append(due_date)
        
        if priority is not None:
            updates.append("priority = ?")
            params.append(priority)
        
        if updates:
            updates.append("modified = ?")
            params.append(time.time())
            params.append(task_id)
            
            with self.db() as conn:
                conn.execute(
                    f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?",
                    params
                )
        
        return True
    
    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed."""
        return self.update_task(task_id, completed=True)
    
    def uncomplete_task(self, task_id: str) -> bool:
        """Mark a task as incomplete."""
        return self.update_task(task_id, completed=False)
    
    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with self.db() as conn:
            conn.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        return True
    
    def get_tasks(
        self,
        list_id: str = None,
        completed: bool = None,
        due_before: float = None,
        due_after: float = None,
        limit: int = 100,
    ) -> list:
        """Get tasks with optional filters."""
        query = "SELECT * FROM tasks WHERE 1=1"
        params = []
        
        if list_id:
            query += " AND list_id = ?"
            params.append(list_id)
        
        if completed is not None:
            query += " AND completed = ?"
            params.append(1 if completed else 0)
        
        if due_before:
            query += " AND due_date < ?"
            params.append(due_before)
        
        if due_after:
            query += " AND due_date > ?"
            params.append(due_after)
        
        query += " ORDER BY priority DESC, position ASC, created DESC LIMIT ?"
        params.append(limit)
        
        with self.db() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def get_task(self, task_id: str) -> dict:
        """Get a task by ID."""
        with self.db() as conn:
            cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def add_reminder(self, task_id: str, remind_at: float) -> str:
        """Add a reminder for a task."""
        import uuid
        
        reminder_id = str(uuid.uuid4())
        
        with self.db() as conn:
            conn.execute(
                "INSERT INTO reminders (id, task_id, remind_at) VALUES (?, ?, ?)",
                (reminder_id, task_id, remind_at)
            )
        
        return reminder_id
    
    def get_due_reminders(self, before: float = None) -> list:
        """Get pending reminders."""
        import time
        
        query = "SELECT * FROM reminders WHERE notified = 0"
        params = []
        
        if before:
            query += " AND remind_at < ?"
            params.append(before)
        else:
            query += " AND remind_at < ?"
            params.append(time.time())
        
        with self.db() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]
    
    def mark_reminder_notified(self, reminder_id: str) -> bool:
        """Mark a reminder as notified."""
        with self.db() as conn:
            conn.execute(
                "UPDATE reminders SET notified = 1 WHERE id = ?",
                (reminder_id,)
            )
        return True
