"""Apps package for Meshloom."""

from .base import App, AppContext
from .metadata import (
    AppMetadata,
    AppCategory,
    AppState,
    AppDependency,
    APP_CATEGORIES,
)
from .registry import AppRegistry, AppEntry, get_registry

__all__ = [
    "App",
    "AppContext",
    "AppMetadata",
    "AppCategory", 
    "AppState",
    "AppDependency",
    "APP_CATEGORIES",
    "AppRegistry",
    "AppEntry",
    "get_registry",
]
