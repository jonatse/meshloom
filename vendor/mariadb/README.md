# MariaDB Bundled Binaries

This directory contains the MariaDB server binaries for Meshloom's embedded database.

## Downloading MariaDB

1. Go to https://mariadb.org/download
2. Select "MariaDB Server" (not MariaDB Cluster)
3. Choose "Linux x86_64" as the target OS
4. Select version 10.11 LTS or 11.x LTS
5. Download the binary tarball (not the RPM/DEB package)

## Manual Setup

If setup.py doesn't work, you can manually extract the tarball:

```bash
cd vendor/mariadb
tar -xzf /path/to/mariadb-*-linux-systemd-x86_64.tar.gz
# Move contents up one level
mv mariadb-*-linux-systemd-x86_64/* .
rmdir mariadb-*-linux-systemd-x86_64
```

## Required Files

After extraction, you should have:
- `bin/mariadbd` - The MariaDB server binary
- `bin/mysql` - Client binary (optional)
- `scripts/mariadb-install-db` - Database initialization script

## First Run

On first run, Meshloom will automatically initialize the data directory at `~/.meshloom/data/mariadb`.

The database uses:
- Socket: `~/.meshloom/run/mariadb.sock`
- Port: 3306
