from pydactyl import PterodactylClient
import asyncio
import logging
import aiohttp
import httpx
import json
import requests
from typing import Optional, Dict, Any, Union, TypeVar, Callable
from functools import partial
import settings

T = TypeVar('T')

class PterodactylManager:
    def __init__(self, api_key: str, base_url: str, egg_id: int, nest_id: int, server_name: str, settings_obj: Optional[Any] = None) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.egg_id = egg_id
        self.nest_id = nest_id
        self.server_name = server_name
        self.settings = settings_obj
        self.server_id = None
        self.current_server_name = None
        self.server_identifier = None
        self.user = None
        
        # Configure timeouts and retries
        self.DEFAULT_TIMEOUT = 30.0  # 30 seconds
        self.LONG_TIMEOUT = 300.0    # 5 minutes
        self.MAX_RETRIES = 3
        self._session = None
        
        # Initialize standard client
        self.client = PterodactylClient(url=base_url, api_key=api_key)

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get the current session or create a new one."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={
                    'Authorization': f'Bearer {self.api_key}',
                    'Content-Type': 'application/json',
                    'Accept': 'application/json',
                },
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            )
        return self._session

    async def cleanup(self) -> None:
        """Clean up resources."""
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def _retry_operation(self, operation: Callable[..., T], *args, timeout: Optional[float] = None, **kwargs) -> T:
        """Execute an operation with retries."""
        last_error = None
        timeout = timeout or self.DEFAULT_TIMEOUT

        for attempt in range(self.MAX_RETRIES):
            try:
                if attempt > 0:
                    await asyncio.sleep(min(2 ** attempt, 10))

                # Run the operation in the default executor
                loop = asyncio.get_event_loop()
                try:
                    async with asyncio.timeout(timeout):
                        result = await loop.run_in_executor(
                            None,
                            lambda: operation(*args, **kwargs)
                        )
                        return result
                except asyncio.TimeoutError as e:
                    raise TimeoutError(f"Operation timed out after {timeout} seconds") from e

            except TimeoutError as e:
                last_error = e
                logging.warning(f"Operation timed out (attempt {attempt + 1}/{self.MAX_RETRIES})")
            except Exception as e:
                last_error = e
                # Check if it's a retriable error
                if hasattr(e, 'response'):
                    status = getattr(getattr(e, 'response', None), 'status_code', 0)
                    if status < 500 and status != 429:  # Don't retry 4xx except 429
                        raise
                logging.warning(f"Operation failed (attempt {attempt + 1}/{self.MAX_RETRIES}): {e}")

        raise last_error or Exception("Operation failed after all retries")

    async def create_server(self, target_version_id=None, preferred_loaders=None) -> bool:
        """Create a new server with retry logic."""
        try:
            if self.server_id:
                await self.deleteServer()

            async with asyncio.timeout(self.LONG_TIMEOUT):
                # Get version info based on target version or get latest
                if target_version_id:
                    logging.info(f"Attempting to use specific version ID: {target_version_id}")
                    async with self.session.get(
                        f"https://api.modrinth.com/v2/version/{target_version_id}",
                        timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
                    ) as response:
                        response.raise_for_status()
                        target_version = await response.json()
                    
                    # Verify version compatibility
                    version_loaders = [l.lower() for l in target_version.get('loaders', [])]
                    compatible_loader = next(
                        (loader for loader in (preferred_loaders or ['fabric']) 
                         if loader in version_loaders),
                        None
                    )
                    
                    if not compatible_loader:
                        # Fall back to latest compatible version
                        target_version = await self._get_latest_version(preferred_loaders)
                else:
                    target_version = await self._get_latest_version(preferred_loaders)
                
                if not target_version:
                    raise ValueError("Could not find a suitable version")
                
                # Create the server
                server_data = await self._create_server_instance(target_version)
                if not server_data:
                    raise ValueError("Failed to create server instance")
                
                # Wait for server installation
                if not await self.wait_for_server_installation():
                    logging.error("Server installation failed or timed out")
                    await self.deleteServer()
                    return False
                
                # Upload mod file if configured
                mod_file = None
                if self.settings:
                    mod_file = getattr(self.settings, 'MOD_FILE_PATH', None)
                    if not mod_file and hasattr(self.settings, 'get'):
                        mod_file = self.settings.get('MOD_FILE_PATH')
                
                if mod_file:
                    if not await self.upload_mod_file(str(mod_file)):
                        logging.error("Failed to upload mod file")
                        await self.deleteServer()
                        return False
                
                return True

        except asyncio.TimeoutError:
            logging.error("Server creation timed out")
            if self.server_id:
                await self.deleteServer()
            return False
        except Exception as e:
            logging.error(f"Failed to create server: {e}", exc_info=True)
            if self.server_id:
                await self.deleteServer()
            return False

    async def _get_latest_version(self, preferred_loaders=None) -> Optional[Dict]:
        """Get latest version info with loader preference."""
        preferred_loaders = preferred_loaders or ['fabric']
        
        try:
            async with self.session.get(
                f"https://api.modrinth.com/v2/project/{settings.MOD_ID}/version",
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                versions = await response.json()

            if not versions:
                raise ValueError("No versions found for the mod")

            # Group versions by game version and loader
            mc_versions = {}
            for version in versions:
                for mc_ver in version.get('game_versions', []):
                    if mc_ver not in mc_versions:
                        mc_versions[mc_ver] = {}
                    
                    for loader in version.get('loaders', []):
                        loader = loader.lower()
                        if loader not in mc_versions[mc_ver]:
                            mc_versions[mc_ver][loader] = []
                        mc_versions[mc_ver][loader].append(version)

            # Find latest compatible version
            for loader in preferred_loaders:
                for mc_version in sorted(
                    mc_versions.keys(),
                    key=lambda v: [int(x) for x in v.split('.')],
                    reverse=True
                ):
                    loader_versions = mc_versions.get(mc_version, {}).get(loader, [])
                    if loader_versions:
                        return sorted(
                            loader_versions,
                            key=lambda x: x.get('date_published', ''),
                            reverse=True
                        )[0]

            raise ValueError(f"No suitable version found with preferred loaders: {preferred_loaders}")

        except Exception as e:
            logging.error(f"Failed to get latest version info: {e}", exc_info=True)
            raise

    async def _create_server_instance(self, version_info: Dict) -> Optional[Dict]:
        """Create a server instance with the specified version.
        
        Args:
            version_info: Dictionary containing version information
            
        Returns:
            Optional[Dict]: Server data on success, None on failure
        """
        if not self.user or not isinstance(self.user, dict) or "attributes" not in self.user:
            logging.error("No valid user available for server creation")
            return None

        try:
            if not version_info or not isinstance(version_info, dict):
                raise ValueError("Invalid version info provided")

            version_id = version_info.get("id")
            if not version_id:
                raise ValueError("Version ID not found in version info")

            loader_info = next(
                (l.lower() for l in version_info.get('loaders', []) 
                 if l.lower() in ['fabric', 'neoforge', 'forge']),
                'fabric'
            )
            
            self.current_server_name = (
                f"AMV: {self.server_name} - {version_info.get('name', 'Unknown')} "
                f"({loader_info})"
            )

            logging.info(f"Creating server with name: {self.current_server_name}")
            logging.debug(f"Version details: {json.dumps(version_info, indent=2)}")

            game_versions = version_info.get('game_versions', [])
            if not game_versions:
                raise ValueError("No game versions found in version info")

            # Prepare environment variables
            env_vars = {
                "MINECRAFT_VERSION": game_versions[0],
                "MOD_LOADER_TYPE": loader_info,
                "SERVER_JARFILE": "server.jar",
                "MEMORY_LIMIT": str(getattr(settings, 'SERVER_MEMORY_LIMIT', 8192)),
            }

            # Create server with retry logic
            server_data = await self._retry_operation(
                self.client.servers.create_server,
                name=self.current_server_name,
                user_id=self.user["attributes"]["id"],
                nest_id=self.nest_id,
                egg_id=self.egg_id,
                memory_limit=getattr(settings, 'SERVER_MEMORY_LIMIT', 8192),
                swap_limit=0,
                disk_limit=getattr(settings, 'SERVER_DISK_LIMIT', 10240),
                io_limit=500,
                cpu_limit=getattr(settings, 'SERVER_CPU_LIMIT', 400),
                database_limit=0,
                allocation_limit=0,
                backup_limit=0,
                environment=env_vars,
                location_ids=[1],
                image="ghcr.io/pterodactyl/yolks:java_21",
                startup_command="java -Xms128M -XX:MaxRAMPercentage=95.0 -Dterminal.jline=false -Dterminal.ansi=true -jar server.jar",
                description=f"Server for {self.current_server_name}. Testing purposes only."
            )

            if not server_data or not isinstance(server_data, dict):
                raise ValueError("Invalid server creation response")

            attributes = server_data.get('attributes', {})
            if not isinstance(attributes, dict):
                raise ValueError("Invalid attributes in server creation response")

            self.server_id = attributes.get('id')
            self.server_identifier = attributes.get('identifier')

            if not self.server_id or not self.server_identifier:
                raise ValueError("Missing server ID or identifier in response")

            logging.info("Server created successfully:")
            logging.info(f"- Name: {self.current_server_name}")
            logging.info(f"- ID: {self.server_id}")
            logging.info(f"- Identifier: {self.server_identifier}")

            return server_data

        except Exception as e:
            logging.error(f"Failed to create server instance: {e}", exc_info=True)
            self.server_id = None
            self.current_server_name = None
            self.server_identifier = None
            return None
        
    async def check_server(self) -> bool:
        """Check if the current server exists and is accessible.
        
        Returns:
            bool: True if server exists and is accessible, False otherwise.
        """
        if not self.server_id:
            logging.debug("No server ID available to check")
            return False
            
        try:
            # Try to get server details using the server ID
            server_list = self.client.servers.list_servers()
            if not server_list:
                logging.debug("No servers found")
                return False

            for server in server_list:
                if not server:
                    continue
                for data in server:
                    if not isinstance(data, dict) or "attributes" not in data:
                        continue
                    attributes = data.get("attributes", {})
                    if not attributes:
                        continue
                        
                    server_id = attributes.get("id")
                    if str(server_id) == str(self.server_id):
                        server_name = attributes.get("name", "Unknown")
                        logging.debug(f"Found server: {server_name} (ID: {self.server_id})")
                        return True
            
            logging.debug(f"Server with ID {self.server_id} not found")
            return False
            
        except Exception as e:
            logging.error(f"Error checking server status: {e}")
            return False

    async def get_status(self) -> dict:
        """Get the current status of the server.
        
        Returns:
            dict: Server status information including whether it exists and its current state.
        """
        status = {
            "has_server": "false",
            "server_state": "unknown",
            "server_id": self.server_id,
            "server_name": self.current_server_name
        }
        
        if not self.server_id:
            return status
            
        try:
            # Try to get server details using the server ID
            server_list = self.client.servers.list_servers()
            if not server_list:
                return status

            for server in server_list:
                if not server:
                    continue
                for data in server:
                    if not isinstance(data, dict) or "attributes" not in data:
                        continue
                    attributes = data.get("attributes", {})
                    if not attributes:
                        continue
                        
                    server_id = attributes.get("id")
                    if str(server_id) == str(self.server_id):
                        status["has_server"] = "true"
                        status["server_state"] = attributes.get("status", "unknown")
                        return status
            
            return status
            
        except Exception as e:
            logging.error(f"Error getting server status: {e}")
            return status

    async def deleteServer(self) -> bool:
        """Delete the current server if it exists."""
        if not self.server_id:
            logging.info("No server ID to delete")
            return True
            
        try:
            server_found = False
            
            # List servers with retry
            server_list = await self._retry_operation(
                self.client.servers.list_servers,
                timeout=self.DEFAULT_TIMEOUT
            )
            
            if not server_list:
                logging.info("No servers found to delete")
                return True

            for server in server_list:
                if not server or not isinstance(server, dict):
                    continue

                attributes = server.get('attributes', {})
                if not isinstance(attributes, dict):
                    continue

                server_name = attributes.get('name', '')
                server_id = attributes.get('id')

                if server_id and server_name and (
                    str(server_id) == str(self.server_id) or 
                    (server_name == self.current_server_name and server_name.startswith("AMV:"))
                ):
                    # Verify before deletion
                    logging.info(f"Found server to delete: {server_name} (ID: {server_id})")
                    
                    if not server_name.startswith("AMV:"):
                        logging.error(f"Safety check failed: Server {server_name} doesn't start with AMV: prefix")
                        continue

                    # Delete with retry
                    await self._retry_operation(
                        self.client.servers.delete_server,
                        server_id,
                        timeout=self.DEFAULT_TIMEOUT
                    )
                    
                    logging.info(f"Successfully deleted server: {server_name} (ID: {server_id})")
                    server_found = True
                    break

            # Reset server attributes
            self.server_id = None
            self.current_server_name = None
            self.server_identifier = None

            if not server_found:
                logging.info("No matching server found to delete")

            return True

        except Exception as e:
            logging.error(f"Failed to delete server: {e}", exc_info=True)
            return False

    async def IsInstalled(self) -> bool:
        """Check if the Pterodactyl server is installed and configured.
        
        Returns:
            bool: True if the server is installed, False otherwise.
        """
        try:
            # Check if we can list servers - this validates our connection and API key
            server_list = self.client.servers.list_servers()
            if server_list:
                logging.debug("Successfully connected to Pterodactyl panel")
                return True
            logging.warning("Could not list servers - Pterodactyl may not be properly configured")
            return False
        except Exception as e:
            logging.error(f"Error checking Pterodactyl installation: {e}")
            return False

    async def _get_files(self, path: str = '/') -> Dict:
        """Get list of files at specified path."""
        try:
            async with self.session.get(
                f'{self.base_url}/api/client/servers/{self.server_identifier}/files/list',
                params={'directory': path},
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                return await response.json()
        except Exception as e:
            logging.error(f"Failed to list files at {path}: {e}")
            return {'data': []}

    async def _create_directory(self, path: str) -> bool:
        """Create a directory at specified path."""
        try:
            async with self.session.post(
                f'{self.base_url}/api/client/servers/{self.server_identifier}/files/create-folder',
                json={'name': path},
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            logging.error(f"Failed to create directory {path}: {e}")
            return False

    async def _delete_files(self, files: list) -> bool:
        """Delete specified files."""
        try:
            async with self.session.post(
                f'{self.base_url}/api/client/servers/{self.server_identifier}/files/delete',
                json={'root': '/mods', 'files': files},
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                return True
        except Exception as e:
            logging.error(f"Failed to delete files {files}: {e}")
            return False

    async def _get_upload_url(self) -> Optional[str]:
        """Get URL for file upload."""
        try:
            async with self.session.get(
                f'{self.base_url}/api/client/servers/{self.server_identifier}/files/upload',
                timeout=aiohttp.ClientTimeout(total=self.DEFAULT_TIMEOUT)
            ) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get('attributes', {}).get('url')
        except Exception as e:
            logging.error(f"Failed to get upload URL: {e}")
            return None

    async def upload_mod_file(self, file_path: str) -> bool:
        """Upload mod file to server with retry logic."""
        if not self.server_id or not self.server_identifier:
            logging.error("No server available for mod upload")
            return False

        try:
            # Create mods directory
            await self._create_directory('mods')

            # List existing files
            files = await self._get_files('/mods')
            if files and isinstance(files, dict):
                # Clean up old mod files
                files_to_delete = [
                    file['attributes']['name']
                    for file in files.get('data', [])
                    if file.get('attributes', {}).get('name', '').endswith('.jar')
                ]
                if files_to_delete:
                    await self._delete_files(files_to_delete)
                    logging.info(f"Deleted old mod files: {files_to_delete}")

            # Get upload URL
            upload_url = await self._get_upload_url()
            if not upload_url:
                raise ValueError("Failed to get upload URL")

            # Upload new mod file
            async with aiohttp.ClientSession() as session:
                with open(file_path, 'rb') as f:
                    data = aiohttp.FormData()
                    data.add_field('files', f, filename=file_path.split('/')[-1])

                    async with session.post(
                        upload_url,
                        data=data,
                        timeout=aiohttp.ClientTimeout(total=self.LONG_TIMEOUT)
                    ) as response:
                        response.raise_for_status()
                        logging.info(f"Successfully uploaded mod file: {file_path}")
                        return True

        except Exception as e:
            logging.error(f"Failed to upload mod file: {e}", exc_info=True)
            return False

    async def wait_for_server_installation(self, timeout_seconds: int = 300) -> bool:
        """Wait for server installation to complete.
        
        Args:
            timeout_seconds: Maximum time to wait in seconds
            
        Returns:
            bool: True if server is installed and running, False if timeout or error
        """
        import asyncio
        import time
        
        start_time = time.time()
        check_interval = 5  # Check every 5 seconds
        
        logging.info(f"Waiting for server {self.server_id} installation to complete...")
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Get current server status
                status = await self.get_status()
                server_state = status.get("server_state", "unknown").lower()
                
                # Check if server is in a final state
                if server_state in ["running", "ready", "installed"]:
                    logging.info(f"Server {self.server_id} is ready (state: {server_state})")
                    return True
                elif server_state in ["install_failed", "error", "failed"]:
                    logging.error(f"Server installation failed (state: {server_state})")
                    return False
                    
                logging.debug(f"Server {self.server_id} still installing (state: {server_state})")
                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logging.error(f"Error checking server installation status: {e}")
                return False
                
        logging.error(f"Timeout waiting for server {self.server_id} installation")
        return False