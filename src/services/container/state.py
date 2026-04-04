"""Container state enum for Meshloom."""

from enum import Enum, auto


class ContainerState(Enum):
    """
    Container lifecycle states.
    
    States:
        STOPPED: Container is not running
        STARTING: Container is being created and started
        RUNNING: Container is active and executing
        STOPPING: Container is being gracefully stopped
        FAILED: Container encountered an error
        UNKNOWN: Container state cannot be determined
    """
    
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    FAILED = auto()
    UNKNOWN = auto()
    
    def is_active(self) -> bool:
        """Check if container is in an active state."""
        return self in (ContainerState.STARTING, ContainerState.RUNNING)
    
    def is_transition_state(self) -> bool:
        """Check if container is in a transitional state."""
        return self in (ContainerState.STARTING, ContainerState.STOPPING)
    
    def __str__(self) -> str:
        return self.name.lower()