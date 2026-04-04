"""Configuration system for Meshloom."""

import os
import json
from typing import Any, Dict, Optional


class Config:
    """Configuration manager with dot-notation access."""
    
    DEFAULT_CONFIG: Dict[str, Any] = {
        "app": {
            "name": "Meshloom",
            "version": "0.1.0"
        },
        "debug": {
            "global_level": "INFO",
            "checkpoints": False,
            "modules": {
                "core": {"level": "INFO", "checkpoints": True, "performance": False},
                "network": {"level": "INFO", "checkpoints": True, "performance": False},
                "sync": {"level": "INFO", "checkpoints": True, "performance": False},
                "storage": {"level": "INFO", "checkpoints": True, "performance": False},
                "identity": {"level": "INFO", "checkpoints": False, "performance": False},
            }
        },
        "reticulum": {
            "identity_path": "~/.meshloom/storage/identities/meshloom",
            "announce_interval": 30,
            "interface": "auto",
        },
        "sync": {
            "sync_dir": "~/Meshloom/Sync",
            "sync_interval": 60,
            "auto_sync": True,
        },
        "network": {
            "bind_address": "0.0.0.0",
            "max_peers": 10,
            "transports": ["auto"],
        },
        "storage": {
            "data_dir": "~/.meshloom/storage",
            "cache_dir": "~/.meshloom/cache",
        },
    }
    
    def __init__(self, config_path: Optional[str] = None) -> None:
        self._config: Dict[str, Any] = self._deep_copy(self.DEFAULT_CONFIG)
        self.config_path: str = config_path or os.path.expanduser("~/.config/meshloom/config.json")
        self._load()
    
    def _deep_copy(self, obj: Any) -> Any:
        """Deep copy a dict/list structure."""
        if isinstance(obj, dict):
            return {k: self._deep_copy(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        return obj
    
    def _load(self) -> None:
        """Load config from file if exists."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    user_config = json.load(f)
                    self._merge(self._config, user_config)
            except (json.JSONDecodeError, IOError):
                pass
    
    def _merge(self, base: Dict[str, Any], update: Dict[str, Any]) -> None:
        """Recursively merge update into base."""
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._merge(base[key], value)
            else:
                base[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value by dot-notation key."""
        keys = key.split('.')
        value: Any = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            else:
                return default
        return value
    
    def set(self, key: str, value: Any) -> None:
        """Set config value by dot-notation key."""
        keys = key.split('.')
        config: Dict[str, Any] = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
    
    def save(self) -> None:
        """Save config to file."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(self._config, f, indent=2)
    
    @property
    def data(self) -> Dict[str, Any]:
        """Get raw config data."""
        return self._config


config = Config()
