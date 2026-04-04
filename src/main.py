"""
Meshloom Main Orchestrator.

Main entry point that orchestrates all services, handles startup/shutdown
lifecycle, wires up dependencies between services, and provides unified status.
"""

import argparse
import asyncio
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from src.core.config import Config
from src.core.diagnostics import Diagnostics
from src.core.events import EventBus, Event
from src.services.network import NetworkService
from src.services.sync.engine import SyncEngine
from src.services.container.manager import ContainerManager
from src.services.db import DatabaseManager
from src.apps.registry import AppRegistry, get_registry
from src.apps.base import AppContext
from src.bridges.manager import BridgeManager
from src.bridges.atak import ATAKBridge
from src.bridges.xmpp import XMPPBridge
from src.bridges.matrix import MatrixBridge
from src.bridges.nextcloud import NextcloudBridge
from src.api.server import APIServer
from src.api.commands import CommandHandler
from src.core.version import VERSION, __app_name__


class Meshloom:
    """
    Main orchestrator for Meshloom.
    
    Creates and manages all services, handles startup/shutdown lifecycle,
    wires up dependencies between services, and provides unified status.
    
    Startup sequence:
        1. Initialize config and diagnostics
        2. Create event bus
        3. Start network service
        4. Start sync engine
        5. Start container manager
        6. Register apps
        7. Start bridges
        8. Start API server
    
    Shutdown sequence:
        Reverse of startup
    """
    
    def __init__(self, config: Optional[Config] = None) -> None:
        self._config = config or Config()
        self._diag = Diagnostics(self._config)
        self._event_bus = EventBus()
        
        self._network: Optional[NetworkService] = None
        self._sync_engine: Optional[SyncEngine] = None
        self._container_manager: Optional[ContainerManager] = None
        self._app_registry: Optional[AppRegistry] = None
        self._bridge_manager: Optional[BridgeManager] = None
        self._api_server: Optional[APIServer] = None
        self._command_handler: Optional[CommandHandler] = None
        
        self._running = False
        self._start_time: Optional[float] = None
        
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        print("\nReceived shutdown signal, stopping Meshloom...")
        asyncio.create_task(self.stop())
    
    @property
    def running(self) -> bool:
        """Check if Meshloom is running."""
        return self._running
    
    @property
    def uptime(self) -> float:
        """Get uptime in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return 0.0
    
    async def start(self) -> bool:
        """
        Start all Meshloom services.
        
        Returns:
            True if all services started successfully
        """
        self._diag.info("core", f"Starting {__app_name__} v{VERSION}")
        self._diag.checkpoint("core.start")
        
        try:
            await self._start_network()
            self._diag.checkpoint("network.started")
            
            await self._start_sync_engine()
            self._diag.checkpoint("sync.started")
            
            await self._start_container_manager()
            self._diag.checkpoint("container.started")
            
            await self._register_apps()
            self._diag.checkpoint("apps.registered")
            
            await self._start_bridges()
            self._diag.checkpoint("bridges.started")
            
            await self._start_api_server()
            self._diag.checkpoint("api.started")
            
            self._running = True
            self._start_time = time.time()
            
            self._diag.info("core", f"{__app_name__} started successfully")
            self._diag.checkpoint("core.ready")
            
            return True
            
        except Exception as e:
            self._diag.error("core", f"Failed to start: {e}")
            await self.stop()
            return False
    
    async def stop(self) -> bool:
        """
        Stop all Meshloom services in reverse order.
        
        Returns:
            True if all services stopped successfully
        """
        if not self._running:
            return True
        
        self._diag.info("core", "Stopping Meshloom")
        self._running = False
        
        errors: List[str] = []
        
        if self._api_server:
            try:
                await self._api_server.stop()
                self._diag.debug("core", "API server stopped")
            except Exception as e:
                errors.append(f"API server: {e}")
        
        if self._bridge_manager:
            try:
                self._bridge_manager.stop()
                self._diag.debug("core", "Bridges stopped")
            except Exception as e:
                errors.append(f"Bridge manager: {e}")
        
        if self._app_registry:
            for entry in self._app_registry.started_apps:
                try:
                    self._app_registry.stop(entry.metadata.name.lower().replace(" ", "_"))
                except Exception as e:
                    errors.append(f"App {entry.metadata.name}: {e}")
        
        if self._container_manager:
            try:
                await self._container_manager.stop()
                self._diag.debug("core", "Container manager stopped")
            except Exception as e:
                errors.append(f"Container manager: {e}")
        
        if self._sync_engine:
            try:
                await self._sync_engine.stop()
                self._diag.debug("core", "Sync engine stopped")
            except Exception as e:
                errors.append(f"Sync engine: {e}")
        
        if self._network:
            try:
                await self._network.stop()
                self._diag.debug("core", "Network service stopped")
            except Exception as e:
                errors.append(f"Network service: {e}")
        
        if errors:
            self._diag.warn("core", f"Shutdown errors: {', '.join(errors)}")
        
        self._diag.info("core", "Meshloom stopped")
        
        return True
    
    async def _start_network(self) -> None:
        """Start the network service."""
        self._diag.info("core", "Starting network service")
        self._network = NetworkService(self._config, self._diag)
        await self._network.start()
    
    async def _start_sync_engine(self) -> None:
        """Start the sync engine."""
        self._diag.info("core", "Starting sync engine")
        self._sync_engine = SyncEngine(
            self._config,
            self._diag,
            self._network,
        )
        await self._sync_engine.start()
        
        self._network.register_index_handler(self._sync_engine.get_local_manifest)
    
    async def _start_container_manager(self) -> None:
        """Start the container manager."""
        self._diag.info("core", "Starting container manager")
        self._container_manager = ContainerManager(
            self._config,
            self._diag,
            self._event_bus,
        )
        
        auto_start = self._config.get("container.auto_start", True)
        if auto_start:
            await self._container_manager.start()
    
    async def _register_apps(self) -> None:
        """Register and initialize apps."""
        self._diag.info("core", "Registering apps")
        
        db_config = {
            "data_dir": os.path.expanduser(self._config.get("storage.data_dir", "~/.meshloom/data")),
            "run_dir": os.path.expanduser(self._config.get("storage.run_dir", "~/.meshloom/run")),
            "backend": self._config.get("database.backend", "mariadb"),
        }
        self._db_manager = DatabaseManager(db_config)
        self._db_manager.initialize()
        
        self._app_registry = get_registry()
        
        apps_dir = Path(__file__).parent / "apps"
        if apps_dir.exists():
            self._app_registry = AppRegistry(apps_dir)
        
        data_dir = Path(os.path.expanduser(self._config.get("storage.data_dir", "~/.meshloom/storage")))
        sync_dir = Path(os.path.expanduser(self._config.get("sync.sync_dir", "~/Meshloom/Sync")))
        
        app_context = AppContext(
            app_id="meshloom",
            app_dir=apps_dir,
            data_dir=data_dir,
            sync_dir=sync_dir,
            config=self._config.data,
            db_manager=self._db_manager,
        )
        
        self._app_registry.set_app_context(app_context)
        self._app_registry.set_db_manager(self._db_manager)
        
        self._load_builtin_apps()
        
        self._diag.info("core", f"Registered {len(self._app_registry.entries)} apps")
    
    def _load_builtin_apps(self) -> None:
        """Load built-in apps."""
        try:
            from apps.files.app import FilesApp, APP_METADATA as FILES_APP_METADATA
            from apps.notes.app import NotesApp, APP_METADATA as NOTES_APP_METADATA
            from apps.tasks.app import TasksApp, APP_METADATA as TASKS_APP_METADATA
            
            self._app_registry.register(FILES_APP_METADATA, FilesApp)
            self._app_registry.register(NOTES_APP_METADATA, NotesApp)
            self._app_registry.register(TASKS_APP_METADATA, TasksApp)
        except ImportError as e:
            self._diag.warn("core", f"Could not load built-in apps: {e}")
        
        for entry in self._app_registry.entries.values():
            try:
                self._app_registry.install(entry.metadata.name.lower().replace(" ", "_"))
            except Exception as e:
                self._diag.warn("core", f"Failed to install {entry.metadata.name}: {e}")
    
    async def _start_bridges(self) -> None:
        """Start bridge manager and initialize bridges."""
        self._diag.info("core", "Starting bridges")
        
        self._bridge_manager = BridgeManager()
        
        bridges_config = self._config.get("bridges", {})
        
        if bridges_config.get("atak", {}).get("enabled", False):
            self._bridge_manager.register_bridge(
                ATAKBridge(bridges_config.get("atak", {}))
            )
        
        if bridges_config.get("xmpp", {}).get("enabled", False):
            self._bridge_manager.register_bridge(
                XMPPBridge(bridges_config.get("xmpp", {}))
            )
        
        if bridges_config.get("matrix", {}).get("enabled", False):
            self._bridge_manager.register_bridge(
                MatrixBridge(bridges_config.get("matrix", {}))
            )
        
        if bridges_config.get("nextcloud", {}).get("enabled", False):
            self._bridge_manager.register_bridge(
                NextcloudBridge(bridges_config.get("nextcloud", {}))
            )
        
        self._bridge_manager.start()
        
        self._diag.info("core", f"Started {len(self._bridge_manager.bridges)} bridges")
    
    async def _start_api_server(self) -> None:
        """Start the API server."""
        self._diag.info("core", "Starting API server")
        
        socket_path = self._config.get("api.socket_path")
        
        self._command_handler = CommandHandler(
            config=self._config,
            network_service=self._network,
            sync_service=self._sync_engine,
            container_service=self._container_manager,
            app_registry=self._app_registry,
            bridge_manager=self._bridge_manager,
        )
        
        self._api_server = APIServer(
            socket_path=socket_path,
            command_handler=self._command_handler,
        )
        
        await self._api_server.start()
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get unified status of all services.
        
        Returns:
            Dictionary with status of all services
        """
        status: Dict[str, Any] = {
            "app": __app_name__,
            "version": VERSION,
            "running": self._running,
            "uptime_seconds": self.uptime,
            "services": {},
        }
        
        if self._network:
            status["services"]["network"] = self._network.get_status()
        
        if self._sync_engine:
            status["services"]["sync"] = self._sync_engine.get_status()
        
        if self._container_manager:
            status["services"]["container"] = self._container_manager.get_status()
        
        if self._app_registry:
            status["services"]["apps"] = {
                "registered": len(self._app_registry.entries),
                "installed": len(self._app_registry.installed_apps),
                "started": len(self._app_registry.started_apps),
            }
        
        if self._bridge_manager:
            status["services"]["bridges"] = self._bridge_manager.get_status()
        
        if self._api_server:
            status["services"]["api"] = {
                "running": self._api_server.is_running,
                "socket_path": self._api_server.socket_path,
            }
        
        return status


