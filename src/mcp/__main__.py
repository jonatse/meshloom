"""Allow running MCP server as: python -m src.mcp"""

import os
import sys
import logging

vendor_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

from .server import create_server


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger(__name__)
    
    logger.info("Starting Meshloom MCP Server...")
    
    server = create_server()
    
    try:
        server.run_sync()
    except KeyboardInterrupt:
        logger.info("MCP server stopped")
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
