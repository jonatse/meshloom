"""Debug and diagnostics system for Meshloom."""

import time
import logging
from enum import IntEnum
from typing import Dict, List, Any, Optional, TYPE_CHECKING
from dataclasses import dataclass, field
from datetime import datetime
import json
import os

if TYPE_CHECKING:
    from .config import Config


class DebugLevel(IntEnum):
    """Debug verbosity levels."""
    OFF = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


@dataclass
class Checkpoint:
    """A checkpoint for tracking startup flow."""
    name: str
    timestamp: float
    data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Timing:
    """Timing measurement for an operation."""
    operation: str
    duration_ms: float
    timestamp: float


class Diagnostics:
    """
    Central debug system for Meshloom.
    
    Config-driven, per-module toggles, checkpoint tracking.
    No code changes needed to enable debug - just edit config.
    """
    
    DEFAULT_LEVEL = DebugLevel.INFO
    
    def __init__(self, config: "Config") -> None:
        self._config = config
        self._log = logging.getLogger("meshloom.diagnostics")
        self._checkpoints: List[Checkpoint] = []
        self._timings: List[Timing] = []
        self._level_map: Dict[str, DebugLevel] = {
            "OFF": DebugLevel.OFF,
            "ERROR": DebugLevel.ERROR,
            "WARN": DebugLevel.WARN,
            "INFO": DebugLevel.INFO,
            "DEBUG": DebugLevel.DEBUG,
            "TRACE": DebugLevel.TRACE,
        }
    
    def _get_module_level(self, module: str) -> DebugLevel:
        """Get debug level for module from config."""
        level_str = self._config.get(f"debug.modules.{module}.level", "INFO")
        return self._level_map.get(level_str.upper(), self.DEFAULT_LEVEL)
    
    def _get_module_setting(self, module: str, key: str, default: Any) -> Any:
        """Get a debug setting for a module."""
        return self._config.get(f"debug.modules.{module}.{key}", default)
    
    def log(self, module: str, level: str, message: str, **data: Any) -> None:
        """Log a message if debug level permits."""
        module_level = self._get_module_level(module)
        msg_level = self._level_map.get(level.upper(), DebugLevel.INFO)
        
        if msg_level <= module_level:
            timestamp = datetime.now().isoformat()
            version = self._config.get("app.version", "0.1.0")
            
            log_entry: Dict[str, Any] = {
                "timestamp": timestamp,
                "version": version,
                "module": module,
                "level": level.upper(),
                "message": message,
            }
            if data:
                log_entry["data"] = data
            
            prefix = f"[{level.upper()}]"
            if data:
                print(f"{prefix} {module}: {message} {json.dumps(data)}")
            else:
                print(f"{prefix} {module}: {message}")
            
            self._write_to_file(log_entry)
    
    def checkpoint(self, name: str, **data: Any) -> None:
        """Record a checkpoint - shows startup flow."""
        module = name.split(".")[0]
        enabled = self._get_module_setting(module, "checkpoints", False)
        
        if enabled:
            cp = Checkpoint(
                name=name,
                timestamp=time.time(),
                data=data
            )
            self._checkpoints.append(cp)
            print(f"[CHECKPOINT] {name}")
    
    def timing(self, operation: str, duration_ms: float) -> None:
        """Record timing for an operation."""
        module = operation.split(".")[0]
        enabled = self._get_module_setting(module, "performance", False)
        
        if enabled:
            t = Timing(
                operation=operation,
                duration_ms=duration_ms,
                timestamp=time.time()
            )
            self._timings.append(t)
    
    def error(self, module: str, message: str, **data: Any) -> None:
        """Log error level."""
        self.log(module, "ERROR", message, **data)
    
    def warn(self, module: str, message: str, **data: Any) -> None:
        """Log warning level."""
        self.log(module, "WARN", message, **data)
    
    def info(self, module: str, message: str, **data: Any) -> None:
        """Log info level."""
        self.log(module, "INFO", message, **data)
    
    def debug(self, module: str, message: str, **data: Any) -> None:
        """Log debug level."""
        self.log(module, "DEBUG", message, **data)
    
    def trace(self, module: str, message: str, **data: Any) -> None:
        """Log trace level."""
        self.log(module, "TRACE", message, **data)
    
    def _write_to_file(self, entry: Dict[str, Any]) -> None:
        """Write log entry to file."""
        try:
            log_dir = os.path.expanduser("~/.local/share/meshloom/logs")
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, "diagnostics.log")
            
            with open(log_file, "a") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            self._log.warning(f"Failed to write to diagnostics log: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current debug status."""
        modules: Dict[str, str] = {}
        for key in self._config.data.get("debug", {}).get("modules", {}).keys():
            modules[key] = self._config.get(f"debug.modules.{key}.level", "INFO")
        
        return {
            "global_level": self._config.get("debug.global_level", "INFO"),
            "modules": modules,
            "checkpoints_enabled": self._config.get("debug.checkpoints", False),
            "checkpoint_count": len(self._checkpoints),
            "timing_count": len(self._timings),
        }
    
    def get_checkpoints(self) -> List[Dict[str, Any]]:
        """Get all recorded checkpoints."""
        return [
            {"name": cp.name, "timestamp": cp.timestamp, "data": cp.data}
            for cp in self._checkpoints
        ]
    
    def get_timings(self) -> List[Dict[str, Any]]:
        """Get all recorded timings."""
        return [
            {"operation": t.operation, "duration_ms": t.duration_ms, "timestamp": t.timestamp}
            for t in self._timings
        ]
    
    def set_module_level(self, module: str, level: str) -> bool:
        """Set debug level for a module at runtime."""
        if level.upper() not in self._level_map:
            return False
        
        self._config.set(f"debug.modules.{module}.level", level.upper())
        return True


def create_diagnostics(config: Optional["Config"] = None) -> Diagnostics:
    """Create diagnostics with default or provided config."""
    if config is None:
        from .config import Config
        config = Config()
    return Diagnostics(config)
