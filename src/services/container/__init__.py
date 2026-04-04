"""
Container Service - Manages isolated container environments for Meshloom.

Uses Alpine Linux rootfs with support for chroot, systemd-nspawn, or Docker fallback.
Provides container lifecycle management, command execution, and health monitoring.
"""

from .manager import ContainerManager
from .state import ContainerState

__all__ = ["ContainerManager", "ContainerState"]