"""
Container Manager for Meshloom.

Manages isolated container environments for running apps using:
- Alpine Linux rootfs by default
- Self-contained (chroot, systemd-nspawn, or Docker fallback)
- Health monitoring with auto-restart
- Volume mounts for sync directory and Meshloom socket API
"""

import asyncio
import os
import shutil
import signal
import subprocess
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ...core.config import Config
from ...core.diagnostics import Diagnostics
from ...core.events import Event, EventBus, event_bus
from .state import ContainerState


@dataclass
class ContainerConfig:
    """Configuration for container runtime."""
    image: str = "alpine:latest"
    name: str = "meshloom-container"
    auto_start: bool = True
    rootfs_path: str = "~/.meshloom/container/rootfs"
    sync_dir: str = "~/Meshloom/Sync"
    socket_path: str = "~/.meshloom/meshloom.sock"
    data_dir: str = "~/.meshloom/storage"
    cpu_limit: Optional[float] = None
    memory_limit: Optional[str] = None
    restart_policy: str = "on-failure"
    health_check_interval: int = 30
    health_check_timeout: int = 10


@dataclass
class ContainerStatus:
    """Status information for the container."""
    state: ContainerState = ContainerState.UNKNOWN
    pid: Optional[int] = None
    uptime_seconds: float = 0.0
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    restart_count: int = 0
    last_error: Optional[str] = None
    rootfs_exists: bool = False


@dataclass
class ExecResult:
    """Result of command execution inside container."""
    exit_code: int
    stdout: str
    stderr: str
    duration_ms: float


