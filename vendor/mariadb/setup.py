#!/usr/bin/env python3
"""Download and setup MariaDB binaries for Meshloom."""

import os
import subprocess
import sys
import urllib.request
import tarfile
import shutil
from pathlib import Path

MARIADB_VERSION = "10.11.12"
MARIADB_MIRROR = "https://archive.mariadb.org/mariadb-" + MARIADB_VERSION + "/bintar-linux-systemd-x86_64/mariadb-" + MARIADB_VERSION + "-linux-systemd-x86_64.tar.gz"


def get_vendor_dir() -> Path:
    """Get the vendor/mariadb directory."""
    script_dir = Path(__file__).parent.resolve()
    return script_dir


def download_mariadb(vendor_dir: Path) -> Path:
    """Download MariaDB binary tarball."""
    tarball_path = vendor_dir / f"mariadb-{MARIADB_VERSION}-linux-systemd-x86_64.tar.gz"
    
    if tarball_path.exists():
        print(f"Tarball already exists at {tarball_path}")
        return tarball_path
    
    print(f"Downloading MariaDB {MARIADB_VERSION}...")
    print(f"URL: {MARIADB_MIRROR}")
    
    try:
        urllib.request.urlretrieve(MARIADB_MIRROR, tarball_path)
        print(f"Downloaded to {tarball_path}")
    except Exception as e:
        print(f"Failed to download: {e}")
        print("\nManual download instructions:")
        print("1. Go to https://mariadb.org/download")
        print("2. Select 'MariaDB Server' - 'Linux x86_64' - version 10.11 or 11.x")
        print("3. Download the binary tarball")
        print(f"4. Save to {tarball_path}")
        sys.exit(1)
    
    return tarball_path


def extract_mariadb(vendor_dir: Path, tarball_path: Path) -> None:
    """Extract MariaDB binary tarball."""
    extracted_dir = vendor_dir / f"mariadb-{MARIADB_VERSION}-linux-systemd-x86_64"
    
    if (vendor_dir / "bin" / "mariadbd").exists():
        print("MariaDB already extracted")
        return
    
    print("Extracting MariaDB...")
    
    with tarfile.open(tarball_path, "r:gz") as tar:
        tar.extractall(vendor_dir)
    
    if extracted_dir.exists():
        for item in extracted_dir.iterdir():
            shutil.move(str(item), str(vendor_dir / item.name))
        extracted_dir.rmdir()
    
    print("Extraction complete")


def verify_installation(vendor_dir: Path) -> bool:
    """Verify MariaDB binaries are properly installed."""
    mariadbd = vendor_dir / "bin" / "mariadbd"
    install_db = vendor_dir / "scripts" / "mariadb-install-db"
    
    issues = []
    
    if not mariadbd.exists():
        issues.append(f"mariadbd not found at {mariadbd}")
    else:
        print(f"✓ Found mariadbd at {mariadbd}")
    
    if not install_db.exists():
        alt_install_db = vendor_dir / "bin" / "mariadb-install-db"
        if alt_install_db.exists():
            shutil.move(str(alt_install_db), str(install_db))
            print(f"✓ Found mariadb-install-db at {install_db}")
        else:
            issues.append(f"mariadb-install-db not found at {install_db} or {alt_install_db}")
    else:
        print(f"✓ Found mariadb-install-db at {install_db}")
    
    if issues:
        print("\nIssues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    
    return True


def main():
    """Main setup function."""
    vendor_dir = get_vendor_dir()
    
    print(f"Vendor directory: {vendor_dir}")
    
    tarball_path = download_mariadb(vendor_dir)
    extract_mariadb(vendor_dir, tarball_path)
    
    if verify_installation(vendor_dir):
        print("\n✓ MariaDB setup complete!")
        print("\nTo initialize the database, run Meshloom which will:")
        print("  - Create data directory at ~/.meshloom/data/mariadb")
        print("  - Initialize the database schema")
        print("  - Start the MariaDB server")
    else:
        print("\n✗ MariaDB setup incomplete")
        sys.exit(1)


if __name__ == "__main__":
    main()
