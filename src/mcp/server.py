"""MCP Server implementation for Meshloom."""

import os
import sys
import json
import logging
from typing import Any, Optional

vendor_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'vendor', 'python')
if os.path.exists(vendor_dir) and vendor_dir not in sys.path:
    sys.path.insert(0, vendor_dir)

logger = logging.getLogger(__name__)

try:
    from mcp.server import Server
    from mcp.types import (
        Resource,
        ResourceTemplate,
        Tool,
        Prompt,
        PromptMessage,
        TextContent,
    )
    from mcp.server.stdio import stdio_server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not available. Install with: pip install modelcontextprotocol")


from .client import MeshloomClient
from . import resources, tools, prompts


class MCPServer:
    """MCP Server for Meshloom."""
    
    def __init__(self, client: Optional[MeshloomClient] = None):
        if not MCP_AVAILABLE:
            raise RuntimeError("MCP SDK not available. Please install: pip install modelcontextprotocol")
        
        self._client = client or MeshloomClient()
        self._server = Server("meshloom")
        self._register_handlers()
    
    def _register_handlers(self) -> None:
        """Register all MCP handlers."""
        resources.register_resources(self._server, self._client)
        tools.register_tools(self._server, self._client)
        prompts.register_prompts(self._server)
    
    async def run(self) -> None:
        """Run the MCP server using stdio."""
        async with stdio_server() as streams:
            await self._server.run(
                streams[0],
                streams[1],
                self._server.create_initialization_options()
            )
    
    def run_sync(self) -> None:
        """Run the MCP server synchronously."""
        import asyncio
        asyncio.run(self.run())


def create_server(meshloom_instance: Any = None) -> MCPServer:
    """Create an MCP server with a Meshloom client."""
    client = MeshloomClient(meshloom_instance)
    return MCPServer(client)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    server = create_server()
    server.run_sync()
