"""Meshloom MCP Server - Exposes Meshloom to AI assistants via MCP."""

import os
import sys

vendor_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

from .server import MCPServer, create_server

__all__ = ["MCPServer", "create_server"]
__version__ = "0.1.0"
