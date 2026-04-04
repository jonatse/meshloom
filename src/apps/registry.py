"""App Registry for Meshloom."""

import os
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Type

from .base import App, AppContext
from .metadata import AppMetadata, AppState, AppDependency


@dataclass
class AppEntry:
    """An entry in the app registry."""
    metadata: AppMetadata
    app_class: Type[App]
    state: AppState = AppState.INSTALLED
    instance: Optional[App] = None
    error: Optional[str] = None


class AppRegistry:
    """
    Registry for managing apps.
    
    Features:
    - App discovery and loading
    - State management
    - Dependency resolution
    - Installation/uninstallation
    
    Attributes:
        app_dir: Directory containing app modules
    """
    
    def __init__(self, app_dir: Optional[Path] = None) -> None:
        self._entries: Dict[str, AppEntry] = {}
        self._app_dir = app_dir
        self._app_context: Optional[AppContext] = None
    
    @property
    def entries(self) -> Dict[str, AppEntry]:
        """Get all registered apps."""
        return self._entries
    
    @property
    def installed_apps(self) -> List[AppEntry]:
        """Get all installed apps."""
        return [e for e in self._entries.values() if e.state != AppState.FAILED]
    
    @property
    def started_apps(self) -> List[AppEntry]:
        """Get all started apps."""
        return [e for e in self._entries.values() if e.state == AppState.STARTED]
    
    def set_app_context(self, context: AppContext) -> None:
        """Set context for all apps."""
        self._app_context = context
    
    def register(
        self,
        metadata: AppMetadata,
        app_class: Type[App],
    ) -> None:
        """
        Register an app.
        
        Args:
            metadata: App metadata
            app_class: App class
        """
        app_id = metadata.name.lower().replace(" ", "_")
        
        if app_id in self._entries:
            raise ValueError(f"App already registered: {app_id}")
        
        self._entries[app_id] = AppEntry(
            metadata=metadata,
            app_class=app_class,
        )
    
    def unregister(self, app_id: str) -> bool:
        """
        Unregister an app.
        
        Args:
            app_id: App identifier
            
        Returns:
            True if unregistered
        """
        if app_id in self._entries:
            del self._entries[app_id]
            return True
        return False
    
    def get(self, app_id: str) -> Optional[AppEntry]:
        """
        Get app entry by ID.
        
        Args:
            app_id: App identifier
            
        Returns:
            App entry or None
        """
        return self._entries.get(app_id)
    
    def get_by_name(self, name: str) -> Optional[AppEntry]:
        """
        Get app entry by name.
        
        Args:
            name: App name
            
        Returns:
            App entry or None
        """
        name_lower = name.lower().replace(" ", "_")
        return self._entries.get(name_lower)
    
    def _resolve_dependencies(
        self,
        entry: AppEntry,
        resolved: List[str] = None,
    ) -> List[str]:
        """
        Resolve app dependencies.
        
        Args:
            entry: App entry
            resolved: Already resolved apps
            
        Returns:
            List of app IDs in dependency order
        """
        if resolved is None:
            resolved = []
        
        for dep in entry.metadata.dependencies:
            dep_id = dep.name.lower().replace(" ", "_")
            
            if dep_id in resolved:
                continue
            
            if dep_id not in self._entries:
                if not dep.optional:
                    raise RuntimeError(f"Missing dependency: {dep.name}")
                continue
            
            dep_entry = self._entries[dep_id]
            self._resolve_dependencies(dep_entry, resolved)
            
            if dep_id not in resolved:
                resolved.append(dep_id)
        
        app_id = entry.metadata.name.lower().replace(" ", "_")
        if app_id not in resolved:
            resolved.append(app_id)
        
        return resolved
    
    def install(self, app_id: str) -> bool:
        """
        Install an app.
        
        Args:
            app_id: App identifier
            
        Returns:
            True if installed successfully
        """
        entry = self._entries.get(app_id)
        if not entry:
            return False
        
        if entry.instance:
            return True
        
        if not self._check_dependencies(entry):
            return False
        
        try:
            app = entry.app_class(entry.metadata)
            
            if self._app_context:
                app._set_context(self._app_context)
            
            if not app.on_install():
                entry.error = "Installation failed"
                entry.state = AppState.FAILED
                return False
            
            entry.instance = app
            entry.state = AppState.INSTALLED
            
            return True
            
        except Exception as e:
            entry.error = str(e)
            entry.state = AppState.FAILED
            return False
    
    def uninstall(self, app_id: str) -> bool:
        """
        Uninstall an app.
        
        Args:
            app_id: App identifier
            
        Returns:
            True if uninstalled successfully
        """
        entry = self._entries.get(app_id)
        if not entry:
            return False
        
        if entry.state == AppState.STARTED:
            self.stop(app_id)
        
        if not entry.instance:
            return True
        
        try:
            if not entry.instance.on_uninstall():
                return False
            
            entry.instance = None
            entry.state = AppState.INSTALLED
            
            return True
            
        except Exception as e:
            entry.error = str(e)
            return False
    
    def start(self, app_id: str) -> bool:
        """
        Start an app.
        
        Args:
            app_id: App identifier
            
        Returns:
            True if started successfully
        """
        entry = self._entries.get(app_id)
        if not entry:
            return False
        
        if entry.state == AppState.STARTED:
            return True
        
        if not self._check_dependencies(entry):
            return False
        
        try:
            if not entry.instance:
                if not self.install(app_id):
                    return False
                entry = self._entries[app_id]
            
            if not entry.instance.on_start():
                entry.error = "Start failed"
                entry.state = AppState.FAILED
                return False
            
            entry.state = AppState.STARTED
            
            return True
            
        except Exception as e:
            entry.error = str(e)
            entry.state = AppState.FAILED
            return False
    
    def stop(self, app_id: str) -> bool:
        """
        Stop an app.
        
        Args:
            app_id: App identifier
            
        Returns:
            True if stopped successfully
        """
        entry = self._entries.get(app_id)
        if not entry:
            return False
        
        if entry.state != AppState.STARTED:
            return True
        
        try:
            if not entry.instance.on_stop():
                return False
            
            entry.state = AppState.STOPPED
            
            return True
            
        except Exception as e:
            entry.error = str(e)
            return False
    
    def _check_dependencies(self, entry: AppEntry) -> bool:
        """Check if dependencies are met."""
        for dep in entry.metadata.dependencies:
            dep_id = dep.name.lower().replace(" ", "_")
            
            if dep_id not in self._entries:
                if not dep.optional:
                    entry.error = f"Missing dependency: {dep.name}"
                    return False
                continue
            
            dep_entry = self._entries[dep_id]
            if dep_entry.state != AppState.STARTED:
                if not dep.optional:
                    entry.error = f"Dependency not started: {dep.name}"
                    return False
                continue
        
        return True
    
    def load_apps(self) -> int:
        """
        Discover and load apps from app directory.
        
        Returns:
            Number of apps loaded
        """
        if not self._app_dir:
            return 0
        
        loaded = 0
        
        for app_path in self._app_dir.iterdir():
            if not app_path.is_dir():
                continue
            
            init_file = app_path / "app.py"
            if not init_file.exists():
                continue
            
            try:
                self._load_app_from_path(app_path)
                loaded += 1
            except Exception:
                pass
        
        return loaded
    
    def _load_app_from_path(self, app_path: Path) -> None:
        """Load app from directory path."""
        import importlib.util
        import sys
        
        module_name = f"meshloom.apps.{app_path.name}"
        
        spec = importlib.util.spec_from_file_location(
            module_name,
            app_path / "app.py"
        )
        
        if not spec or not spec.loader:
            return
        
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
        
        if hasattr(module, "APP_METADATA"):
            metadata = module.APP_METADATA
            if hasattr(module, "App"):
                self.register(metadata, module.App)
    
    def get_status(self, app_id: str) -> Dict[str, Any]:
        """
        Get app status.
        
        Args:
            app_id: App identifier
            
        Returns:
            Status dictionary
        """
        entry = self._entries.get(app_id)
        if not entry:
            return {"found": False}
        
        return {
            "found": True,
            "name": entry.metadata.name,
            "version": entry.metadata.version,
            "state": entry.state.value,
            "error": entry.error,
        }
    
    def list_apps(
        self,
        category: Optional[str] = None,
        state: Optional[AppState] = None,
    ) -> List[Dict[str, Any]]:
        """
        List apps with optional filters.
        
        Args:
            category: Filter by category
            state: Filter by state
            
        Returns:
            List of app info
        """
        result = []
        
        for entry in self._entries.values():
            if category and entry.metadata.category.value != category:
                continue
            if state and entry.state != state:
                continue
            
            result.append({
                "name": entry.metadata.name,
                "id": entry.metadata.name.lower().replace(" ", "_"),
                "version": entry.metadata.version,
                "category": entry.metadata.category.value,
                "state": entry.state.value,
            })
        
        return result


_app_registry: Optional[AppRegistry] = None


def get_registry() -> AppRegistry:
    """Get the global app registry."""
    global _app_registry
    if _app_registry is None:
        _app_registry = AppRegistry()
    return _app_registry
