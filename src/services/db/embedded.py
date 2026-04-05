"""Embedded MariaDB support for Meshloom."""

import os
import subprocess
from pathlib import Path
from typing import Optional, Tuple


def get_vendor_dir() -> Optional[Path]:
    """Get the bundled MariaDB vendor directory."""
    current_file = Path(__file__).resolve()
    project_root = current_file.parent.parent.parent.parent
    vendor_dir = project_root / "vendor" / "mariadb"
    
    if vendor_dir.exists() and (vendor_dir / "bin" / "mariadbd").exists():
        return vendor_dir
    return None


def get_bundled_mariadb_paths() -> Tuple[Optional[Path], Optional[Path]]:
    """Get paths to bundled MariaDB binaries.
    
    Returns:
        Tuple of (mariadbd_path, mariadb_install_db_path) or (None, None) if not bundled.
    """
    vendor_dir = get_vendor_dir()
    
    if vendor_dir is None:
        return None, None
    
    mariadbd = vendor_dir / "bin" / "mariadbd"
    
    install_db = vendor_dir / "scripts" / "mariadb-install-db"
    if not install_db.exists():
        install_db = vendor_dir / "bin" / "mariadb-install-db"
    
    if mariadbd.exists():
        return mariadbd, install_db if install_db.exists() else None
    
    return None, None


def create_mariadb_config(vendor_dir: Path, data_dir: Path, socket_path: str, port: int) -> Path:
    """Create MariaDB configuration file for embedded use.
    
    Args:
        vendor_dir: Path to vendor/mariadb directory
        data_dir: Path to data directory
        socket_path: Path to socket file
        port: Port number
    
    Returns:
        Path to created config file
    """
    config_path = vendor_dir / "my.cnf"
    
    config_content = f"""[mysqld]
datadir={data_dir}
socket={socket_path}
port={port}
bind-address=127.0.0.1
skip-networking=0
user={os.environ.get('USER', 'root')}

[client]
socket={socket_path}
port={port}
"""
    
    config_path.write_text(config_content)
    return config_path


def initialize_mariadb_data(install_db_path: Path, data_dir: Path, socket_path: str) -> bool:
    """Initialize MariaDB data directory.
    
    Args:
        install_db_path: Path to mariadb-install-db script
        data_dir: Path to data directory
        socket_path: Path to socket file
    
    Returns:
        True if initialization succeeded
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    
    init_cmd = [
        str(install_db_path),
        f"--datadir={data_dir}",
        f"--socket={socket_path}",
        "--auth-root=socket",
    ]
    
    try:
        result = subprocess.run(
            init_cmd,
            check=True,
            capture_output=True,
            timeout=60,
        )
        return True
    except subprocess.CalledProcessError as e:
        print(f"Init failed with: {e}")
        print(f"stderr: {e.stderr.decode() if e.stderr else ''}")
        return False
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"Init error: {e}")
        return False


def start_bundled_mariadb(
    vendor_dir: Path,
    data_dir: Path,
    socket_path: str,
    port: int,
) -> Optional[subprocess.Popen]:
    """Start bundled MariaDB server.
    
    Args:
        vendor_dir: Path to vendor/mariadb directory
        data_dir: Path to data directory
        socket_path: Path to socket file
        port: Port number
    
    Returns:
        Popen process or None if failed
    """
    mariadbd_path = vendor_dir / "bin" / "mariadbd"
    config_path = create_mariadb_config(vendor_dir, data_dir, socket_path, port)
    
    server_cmd = [
        str(mariadbd_path),
        f"--defaults-file={config_path}",
    ]
    
    try:
        proc = subprocess.Popen(
            server_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc
    except FileNotFoundError:
        print(f"MariaDB binary not found: {mariadbd_path}")
        return None
    except Exception as e:
        print(f"Failed to start MariaDB: {e}")
        return None


def check_system_mariadb() -> bool:
    """Check if system MariaDB/MySQL is available.
    
    Returns:
        True if system mariadbd or mysqld is available
    """
    for binary in ["mariadbd", "mysqld"]:
        try:
            result = subprocess.run(
                ["which", binary],
                capture_output=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
    return False
