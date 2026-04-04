"""Database manager for Meshloom with MariaDB support."""

import os
import subprocess
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from threading import Lock, Thread
from typing import Any, Dict, Generator, List, Optional

try:
    import pymysql
    from pymysql.cursors import DictCursor
    PYMYSQL_AVAILABLE = True
except ImportError:
    PYMYSQL_AVAILABLE = False

from .models import App, Device, Edge, Node, SyncLog
from .schema import INITIAL_SCHEMA


class DatabaseManager:
    """Manages database connections and embedded MariaDB server."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._data_dir = Path(os.path.expanduser(self._config.get("data_dir", "~/.meshloom/data")))
        self._run_dir = Path(os.path.expanduser(self._config.get("run_dir", "~/.meshloom/run")))
        
        self._host = self._config.get("host", "localhost")
        self._port = self._config.get("port", 3306)
        self._user = self._config.get("user", "meshloom")
        self._password = self._config.get("password", "")
        self._socket = self._config.get("socket", str(self._run_dir / "mariadb.sock"))
        self._database = self._config.get("database", "meshloom")
        
        self._mariadb_process: Optional[subprocess.Popen] = None
        self._mariadb_running = False
        self._mariadb_lock = Lock()
        self._initialized = False
        
        self._pool_size = self._config.get("pool_size", 5)
        
        self._ensure_directories()
    
    def _ensure_directories(self) -> None:
        """Ensure data and run directories exist."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._run_dir.mkdir(parents=True, exist_ok=True)
    
    @property
    def backend(self) -> str:
        """Get current backend."""
        return "mariadb"
    
    @property
    def is_mariadb_available(self) -> bool:
        """Check if PyMySQL is available."""
        return PYMYSQL_AVAILABLE
    
    @property
    def is_running(self) -> bool:
        """Check if database is running."""
        return self._mariadb_running
    
    def _start_mariadb(self) -> bool:
        """Start embedded MariaDB server."""
        if not PYMYSQL_AVAILABLE:
            return False
        
        with self._mariadb_lock:
            if self._mariadb_running:
                return True
            
            try:
                socket_dir = os.path.dirname(self._socket)
                os.makedirs(socket_dir, exist_ok=True)
                
                mariadb_data = self._data_dir / "mariadb"
                mariadb_data.mkdir(exist_ok=True)
                
                init_cmd = [
                    "mariadb-install-db",
                    f"--datadir={mariadb_data}",
                    f"--socket={self._socket}",
                    "--auth-root=socket",
                ]
                try:
                    subprocess.run(init_cmd, check=True, capture_output=True, timeout=30)
                except FileNotFoundError:
                    init_cmd = [
                        "mysql_install_db",
                        f"--datadir={mariadb_data}",
                        f"--socket={self._socket}",
                    ]
                    subprocess.run(init_cmd, check=True, capture_output=True, timeout=30)
                except subprocess.CalledProcessError:
                    pass
                
                server_cmd = [
                    "mariadbd",
                    f"--datadir={mariadb_data}",
                    f"--socket={self._socket}",
                    f"--port={self._port}",
                    "--skip-networking=0",
                    "--bind-address=127.0.0.1",
                ]
                try:
                    self._mariadb_process = subprocess.Popen(
                        server_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except FileNotFoundError:
                    server_cmd = [
                        "mysqld",
                        f"--datadir={mariadb_data}",
                        f"--socket={self._socket}",
                        f"--port={self._port}",
                    ]
                    self._mariadb_process = subprocess.Popen(
                        server_cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                
                for _ in range(30):
                    try:
                        conn = pymysql.connect(
                            unix_socket=self._socket,
                            user=self._user,
                            database=self._database,
                        )
                        conn.close()
                        self._mariadb_running = True
                        return True
                    except Exception:
                        time.sleep(0.5)
                
                return False
            except Exception as e:
                print(f"Failed to start MariaDB: {e}")
                return False
    
    def _stop_mariadb(self) -> None:
        """Stop embedded MariaDB server."""
        with self._mariadb_lock:
            if self._mariadb_process:
                self._mariadb_process.terminate()
                try:
                    self._mariadb_process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._mariadb_process.kill()
                self._mariadb_process = None
            self._mariadb_running = False
    
    def initialize(self) -> bool:
        """Initialize the database."""
        if self._initialized:
            return True
        
        self._start_mariadb()
        if self._mariadb_running:
            self._init_mariadb_schema()
            self._initialized = True
            return True
        
        return False
    
    def _init_mariadb_schema(self) -> None:
        """Initialize MariaDB schema."""
        if not PYMYSQL_AVAILABLE:
            return
        
        try:
            conn = pymysql.connect(
                unix_socket=self._socket,
                user=self._user,
            )
            try:
                with conn.cursor() as cursor:
                    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {self._database}")
                    cursor.execute(f"USE {self._database}")
                    for statement in INITIAL_SCHEMA.split(";"):
                        statement = statement.strip()
                        if statement:
                            cursor.execute(statement)
                    conn.commit()
            finally:
                conn.close()
        except Exception as e:
            print(f"Error initializing MariaDB schema: {e}")
    
    @contextmanager
    def get_connection(self) -> Generator[Any, None, None]:
        """Get a database connection."""
        yield self._get_mariadb_connection()
    
    def _get_mariadb_connection(self):
        """Get MariaDB connection."""
        if not PYMYSQL_AVAILABLE:
            raise RuntimeError("PyMySQL not available")
        
        conn = pymysql.connect(
            unix_socket=self._socket,
            user=self._user,
            database=self._database,
            cursorclass=DictCursor,
        )
        return conn
    
    def health_check(self) -> Dict[str, Any]:
        """Check database health."""
        result = {
            "backend": "mariadb",
            "running": self.is_running,
            "mariadb_available": PYMYSQL_AVAILABLE,
            "data_dir": str(self._data_dir),
            "socket": self._socket,
            "port": self._port,
        }
        
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
            result["healthy"] = True
        except Exception as e:
            result["healthy"] = False
            result["error"] = str(e)
        
        return result
    
    def status(self) -> Dict[str, Any]:
        """Get database status."""
        return {
            "backend": "mariadb",
            "initialized": self._initialized,
            "running": self.is_running,
            "data_dir": str(self._data_dir),
            "socket": self._socket,
        }
    
    def shutdown(self) -> None:
        """Shutdown the database."""
        self._stop_mariadb()
        self._initialized = False
    
    def execute(self, query: str, params: tuple = None) -> Any:
        """Execute a query."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, params or ())
                if query.strip().upper().startswith("SELECT"):
                    return cursor.fetchall()
                conn.commit()
    
    def insert_node(self, node: Node) -> bool:
        """Insert a node."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO nodes (id, title, content, summary, interest_level, 
                       created_at, updated_at, source_url, source_type, metadata)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                    (node.id, node.title, node.content, node.summary, node.interest_level,
                     node.created_at, node.updated_at, node.source_url, node.source_type,
                     __import__('json').dumps(node.metadata))
                )
                conn.commit()
        return True
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by ID."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM nodes WHERE id = %s", (node_id,))
                row = cursor.fetchone()
                if row:
                    return Node.from_dict(row)
        return None
    
    def list_nodes(self, limit: int = 100, offset: int = 0) -> List[Node]:
        """List nodes."""
        nodes = []
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM nodes ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
                for row in cursor.fetchall():
                    nodes.append(Node.from_dict(row))
        return nodes
    
    def update_node(self, node: Node) -> bool:
        """Update a node."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """UPDATE nodes SET title=%s, content=%s, summary=%s, interest_level=%s,
                       updated_at=%s, source_url=%s, source_type=%s, metadata=%s WHERE id=%s""",
                    (node.title, node.content, node.summary, node.interest_level,
                     node.updated_at, node.source_url, node.source_type,
                     __import__('json').dumps(node.metadata), node.id)
                )
                conn.commit()
        return True
    
    def delete_node(self, node_id: str) -> bool:
        """Delete a node."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM nodes WHERE id = %s", (node_id,))
                conn.commit()
        return True
    
    def insert_edge(self, edge: Edge) -> bool:
        """Insert an edge."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO edges (id, source_id, target_id, relationship_type, created_at)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (edge.id, edge.source_id, edge.target_id, edge.relationship_type, edge.created_at)
                )
                conn.commit()
        return True
    
    def list_edges(self, source_id: str = None, target_id: str = None) -> List[Edge]:
        """List edges."""
        edges = []
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                if source_id:
                    cursor.execute("SELECT * FROM edges WHERE source_id = %s", (source_id,))
                elif target_id:
                    cursor.execute("SELECT * FROM edges WHERE target_id = %s", (target_id,))
                else:
                    cursor.execute("SELECT * FROM edges")
                for row in cursor.fetchall():
                    edges.append(Edge.from_dict(row))
        return edges
    
    def delete_edge(self, edge_id: str) -> bool:
        """Delete an edge."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM edges WHERE id = %s", (edge_id,))
                conn.commit()
        return True
    
    def insert_app(self, app: App) -> bool:
        """Insert an app."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO apps (id, name, category, state, config, created_at, updated_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                    (app.id, app.name, app.category, app.state,
                     __import__('json').dumps(app.config), app.created_at, app.updated_at)
                )
                conn.commit()
        return True
    
    def list_apps(self) -> List[App]:
        """List apps."""
        apps = []
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM apps ORDER BY name")
                for row in cursor.fetchall():
                    apps.append(App.from_dict(row))
        return apps
    
    def insert_device(self, device: Device) -> bool:
        """Insert a device."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO devices (id, name, hostname, identity_hash, hardware_json, last_seen)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (device.id, device.name, device.hostname, device.identity_hash,
                     __import__('json').dumps(device.hardware_json), device.last_seen)
                )
                conn.commit()
        return True
    
    def list_devices(self) -> List[Device]:
        """List devices."""
        devices = []
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM devices ORDER BY name")
                for row in cursor.fetchall():
                    devices.append(Device.from_dict(row))
        return devices
    
    def insert_sync_log(self, sync_log: SyncLog) -> bool:
        """Insert a sync log entry."""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """INSERT INTO sync_log (id, entity_type, entity_id, action, timestamp, peer_id)
                       VALUES (%s, %s, %s, %s, %s, %s)""",
                    (sync_log.id, sync_log.entity_type, sync_log.entity_id,
                     sync_log.action, sync_log.timestamp, sync_log.peer_id)
                )
                conn.commit()
        return True