class ContainerRuntime:
    """Abstract container runtime interface."""
    
    def is_available(self) -> bool:
        """Check if runtime is available on this system."""
        raise NotImplementedError
    
    def get_name(self) -> str:
        """Get runtime name."""
        raise NotImplementedError
    
    def create_rootfs(self, image: str, rootfs_path: str) -> bool:
        """Create rootfs from image."""
        raise NotImplementedError
    
    def start_container(
        self,
        name: str,
        rootfs_path: str,
        binds: Dict[str, str],
        env: Dict[str, str],
        command: Optional[List[str]] = None,
    ) -> Optional[int]:
        """Start container, return PID or None."""
        raise NotImplementedError
    
    def stop_container(self, name: str, timeout: int = 10) -> bool:
        """Stop container gracefully."""
        raise NotImplementedError
    
    def is_running(self, name: str) -> bool:
        """Check if container is running."""
        raise NotImplementedError
    
    def get_pid(self, name: str) -> Optional[int]:
        """Get container PID."""
        raise NotImplementedError
    
    def exec_command(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        """Execute command in running container."""
        raise NotImplementedError


class ChrootRuntime(ContainerRuntime):
    """Chroot-based container runtime."""
    
    def is_available(self) -> bool:
        return shutil.which("chroot") is not None
    
    def get_name(self) -> str:
        return "chroot"
    
    def create_rootfs(self, image: str, rootfs_path: str) -> bool:
        rootfs_path = os.path.expanduser(rootfs_path)
        
        if os.path.exists(rootfs_path):
            return True
        
        try:
            os.makedirs(rootfs_path, exist_ok=True)
            
            if ":" in image:
                registry, tag = image.rsplit(":", 1)
            else:
                tag = "latest"
            
            if tag in ("latest", "edge", "stable"):
                self._bootstrap_alpine(rootfs_path)
                return True
            
            return False
        except Exception:
            return False
    
    def _bootstrap_alpine(self, rootfs_path: str) -> bool:
        """Bootstrap Alpine Linux rootfs using apk."""
        try:
            os.makedirs(f"{rootfs_path}/etc", exist_ok=True)
            
            resolv_conf = """nameserver 1.1.1.1
nameserver 8.8.8.8
"""
            with open(f"{rootfs_path}/etc/resolv.conf", "w") as f:
                f.write(resolv_conf)
            
            os.makedirs(f"{rootfs_path}/bin", exist_ok=True)
            os.makedirs(f"{rootfs_path}/lib", exist_ok=True)
            os.makedirs(f"{rootfs_path}/usr/bin", exist_ok=True)
            
            for bin_file in ["sh", "ls", "cat", "echo", "pwd", "cd"]:
                try:
                    src = shutil.which(bin_file)
                    if src:
                        shutil.copy(src, f"{rootfs_path}/bin/")
                except Exception:
                    pass
            
            return True
        except Exception:
            return False
    
    def start_container(
        self,
        name: str,
        rootfs_path: str,
        binds: Dict[str, str],
        env: Dict[str, str],
        command: Optional[List[str]] = None,
    ) -> Optional[int]:
        rootfs_path = os.path.expanduser(rootfs_path)
        
        for src, dst in binds.items():
            if os.path.exists(src):
                target = f"{rootfs_path}{dst}"
                os.makedirs(os.path.dirname(target), exist_ok=True)
                if not os.path.exists(target):
                    try:
                        os.symlink(src, target)
                    except Exception:
                        pass
        
        cmd = command or ["/bin/sh"]
        env_str = " ".join(f"{k}={v}" for k, v in env.items())
        
        full_cmd = f"{env_str} chroot {rootfs_path} {' '.join(cmd)}"
        
        try:
            proc = subprocess.Popen(
                full_cmd,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid,
            )
            return proc.pid
        except Exception:
            return None
    
    def stop_container(self, name: str, timeout: int = 10) -> bool:
        return True
    
    def is_running(self, name: str) -> bool:
        return False
    
    def get_pid(self, name: str) -> Optional[int]:
        return None
    
    def exec_command(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        return (1, "", "Chroot runtime: exec not fully implemented")


class SystemdNspawnRuntime(ContainerRuntime):
    """systemd-nspawn based container runtime."""
    
    def is_available(self) -> bool:
        return shutil.which("systemd-nspawn") is not None
    
    def get_name(self) -> str:
        return "systemd-nspawn"
    
    def create_rootfs(self, image: str, rootfs_path: str) -> bool:
        rootfs_path = os.path.expanduser(rootfs_path)
        
        if os.path.exists(rootfs_path):
            return True
        
        try:
            os.makedirs(rootfs_path, exist_ok=True)
            
            if shutil.which("debootstrap"):
                result = subprocess.run(
                    ["debootstrap", "stable", rootfs_path],
                    capture_output=True,
                    timeout=300,
                )
                return result.returncode == 0
            
            return ChrootRuntime().create_rootfs(image, rootfs_path)
        except Exception:
            return False
    
    def start_container(
        self,
        name: str,
        rootfs_path: str,
        binds: Dict[str, str],
        env: Dict[str, str],
        command: Optional[List[str]] = None,
    ) -> Optional[int]:
        rootfs_path = os.path.expanduser(rootfs_path)
        
        cmd = ["systemd-nspawn", "-D", rootfs_path, "--machine", name]
        
        for src, dst in binds.items():
            if os.path.exists(src):
                cmd.extend(["--bind", f"{src}:{dst}"])
        
        for key, value in env.items():
            cmd.extend(["--setenv", f"{key}={value}"])
        
        if command:
            cmd.extend(command)
        else:
            cmd.append("/bin/sh")
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            return proc.pid
        except Exception:
            return None
    
    def stop_container(self, name: str, timeout: int = 10) -> bool:
        try:
            subprocess.run(
                ["machinectl", "terminate", name],
                capture_output=True,
                timeout=timeout,
            )
            return True
        except Exception:
            return False
    
    def is_running(self, name: str) -> bool:
        try:
            result = subprocess.run(
                ["machinectl", "show", name],
                capture_output=True,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_pid(self, name: str) -> Optional[int]:
        return None
    
    def exec_command(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        try:
            cmd = ["machinectl", "shell", name]
            for key, value in (env or {}).items():
                cmd.extend(["--setenv", f"{key}={value}"])
            cmd.extend(["--", *command])
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (result.returncode, result.stdout, result.stderr)
        except Exception as e:
            return (1, "", str(e))


class DockerRuntime(ContainerRuntime):
    """Docker-based container runtime."""
    
    def is_available(self) -> bool:
        if not shutil.which("docker"):
            return False
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def get_name(self) -> str:
        return "docker"
    
    def create_rootfs(self, image: str, rootfs_path: str) -> bool:
        try:
            result = subprocess.run(
                ["docker", "pull", image],
                capture_output=True,
                timeout=300,
            )
            return result.returncode == 0
        except Exception:
            return False
    
    def start_container(
        self,
        name: str,
        rootfs_path: str,
        binds: Dict[str, str],
        env: Dict[str, str],
        command: Optional[List[str]] = None,
    ) -> Optional[int]:
        cmd = [
            "docker", "run",
            "--detach",
            "--name", name,
            "--network", "none",
            "--restart", "no",
        ]
        
        for src, dst in binds.items():
            if os.path.exists(src):
                cmd.extend(["-v", f"{src}:{dst}:ro"])
        
        for key, value in env.items():
            cmd.extend(["-e", f"{key}={value}"])
        
        if command:
            cmd.append(image)
            cmd.extend(command)
        else:
            cmd.extend([image, "/bin/sh"])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return self._get_container_pid(name)
            return None
        except Exception:
            return None
    
    def _get_container_pid(self, name: str) -> Optional[int]:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Pid}}", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return int(result.stdout.strip())
            return None
        except Exception:
            return None
    
    def stop_container(self, name: str, timeout: int = 10) -> bool:
        try:
            subprocess.run(
                ["docker", "stop", "-t", str(timeout), name],
                capture_output=True,
                timeout=timeout + 5,
            )
            return True
        except Exception:
            return False
    
    def is_running(self, name: str) -> bool:
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Running}}", name],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception:
            return False
    
    def get_pid(self, name: str) -> Optional[int]:
        return self._get_container_pid(name)
    
    def exec_command(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
    ) -> Tuple[int, str, str]:
        try:
            cmd = ["docker", "exec", name]
            
            for key, value in (env or {}).items():
                cmd.extend(["-e", f"{key}={value}"])
            
            if cwd:
                cmd.extend(["-w", cwd])
            
            cmd.extend(command)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return (result.returncode, result.stdout, result.stderr)
        except Exception as e:
            return (1, "", str(e))


