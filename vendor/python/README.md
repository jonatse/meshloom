# Vendored Python Packages

This directory contains bundled Python dependencies for Meshloom, enabling zero-pip operation.

## Packages

### pymysql/
Pure Python MySQL database driver.
- Source: https://github.com/PyMySQL/PyMySQL
- Version: 1.1.2

### rns/
Reticulum Network Stack - secure mesh networking.
- Source: https://github.com/markqvist/Reticulum
- Version: 1.1.4
- Dependencies: pyserial (bundled)

### serial/
pyserial - serial port communication.
- Source: https://github.com/pyserial/pyserial
- Version: 3.5

## Usage

Meshloom automatically adds this directory to `sys.path` at startup. No additional configuration required.

The import pattern in Meshloom:
```python
import sys
import os

# At top of main.py, before any other imports
vendor_dir = os.path.join(os.path.dirname(__file__), '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

# Normal imports work with vendored packages
import pymysql  # Uses vendored or system
import RNS      # Uses vendored or system
import serial  # Uses vendored or system
```

## Updating Packages

To update vendored packages:

```bash
cd vendor/python

# Download new versions
pip download pymysql --no-deps -d .
pip download RNS --no-deps -d .
pip download pyserial --no-deps -d .

# Extract (adjust versions as needed)
unzip -o pymysql-*.whl -d pymysql-tmp && mv pymysql-tmp/pymysql pymysql && rm -rf pymysql-tmp
unzip -o pyserial-*.whl -d serial-tmp && mv serial-tmp/serial serial && rm -rf serial-tmp
unzip -o rns-*.whl -d rns-tmp && mv rns-tmp/RNS rns && rm -rf rns-tmp
```