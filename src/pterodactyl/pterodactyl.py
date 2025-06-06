import logging
from pydactyl import PterodactylClient
import requests
import settings
import json
from typing import Any, Dict, Optional, Union

class PterodactylManager:
    def __init__(self, api_key: str, base_url: str, egg_id: int, nest_id: int, server_name: str, settings_obj: Optional[Any] = None) -> None:
        logging.debug(f"Initializing PterodactylManager with base_url: {base_url}, egg_id: {egg_id}, nest_id: {nest_id}")
        self.client = PterodactylClient(base_url, api_key, debug=False)
        self.egg_id = egg_id
        self.nest_id = nest_id
        self.server_name = server_name
        self.current_server_name = None  # Store the full server name after creation
        self.server_id = None
        self.settings = settings_obj
        self.server_identifier = None  # Initialize server identifier
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        
        # Initialize user with proper validation
        self.user = None
        user_data = self._getTestingUser()
        if user_data and isinstance(user_data, dict) and "attributes" in user_data:
            self.user = user_data
        
        if self.user is None:
            logging.info("Creating new testing user...")
            try:
                self.client.user.create_user(
                    username="TestingUser",
                    email="TestingUser@localhost",
                    first_name="Testing",
                    last_name="User",
                )
                self.user = self._getTestingUser()
            except Exception as e:
                logging.error(f"Failed to create test user: {e}")
                
        if self.user and isinstance(self.user, dict) and "attributes" in self.user:
            username = self.user["attributes"].get("username", "Unknown")
            logging.info(f"Using test user: {username}")
        else:
            logging.error("Failed to initialize or create test user")

    def _getTestingUser(self) -> Optional[Dict[str, Any]]:
        try:
            user_list = self.client.user.list_users()
            if not user_list:
                return None
                
            for user in user_list:
                if not user:
                    continue
                for data in user:
                    if not isinstance(data, dict) or "attributes" not in data:
                        continue
                    attributes = data.get("attributes", {})
                    if not isinstance(attributes, dict):
                        continue
                        
                    if attributes.get("email") == "TestingUser@localhost":
                        return data
            return None
                        
        except requests.exceptions.HTTPError as e:
            if hasattr(e, 'response') and e.response.status_code == 403:
                logging.error("API key doesn't have sufficient permissions. Please use an Application API key.")
            else:
                logging.error(f"HTTP Error occurred while getting test user: {e}")
            return None
        except Exception as e:
            logging.error(f"Error occurred while listing users: {e}")
            return None        
    def _getLatestVersionInfo(self, preferred_loaders=None):
        """Get latest version info with loader preference.
        
        Args:
            preferred_loaders (list, optional): List of preferred mod loaders in order of preference.
                                              Defaults to ['fabric'].
        Returns:
            dict: Version information for the most appropriate version
        """
        if preferred_loaders is None:
            preferred_loaders = ['fabric']  # Default to Fabric only
            
        url = f"https://api.modrinth.com/v2/project/{settings.MOD_ID}/version"
        try:
            logging.info(f"Fetching versions from Modrinth API: {url}")
            response = requests.get(url)
            response.raise_for_status()
            versions = response.json()
            
            if not versions:
                logging.error("No versions found for the mod")
                raise ValueError("No versions found for the mod")
                
            # Group versions by game version and loader
            mc_versions = {}
            for version in versions:
                logging.debug(f"Processing version: {version.get('name')} ({version.get('version_number')})")
                for mc_ver in version.get('game_versions', []):
                    if mc_ver not in mc_versions:
                        mc_versions[mc_ver] = {}
                    
                    # Group by loader
                    for loader in version.get('loaders', []):
                        loader = loader.lower()
                        if loader not in mc_versions[mc_ver]:
                            mc_versions[mc_ver][loader] = []
                        mc_versions[mc_ver][loader].append(version)
            
            # Sort Minecraft versions by semantic versioning
            sorted_mc_versions = sorted(
                mc_versions.keys(),
                key=lambda v: [int(x) for x in v.split('.')],
                reverse=True
            )
            
            logging.info(f"Available Minecraft versions (newest first): {sorted_mc_versions}")
            
            # For each Minecraft version
            for mc_version in sorted_mc_versions:
                logging.info(f"Checking versions for Minecraft {mc_version}")
                
                # Try each preferred loader in order
                for loader in preferred_loaders:
                    loader_versions = mc_versions.get(mc_version, {}).get(loader, [])
                    if loader_versions:
                        # Sort versions by date
                        sorted_versions = sorted(
                            loader_versions,
                            key=lambda x: x.get('date_published', ''),
                            reverse=True
                        )
                        version = sorted_versions[0]
                        logging.info(
                            f"Selected version {version.get('name')} "
                            f"({version.get('version_number')}) with {loader} "
                            f"for MC {mc_version}"
                        )
                        return version
            
            # If we haven't found a version with preferred loaders, raise an error
            logging.error(
                f"No version found with preferred loaders: {preferred_loaders}. "
                f"Available loaders: {[list(mc_versions.get(v, {}).keys()) for v in sorted_mc_versions]}"
            )
            raise ValueError(f"No suitable version found with preferred loaders: {preferred_loaders}")
            
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error occurred while fetching version info: {e}")
            raise
        except Exception as e:
            logging.error(f"Error occurred while getting latest version info: {e}", exc_info=True)
            raise

    async def create_server(self, target_version_id=None, preferred_loaders=None):
        """Create a new Minecraft server in Pterodactyl and upload mod file.
        
        Args:
            target_version_id (str, optional): Specific version ID to use. If not provided,
                                             will get the latest version.
            preferred_loaders (list, optional): List of preferred mod loaders in order of preference.
                                              Defaults to ['fabric'].
        """
        if preferred_loaders is None:
            preferred_loaders = ['fabric']  # Default to Fabric only
            
        try:
            # Create server first
            if not await self._create_server_instance(target_version_id, preferred_loaders):
                return False
                
            # After server is created, upload the mod file if path is configured
            mod_file = None
            if self.settings:
                mod_file = getattr(self.settings, 'MOD_FILE_PATH', None)
                if not mod_file and hasattr(self.settings, 'get'):
                    mod_file = self.settings.get('MOD_FILE_PATH')
            
            if mod_file and await self.upload_mod_file(str(mod_file)):
                logging.info("Mod file uploaded successfully")
                return True
            else:
                logging.warning("No mod file configured or upload failed")
                return False
                
        except Exception as e:
            logging.error(f"Failed to create server or upload mod: {e}", exc_info=True)
            self.server_id = None
            self.current_server_name = None
            self.server_identifier = None
            return False

    async def _create_server_instance(self, target_version_id=None, preferred_loaders=None):
        """Internal method to handle server creation."""
        if not self.user or "attributes" not in self.user:
            logging.error("No valid user available for server creation")
            return False
            
        try:
            # Get version info based on target version or get latest
            if target_version_id:
                logging.info(f"Attempting to use specific version ID: {target_version_id}")
                url = f"https://api.modrinth.com/v2/version/{target_version_id}"
                response = requests.get(url)
                response.raise_for_status()
                target_version = response.json()
                
                # Verify this version is compatible with our preferred loaders
                version_loaders = [l.lower() for l in target_version.get('loaders', [])] if target_version.get('loaders') else []
                compatible_loader = next((loader for loader in (preferred_loaders or []) if loader in version_loaders), None)
                
                if not compatible_loader:
                    logging.warning(
                        f"Specified version {target_version_id} not compatible with preferred loaders. "
                        f"Version loaders: {version_loaders}, Preferred: {preferred_loaders}"
                    )
                    logging.info("Finding alternative version with preferred loader...")
                    target_version = self._getLatestVersionInfo(preferred_loaders)
                else:
                    logging.info(f"Using specific version: {target_version['name']} with loader {compatible_loader}")
            else:
                logging.info("No specific version requested, finding latest compatible version...")
                target_version = self._getLatestVersionInfo(preferred_loaders)
            
            if not target_version:
                raise ValueError("Could not find a suitable version")
                
            version_id = target_version["id"]
            loader_info = next((l for l in target_version.get('loaders', []) if l.lower() in (preferred_loaders or ['fabric'])), 'unknown')
            self.current_server_name = f"AMV: {self.server_name} - {target_version['name']} ({loader_info})"
            
            logging.info(f"Creating server with name: {self.current_server_name}")
            logging.debug(f"Version details: {json.dumps(target_version, indent=2)}")
            
            # Prepare environment variables
            environment_variables = {
                "MINECRAFT_VERSION": target_version["game_versions"][0],
                "MOD_LOADER_TYPE": loader_info,
            }
            
            logging.info(f"Using environment variables: {environment_variables}")
            
            # Create the server with the selected configuration
            response = self.client.servers.create_server(
                name=self.current_server_name,
                user_id=self.user["attributes"]["id"],
                nest_id=self.nest_id,
                egg_id=self.egg_id,
                memory_limit=settings.SERVER_MEMORY_LIMIT,
                swap_limit=0,
                disk_limit=settings.SERVER_DISK_LIMIT,
                environment=environment_variables,
                location_ids=[1],
                cpu_limit=settings.SERVER_CPU_LIMIT,
                database_limit=0,
                allocation_limit=0,
                backup_limit=0,
                docker_image="ghcr.io/pterodactyl/yolks:java_21",
                description=f"Server for {self.current_server_name}. Testing purposes only. Will be deleted after testing."
            )
            
            # Handle response based on pydactyl's response format
            def get_attributes(data: Any) -> Optional[Dict[str, Any]]:
                if isinstance(data, dict) and "attributes" in data:
                    attrs = data.get("attributes")
                    if isinstance(attrs, dict):
                        return attrs
                return None
            
            # Try to extract attributes from the response
            attributes = None
            if isinstance(response, dict):
                attributes = get_attributes(response)
            elif hasattr(response, "json") and callable(response.json):
                try:
                    response_data = response.json()
                    if isinstance(response_data, dict):
                        attributes = get_attributes(response_data)
                except Exception as e:
                    logging.error(f"Failed to parse response JSON: {e}")
                    
            if not attributes:
                raise ValueError(f"Could not extract attributes from response: {response}")
                
            # Extract required fields
            server_id = attributes.get("id")
            server_identifier = attributes.get("identifier")
            
            if not server_id or not server_identifier:
                raise ValueError(f"Missing required attributes in response: {attributes}")
                
            self.server_id = server_id
            self.server_identifier = server_identifier
            
            logging.info(f"Server created successfully:")
            logging.info(f"- Name: {self.current_server_name}")
            logging.info(f"- ID: {self.server_id}")
            logging.info(f"- Identifier: {self.server_identifier}")
            return True
            
        except Exception as e:
            logging.error(f"Failed to create server: {e}", exc_info=True)
            self.server_id = None
            self.current_server_name = None
            self.server_identifier = None
            return False
        
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

    async def deleteServer(self):
        """Delete the current server if it exists."""
        server_found = False
        
        try:
            server_list = self.client.servers.list_servers()
            if not server_list:
                logging.info("No servers found to delete")
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
                        
                    server_name = attributes.get("name")
                    server_id = attributes.get("id")
                    
                    if server_id and server_name and (
                        (self.server_id and str(server_id) == str(self.server_id)) or 
                        (server_name == self.current_server_name and server_name.startswith("AMV:"))
                    ):
                        # Double check to prevent accidental deletion
                        logging.info(f"Found server to delete:")
                        logging.info(f"- Name: {server_name}")
                        logging.info(f"- ID: {server_id}")
                        logging.info(f"- Expected Name: {self.current_server_name}")
                        logging.info(f"- Expected ID: {self.server_id}")

                        try:
                            # Final verification
                            if not server_name.startswith("AMV:"):
                                logging.error(f"Safety check failed: Server {server_name} doesn't start with AMV: prefix")
                                continue

                            self.client.servers.delete_server(server_id)
                            logging.info(f"Successfully deleted server: {server_name} (ID: {server_id})")
                            server_found = True
                        except Exception as e:
                            logging.error(f"Failed to delete server {server_name} (ID: {server_id}): {e}")
                        break

            if not server_found:
                logging.info("No server found to delete with the specified criteria.")
            else:
                logging.info("Server deletion process completed.")

            # Reset server attributes after deletion
            self.server_id = None
            self.current_server_name = None
            self.server_identifier = None
            
            # Return whether a server was found and deleted
            logging.debug(f"Server found and deleted: {server_found}")
            return server_found
            
        except Exception as e:
            logging.error(f"Error during server deletion: {e}")
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

    async def upload_mod_file(self, file_path: str) -> bool:
        """Upload mod file to the server.
        
        Args:
            file_path: Local path to the mod file to upload
            
        Returns:
            bool: True if upload was successful, False otherwise
        """
        if not self.server_id or not self.server_identifier:
            logging.error(f"No server available to upload mod to. Server ID: {self.server_id}, Identifier: {self.server_identifier}")
            return False
            
        try:
            logging.info(f"Starting upload process for file: {file_path}")
            
            # Check if file exists
            import os
            if not os.path.exists(file_path):
                logging.error(f"Mod file does not exist at path: {file_path}")
                return False
                
            # Create mods directory if it doesn't exist
            try:
                logging.debug(f"Creating mods directory for server {self.server_identifier}")
                self.client.client.servers.files.create_folder(
                    self.server_identifier,
                    path='/',
                    name='mods'
                )
                logging.debug("Successfully created mods directory")
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 400:
                    logging.debug("Mods directory already exists, continuing...")
                else:
                    logging.warning(f"Unexpected error creating mods directory: {e.response.text}")
            except Exception as e:
                logging.warning(f"Error during mods directory creation: {str(e)}")
            
            # Get the file name from the path
            file_name = os.path.basename(file_path)
            logging.info(f"Preparing to upload {file_name}")
            
            # Get a pre-signed upload URL for the mods directory
            logging.debug("Requesting upload URL from Pterodactyl API...")
            upload_url = self.client.client.servers.files.get_upload_file_url(
                self.server_identifier
            )
            
            if not upload_url:
                logging.error("Failed to get upload URL from API")
                return False
                
            logging.debug(f"Received upload URL: {upload_url}")
            
            # Check file size
            file_size = os.path.getsize(file_path)
            logging.info(f"File size: {file_size} bytes")
            
            # Prepare the upload with session for better error handling
            session = requests.Session()
            # Add API key to headers if needed
            session.headers.update({
                "Authorization": f"Bearer {self.api_key}"
            })
            
            logging.info("Starting file upload...")
            with open(file_path, 'rb') as f:
                files = {'files': (file_name, f)}
                try:
                    response = session.post(
                        upload_url,
                        files=files,
                        data={'directory': '/mods'}
                    )
                    logging.debug(f"Upload response status code: {response.status_code}")
                    logging.debug(f"Upload response headers: {response.headers}")
                    
                    if response.status_code >= 400:
                        logging.error(f"Upload failed with status {response.status_code}: {response.text}")
                        return False
                        
                    response.raise_for_status()
                    
                except requests.exceptions.RequestException as e:
                    logging.error(f"Request failed during upload: {str(e)}")
                    if hasattr(e, 'response') and e.response:
                        logging.error(f"Response content: {e.response.text}")
                    return False
                    
            logging.info(f"Mod file {file_name} uploaded successfully to /mods directory")
            
            # Verify the file exists after upload
            try:
                files = self.client.client.servers.files.list_files(self.server_identifier, '/mods')
                if any(f.get('attributes', {}).get('name') == file_name for f in files):
                    logging.info("File verified in mods directory after upload")
                else:
                    logging.warning("File not found in directory listing after upload")
            except Exception as e:
                logging.warning(f"Could not verify file after upload: {str(e)}")
            
            return True
            
        except Exception as e:
            logging.error(f"Failed to upload mod file: {str(e)}", exc_info=True)
            return False