class ContainerManager:
    """
    Manages container lifecycle for Meshloom apps.
    
    Provides:
    - Container creation and startup
    - Command execution inside container
    - Shell access
    - Volume mounts (sync directory, socket)
    - Health monitoring with auto-restart
    - Event publishing for container state changes
    
    Args:
        config: Configuration object with container settings
        diagnostics: Diagnostics instance for logging
        event_bus: Optional event bus (uses global if not provided)
    """
    
    DEFAULT_CONTAINER_CONFIG = ContainerConfig()
    
    def __init__(
        self,
        config: Config,
        diagnostics: Diagnostics,
        event_bus: Optional[EventBus] = None,
    ) -> None:
        self._config = config
        self._diag = diagnostics
        self._event_bus = event_bus or event_bus
        
        self._container_config = self._load_container_config()
        self._runtime = self._detect_runtime()
        
        self._state = ContainerState.STOPPED
        self._status = ContainerStatus()
        
        self._health_monitor_task: Optional[asyncio.Task] = None
        self._health_monitor_running = False
        self._start_time: Optional[float] = None
        self._restart_count = 0
        
        self._state_lock = threading.Lock()
        
        self._diag.info("container", f"ContainerManager initialized with {self._runtime.get_name()} runtime")
    
    def _load_container_config(self) -> ContainerConfig:
        """Load container configuration from config object."""
        return ContainerConfig(
            image=self._config.get("container.image", "alpine:latest"),
            name=self._config.get("container.name", "meshloom-container"),
            auto_start=self._config.get("container.auto_start", True),
            rootfs_path=self._config.get("container.rootfs_path", "~/.meshloom/container/rootfs"),
            sync_dir=self._config.get("sync.sync_dir", "~/Meshloom/Sync"),
            socket_path=self._config.get("container.socket_path", "~/.meshloom/meshloom.sock"),
            data_dir=self._config.get("storage.data_dir", "~/.meshloom/storage"),
            cpu_limit=self._config.get("container.cpu_limit"),
            memory_limit=self._config.get("container.memory_limit"),
            restart_policy=self._config.get("container.restart_policy", "on-failure"),
            health_check_interval=self._config.get("container.health_check_interval", 30),
            health_check_timeout=self._config.get("container.health_check_timeout", 10),
        )
    
    def _detect_runtime(self) -> ContainerRuntime:
        """Detect available container runtime."""
        runtimes = [
            DockerRuntime(),
            SystemdNspawnRuntime(),
            ChrootRuntime(),
        ]
        
        for runtime in runtimes:
            if runtime.is_available():
                self._diag.info("container", f"Using {runtime.get_name()} runtime")
                return runtime
        
        return ChrootRuntime()
    
    @property
    def state(self) -> ContainerState:
        """Get current container state."""
        with self._state_lock:
            return self._state
    
    @property
    def status(self) -> ContainerStatus:
        """Get current container status."""
        with self._state_lock:
            status = ContainerStatus(
                state=self._state,
                pid=self._status.pid,
                uptime_seconds=self._get_uptime(),
                cpu_percent=self._status.cpu_percent,
                memory_mb=self._status.memory_mb,
                restart_count=self._restart_count,
                last_error=self._status.last_error,
                rootfs_exists=os.path.exists(os.path.expanduser(self._container_config.rootfs_path)),
            )
            return status
    
    def _get_uptime(self) -> float:
        """Get container uptime in seconds."""
        if self._start_time:
            return time.time() - self._start_time
        return 0.0
    
    def _set_state(self, new_state: ContainerState, error: Optional[str] = None) -> None:
        """Set container state and publish event."""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            
            if error:
                self._status.last_error = error
        
        if old_state != new_state:
            self._diag.info("container", f"State transition: {old_state.name} -> {new_state.name}")
            self._publish_event(
                "container.state_changed",
                {
                    "old_state": str(old_state),
                    "new_state": str(new_state),
                    "error": error,
                }
            )
    
    def _publish_event(self, event_type: str, data: Dict[str, Any]) -> None:
        """Publish event to event bus."""
        event = Event(
            type=event_type,
            data=data,
            source="container",
            timestamp=time.time(),
        )
        self._event_bus.publish(event)
    
    async def start(self) -> bool:
        """
        Start the container.
        
        Creates container if needed, starts in background, enables health monitoring.
        
        Returns:
            True if container started successfully, False otherwise
        """
        if self._state == ContainerState.RUNNING:
            self._diag.warn("container", "Container already running")
            return True
        
        self._set_state(ContainerState.STARTING)
        self._diag.info("container", "Starting container")
        
        try:
            if not self._create_container():
                self._set_state(ContainerState.FAILED, "Failed to create container")
                return False
            
            if not self._start_container_process():
                self._set_state(ContainerState.FAILED, "Failed to start container process")
                return False
            
            self._start_time = time.time()
            self._set_state(ContainerState.RUNNING)
            self._publish_event("container.started", {"name": self._container_config.name})
            
            self._start_health_monitor()
            
            self._diag.info("container", f"Container started successfully (PID: {self._status.pid})")
            return True
            
        except Exception as e:
            error_msg = f"Failed to start container: {e}"
            self._diag.error("container", error_msg)
            self._set_state(ContainerState.FAILED, error_msg)
            return False
    
    def _create_container(self) -> bool:
        """Create container rootfs if not exists."""
        rootfs_path = os.path.expanduser(self._container_config.rootfs_path)
        
        if os.path.exists(rootfs_path):
            self._diag.debug("container", "Using existing rootfs")
            return True
        
        self._diag.info("container", f"Creating rootfs at {rootfs_path}")
        
        os.makedirs(os.path.dirname(rootfs_path), exist_ok=True)
        
        return self._runtime.create_rootfs(
            self._container_config.image,
            self._container_config.rootfs_path
        )
    
    def _start_container_process(self) -> bool:
        """Start container process in background."""
        binds = self._get_volume_binds()
        env = self._get_environment()
        
        pid = self._runtime.start_container(
            self._container_config.name,
            self._container_config.rootfs_path,
            binds,
            env,
            ["/bin/sh", "-c", "while true; do sleep 3600; done"],
        )
        
        if pid:
            self._status.pid = pid
            return True
        
        return False
    
    def _get_volume_binds(self) -> Dict[str, str]:
        """Get volume bindings for container."""
        binds = {}
        
        sync_dir = os.path.expanduser(self._container_config.sync_dir)
        if os.path.exists(sync_dir):
            binds[sync_dir] = "/sync"
        
        data_dir = os.path.expanduser(self._container_config.data_dir)
        if os.path.exists(data_dir):
            binds[data_dir] = "/data"
        
        socket_path = os.path.expanduser(self._container_config.socket_path)
        socket_dir = os.path.dirname(socket_path)
        if os.path.exists(socket_dir):
            binds[socket_dir] = "/socket"
        
        return binds
    
    def _get_environment(self) -> Dict[str, str]:
        """Get environment variables for container."""
        return {
            "MESHLOOM_DATA_DIR": "/data",
            "MESHLOOM_SYNC_DIR": "/sync",
            "MESHLOOM_SOCKET_PATH": "/socket/meshloom.sock",
            "PATH": "/usr/local/bin:/usr/bin:/bin:/sbin:/usr/sbin",
        }
    
    async def stop(self, timeout: int = 10) -> bool:
        """
        Stop the container gracefully.
        
        Args:
            timeout: Maximum seconds to wait for graceful shutdown
            
        Returns:
            True if stopped successfully, False otherwise
        """
        if self._state not in (ContainerState.RUNNING, ContainerState.STARTING):
            self._diag.warn("container", f"Cannot stop container in state: {self._state.name}")
            return True
        
        self._set_state(ContainerState.STOPPING)
        self._diag.info("container", "Stopping container")
        
        self._stop_health_monitor()
        
        try:
            success = self._runtime.stop_container(
                self._container_config.name,
                timeout
            )
            
            self._status.pid = None
            self._start_time = None
            self._set_state(ContainerState.STOPPED)
            self._publish_event("container.stopped", {"name": self._container_config.name})
            
            self._diag.info("container", "Container stopped")
            return success
            
        except Exception as e:
            error_msg = f"Failed to stop container: {e}"
            self._diag.error("container", error_msg)
            self._set_state(ContainerState.FAILED, error_msg)
            return False
    
    async def restart(self) -> bool:
        """
        Restart the container.
        
        Returns:
            True if restart successful, False otherwise
        """
        self._diag.info("container", "Restarting container")
        
        await self.stop()
        
        await asyncio.sleep(1)
        
        return await self.start()
    
    async def execute(
        self,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: int = 60,
    ) -> ExecResult:
        """
        Execute a command inside the container.
        
        Args:
            command: Command and arguments to execute
            env: Optional environment variables
            cwd: Optional working directory
            timeout: Execution timeout in seconds
            
        Returns:
            ExecResult with exit code, stdout, stderr, and duration
        """
        start_time = time.time()
        
        if self._state != ContainerState.RUNNING:
            return ExecResult(
                exit_code=1,
                stdout="",
                stderr=f"Container not running (state: {self._state.name})",
                duration_ms=0.0,
            )
        
        try:
            exit_code, stdout, stderr = self._runtime.exec_command(
                self._container_config.name,
                command,
                env,
                cwd,
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            self._publish_event("container.executed", {
                "command": " ".join(command),
                "exit_code": exit_code,
                "duration_ms": duration_ms,
            })
            
            return ExecResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_ms=duration_ms,
            )
            
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return ExecResult(
                exit_code=1,
                stdout="",
                stderr=str(e),
                duration_ms=duration_ms,
            )
    
    async def shell(self) -> bool:
        """
        Get shell access inside container.
        
        Returns:
            True if shell started, False otherwise
        """
        if self._state != ContainerState.RUNNING:
            self._diag.error("container", "Container not running")
            return False
        
        self._diag.info("container", "Starting interactive shell")
        
        result = await self.execute(
            ["/bin/sh"],
            timeout=3600,
        )
        
        return result.exit_code == 0
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get container status information.
        
        Returns:
            Dictionary with container status
        """
        status = self.status
        
        return {
            "state": str(status.state),
            "running": status.state == ContainerState.RUNNING,
            "pid": status.pid,
            "uptime_seconds": status.uptime_seconds,
            "restart_count": self._restart_count,
            "runtime": self._runtime.get_name(),
            "rootfs_path": self._container_config.rootfs_path,
            "image": self._container_config.image,
            "error": status.last_error,
        }
    
    def is_running(self) -> bool:
        """Check if container is currently running."""
        return self._state == ContainerState.RUNNING
    
    def _start_health_monitor(self) -> None:
        """Start the health monitoring loop."""
        self._health_monitor_running = True
        
        async def health_loop():
            while self._health_monitor_running:
                try:
                    await asyncio.sleep(self._container_config.health_check_interval)
                    
                    if not self._health_check():
                        self._diag.warn("container", "Health check failed")
                        
                        if self._container_config.restart_policy != "no":
                            self._restart_count += 1
                            self._diag.info("container", f"Auto-restarting (attempt {self._restart_count})")
                            
                            await self.restart()
                            
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self._diag.error("container", f"Health monitor error: {e}")
        
        self._health_monitor_task = asyncio.create_task(health_loop())
    
    def _stop_health_monitor(self) -> None:
        """Stop the health monitoring loop."""
        self._health_monitor_running = False
        
        if self._health_monitor_task:
            self._health_monitor_task.cancel()
            self._health_monitor_task = None
    
    def _health_check(self) -> bool:
        """Perform health check on container."""
        if self._state != ContainerState.RUNNING:
            return False
        
        if not self._status.pid:
            return False
        
        try:
            os.kill(self._status.pid, 0)
        except OSError:
            return False
        
        return True
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check and return status.
        
        Returns:
            Dictionary with health check results
        """
        is_healthy = self._health_check()
        
        return {
            "healthy": is_healthy,
            "state": str(self.state),
            "pid": self._status.pid,
            "uptime_seconds": self._get_uptime(),
            "restart_count": self._restart_count,
        }
    
    def get_container_info(self) -> Dict[str, Any]:
        """
        Get detailed container information.
        
        Returns:
            Dictionary with container details
        """
        return {
            "config": {
                "name": self._container_config.name,
                "image": self._container_config.image,
                "rootfs_path": self._container_config.rootfs_path,
                "sync_dir": self._container_config.sync_dir,
                "socket_path": self._container_config.socket_path,
                "auto_start": self._container_config.auto_start,
                "restart_policy": self._container_config.restart_policy,
            },
            "runtime": self._runtime.get_name(),
            "status": self.get_status(),
        }