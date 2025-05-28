import re
import docker
import socket
from pathlib import Path
from typing import Dict, Optional


class DockerPathResolver:
    """
    A class to resolve container paths to host paths when running Docker-in-Docker.

    This is useful when you need to mount volumes from within a container to a sub-container,
    and you need to translate the container paths to actual host filesystem paths.
    """

    def __init__(self):
        self._docker_client = None
        self._current_container = None
        self._binds_cache = None

    @property
    def docker_client(self):
        """Lazy initialization of Docker client"""
        if self._docker_client is None:
            self._docker_client = docker.from_env()
        return self._docker_client

    def in_docker(self) -> bool:
        """
        Check if currently running inside a Docker container.

        Returns:
            bool: True if running in Docker, False otherwise
        """
        try:
            with open('/proc/1/cgroup', 'rt') as cgroup_file:
                return 'docker' in cgroup_file.read()
        except (FileNotFoundError, PermissionError):
            return False

    def get_current_container(self):
        """
        Get the current container object by matching hostname.

        Returns:
            Container: Docker container object for the current container

        Raises:
            ValueError: If not running in Docker or container not found
        """
        if self._current_container is not None:
            return self._current_container

        if not self.in_docker():
            raise ValueError('Not running in Docker container')

        hostname = socket.gethostname()

        try:
            for container in self.docker_client.containers.list():
                if container.attrs['Config']['Hostname'] == hostname:
                    self._current_container = container
                    return container
        except Exception as e:
            raise ValueError(f'Could not access Docker API: {e}')

        raise ValueError(f'No container found with hostname: {hostname}')

    def get_binds(self) -> Dict[str, str]:
        """
        Get all bind mounts for the current container.

        Returns:
            Dict[str, str]: Dictionary mapping container paths to host paths
        """
        if self._binds_cache is not None:
            return self._binds_cache

        container = self.get_current_container()
        binds = {}

        # Get bind mounts from HostConfig
        host_config_binds = container.attrs.get('HostConfig', {}).get('Binds') or []

        for bind in host_config_binds:
            parts = bind.split(':')
            if len(parts) >= 2:
                host_path = parts[0]
                container_path = parts[1]
                binds[container_path] = host_path

        # Also check Mounts section for more detailed info
        mounts = container.attrs.get('Mounts') or []
        for mount in mounts:
            if mount.get('Type') == 'bind':
                container_path = mount.get('Destination')
                host_path = mount.get('Source')
                if container_path and host_path:
                    binds[container_path] = host_path

        self._binds_cache = binds
        return binds

    def translate_path(self, container_path: str) -> str:
        """
        Translate a container path to the corresponding host path.

        Args:
            container_path: Path inside the container

        Returns:
            str: Corresponding path on the host filesystem

        Raises:
            ValueError: If path is not in any bind mount
        """
        container_path = str(Path(container_path).resolve())
        binds = self.get_binds()

        # Direct match
        if container_path in binds:
            return binds[container_path]

        # Find the longest matching mount point
        best_match = None
        best_match_len = 0

        for mount_container_path, mount_host_path in binds.items():
            # Normalize paths for comparison
            mount_container_path = str(Path(mount_container_path).resolve())

            # Check if container_path is under this mount point
            if container_path.startswith(mount_container_path):
                # Make sure it's a proper directory boundary
                if (container_path == mount_container_path or
                        container_path.startswith(mount_container_path + '/')):
                    if len(mount_container_path) > best_match_len:
                        best_match = (mount_container_path, mount_host_path)
                        best_match_len = len(mount_container_path)

        if best_match:
            mount_container_path, mount_host_path = best_match
            # Calculate relative path
            if container_path == mount_container_path:
                return mount_host_path
            else:
                relative_path = container_path[len(mount_container_path):].lstrip('/')
                return str(Path(mount_host_path) / relative_path)

        raise ValueError(
            f'Path "{container_path}" not found in any bind mount. '
            f'Available mounts: {list(binds.keys())}'
        )

    def get_host_project_path(self, container_project_path: str = '/app') -> str:
        """
        Get the host path that corresponds to the project directory in the container.

        Args:
            container_project_path: Path to project inside container (default: '/app')

        Returns:
            str: Host path for the project directory
        """
        try:
            if not self.in_docker():
                # If not in Docker, return current directory
                return str(Path.cwd().resolve())

            return self.translate_path(container_project_path)

        except Exception as e:
            raise RuntimeError(
                f'Could not resolve host path for "{container_project_path}": {e}'
            )

    def clear_cache(self):
        """Clear cached data (useful if container mounts have changed)"""
        self._current_container = None
        self._binds_cache = None

    def debug_info(self) -> Dict:
        """
        Get debugging information about the current container and mounts.

        Returns:
            Dict: Debug information
        """
        try:
            info = {
                'in_docker': self.in_docker(),
                'hostname': socket.gethostname(),
            }

            if self.in_docker():
                container = self.get_current_container()
                info.update({
                    'container_id': container.id[:12],
                    'container_name': container.name,
                    'binds': self.get_binds(),
                })

            return info

        except Exception as e:
            return {'error': str(e)}