"""App metadata definitions for Meshloom."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class AppCategory(Enum):
    """Categories for organizing apps."""
    PRODUCTIVITY = "productivity"
    KNOWLEDGE = "knowledge"
    LIFE = "life"
    COMMUNICATION = "communication"
    INTELLIGENCE = "intelligence"
    LOCATION = "location"
    
    @classmethod
    def from_string(cls, value: str) -> "AppCategory":
        """Create category from string."""
        for category in cls:
            if category.value == value.lower():
                return category
        raise ValueError(f"Unknown category: {value}")


class AppState(Enum):
    """States an app can be in."""
    INSTALLED = "installed"
    STARTED = "started"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass
class AppDependency:
    """Represents an app dependency."""
    name: str
    version: str = "*"
    optional: bool = False


@dataclass
class AppMetadata:
    """
    Metadata for an app.
    
    Contains all information needed to identify and manage an app.
    """
    name: str
    description: str
    category: AppCategory
    version: str = "0.1.0"
    author: str = ""
    dependencies: List[AppDependency] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    icon: str = ""
    keywords: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "dependencies": [
                {"name": d.name, "version": d.version, "optional": d.optional}
                for d in self.dependencies
            ],
            "permissions": self.permissions,
            "icon": self.icon,
            "keywords": self.keywords,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, any]) -> "AppMetadata":
        """Create from dictionary."""
        dependencies = [
            AppDependency(
                name=d["name"],
                version=d.get("version", "*"),
                optional=d.get("optional", False),
            )
            for d in data.get("dependencies", [])
        ]
        
        category = AppCategory.from_string(data.get("category", "productivity"))
        
        return cls(
            name=data["name"],
            description=data["description"],
            category=category,
            version=data.get("version", "0.1.0"),
            author=data.get("author", ""),
            dependencies=dependencies,
            permissions=data.get("permissions", []),
            icon=data.get("icon", ""),
            keywords=data.get("keywords", []),
        )


APP_CATEGORIES = {
    "files": AppCategory.PRODUCTIVITY,
    "deck": AppCategory.PRODUCTIVITY,
    "calendar": AppCategory.PRODUCTIVITY,
    "contacts": AppCategory.PRODUCTIVITY,
    "notes": AppCategory.PRODUCTIVITY,
    "tasks": AppCategory.PRODUCTIVITY,
    "passwords": AppCategory.PRODUCTIVITY,
    "bookmarks": AppCategory.PRODUCTIVITY,
    "collectives": AppCategory.KNOWLEDGE,
    "cookbook": AppCategory.KNOWLEDGE,
    "universal": AppCategory.KNOWLEDGE,
    "vault": AppCategory.LIFE,
    "books": AppCategory.LIFE,
    "media": AppCategory.LIFE,
    "health": AppCategory.LIFE,
    "comm": AppCategory.COMMUNICATION,
    "talk": AppCategory.COMMUNICATION,
    "ai": AppCategory.INTELLIGENCE,
    "office": AppCategory.INTELLIGENCE,
    "map": AppCategory.LOCATION,
    "social": AppCategory.LOCATION,
}
