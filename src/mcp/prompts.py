"""MCP Prompts for Meshloom."""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TextContent:
    def __init__(self, type: str = "text", text: str = ""):
        self.type = type
        self.text = text


class PromptMessage:
    def __init__(self, role: str = "user", content: TextContent = None):
        self.role = role
        self.content = content or TextContent()


class Prompt:
    def __init__(self, name: str, description: str, arguments: list = None):
        self.name = name
        self.description = description
        self.arguments = arguments or []


class PromptArgument:
    def __init__(self, name: str, description: str, required: bool = False):
        self.name = name
        self.description = description
        self.required = required


def register_prompts(server) -> None:
    """Register all MCP prompts."""
    
    @server.list_prompts()
    def list_prompts() -> list[Prompt]:
        return [
            Prompt(
                name="review_sync_status",
                description="Generate a comprehensive sync status report",
                arguments=[
                    PromptArgument(
                        name="include_history",
                        description="Include recent sync history",
                        required=False
                    )
                ]
            ),
            Prompt(
                name="list_all_apps",
                description="Show all installed applications with their current state"
            ),
            Prompt(
                name="check_peer_connectivity",
                description="Display the connection status of all known peers"
            ),
            Prompt(
                name="get_system_overview",
                description="Get a comprehensive overview of the Meshloom system"
            ),
            Prompt(
                name="database_diagnostics",
                description="Run diagnostics on the knowledge database"
            ),
        ]
    
    @server.get_prompt()
    def get_prompt(name: str, arguments: Optional[dict] = None) -> list[PromptMessage]:
        args = arguments or {}
        
        if name == "review_sync_status":
            include_history = args.get("include_history", False)
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        text=f"""Please review the current sync status of Meshloom. 

Include the following information:
- Current sync state (idle/syncing/error)
- Pending changes
- Last successful sync time
- Connected peers and their sync status
{f'- Recent sync history (last 10 syncs)' if include_history else ''}

If there are any issues, please recommend fixes."""
                    )
                )
            ]
        
        elif name == "list_all_apps":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        text="""Please list all installed Meshloom applications.

For each app, show:
- Application name
- Version
- Status (installed/running/stopped)
- Resource usage if running

If any apps have issues, please suggest solutions."""
                    )
                )
            ]
        
        elif name == "check_peer_connectivity":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        text="""Please check the connectivity status of all mesh peers.

For each peer, show:
- Peer ID
- Connection status (connected/disconnected/connecting)
- Last seen timestamp
- Latency
- Pending sync items

If any peers are disconnected, please help troubleshoot."""
                    )
                )
            ]
        
        elif name == "get_system_overview":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        text="""Please provide a comprehensive overview of the Meshloom system.

Include:
- System status (running/stopped)
- Uptime
- All service statuses (network, sync, container, apps, bridges, API)
- Number of connected peers
- Number of installed apps
- Sync status
- Bridge connections

Provide a summary of the overall health of the system."""
                    )
                )
            ]
        
        elif name == "database_diagnostics":
            return [
                PromptMessage(
                    role="user",
                    content=TextContent(
                        text="""Please run diagnostics on the Meshloom knowledge database.

Include:
- Total number of nodes
- Total number of edges
- Database size
- Recent queries
- Any errors or issues

If there are problems, suggest solutions."""
                    )
                )
            ]
        
        raise ValueError(f"Unknown prompt: {name}")