async def run_service() -> None:
    """Run Meshloom as a background service."""
    meshloom = Meshloom()
    
    if not await meshloom.start():
        print("Failed to start Meshloom")
        sys.exit(1)
    
    while meshloom.running:
        await asyncio.sleep(1)


async def run_cli() -> None:
    """Run Meshloom in interactive CLI mode."""
    meshloom = Meshloom()
    
    if not await meshloom.start():
        print("Failed to start Meshloom")
        sys.exit(1)
    
    print(f"\n{__app_name__} v{VERSION} - Interactive Mode")
    print("Type 'help' for commands, 'status' for system status, 'quit' to exit\n")
    
    while meshloom.running:
        try:
            cmd = input("meshloom> ").strip()
            
            if not cmd:
                continue
            
            if cmd == "quit" or cmd == "exit":
                break
            elif cmd == "status":
                import json
                print(json.dumps(meshloom.get_status(), indent=2))
            elif cmd == "help":
                print("""
Commands:
  status    - Show system status
  peers     - List connected peers
  apps      - List installed apps
  bridges   - List configured bridges
  quit      - Exit interactive mode
                """)
            elif cmd == "peers":
                if meshloom._network:
                    peers = meshloom._network.get_peers()
                    print(f"Connected peers: {len(peers)}")
                    for peer in peers:
                        print(f"  - {peer.name} ({peer.id[:16]}...)")
                else:
                    print("Network service not available")
            elif cmd == "apps":
                if meshloom._app_registry:
                    apps = meshloom._app_registry.list_apps()
                    print(f"Installed apps: {len(apps)}")
                    for app in apps:
                        print(f"  - {app['name']} ({app['state']})")
                else:
                    print("App registry not available")
            elif cmd == "bridges":
                if meshloom._bridge_manager:
                    bridges = meshloom._bridge_manager.get_status()
                    print(f"Configured bridges: {len(bridges)}")
                    for bid, bs in bridges.items():
                        print(f"  - {bid}: {bs['state']} ({'connected' if bs['connected'] else 'disconnected'})")
                else:
                    print("Bridge manager not available")
            else:
                print(f"Unknown command: {cmd}")
                
        except EOFError:
            break
        except KeyboardInterrupt:
            print("\nUse 'quit' to exit")
    
    await meshloom.stop()


def show_status() -> None:
    """Show status and exit."""
    meshloom = Meshloom()
    status = meshloom.get_status()
    
    print(f"\n{__app_name__} Status")
    print("=" * 40)
    print(f"Version: {status['version']}")
    print(f"Running: {status['running']}")
    print(f"Uptime: {status['uptime_seconds']:.1f}s")
    print()
    print("Services:")
    for name, svc_status in status['services'].items():
        if isinstance(svc_status, dict):
            print(f"  {name}: ", end="")
            if 'running' in svc_status:
                print(f"{'running' if svc_status['running'] else 'stopped'}")
            elif 'state' in svc_status:
                print(svc_status['state'])
            elif 'registered' in svc_status:
                print(f"{svc_status['started']}/{svc_status['installed']} started")
            else:
                print(svc_status)
    print()


def main() -> None:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description=f"{__app_name__} - Peer-to-peer mesh networking OS"
    )
    parser.add_argument(
        "--cli",
        action="store_true",
        help="Run in interactive CLI mode"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show status and exit"
    )
    parser.add_argument(
        "--config",
        type=str,
        help="Path to config file"
    )
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    if args.cli:
        asyncio.run(run_cli())
    else:
        asyncio.run(run_service())


if __name__ == "__main__":
    main()
