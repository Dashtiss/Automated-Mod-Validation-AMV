import logging
from pydactyl import PterodactylClient
import requests
import settings


class PterodactylManager:
    def __init__(self, api_key: str, base_url: str, egg_id: int, nest_id: int, server_name: str) -> None:
        logging.debug(f"Initializing PterodactylManager with base_url: {base_url}, egg_id: {egg_id}, nest_id: {nest_id}")
        self.client = PterodactylClient(base_url, api_key, debug=False)
        self.egg_id = egg_id
        self.nest_id = nest_id
        self.server_name = server_name
        self.current_server_name = None  # Store the full server name after creation
        
        self.user = self._getTestingUser()
        
        if self.user is None:
            logging.info("Creating new testing user...")
            self.client.user.create_user(
                username="TestingUser",
                email="TestingUser@localhost",
                first_name="Testing",
                last_name="User",
            )
            self.user = self._getTestingUser()
            
        logging.info(f"Using test user: {self.user['attributes']['username']}")
        # self.create_server()

    def _getTestingUser(self):
        try:
            for user in self.client.user.list_users():
                for data in user:
                    if data["attributes"]["email"] == "TestingUser@localhost":
                        return data
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                logging.error("API key doesn't have sufficient permissions. Please use an Application API key.")
            else:
                logging.error(f"HTTP Error occurred while getting test user: {e}")
            return None
        except Exception as e:
            logging.error(f"Error occurred while listing users: {e}")
            return None
    
    def _getLatestVersionInfo(self):
        url = f"https://api.modrinth.com/v2/project/{settings.MOD_ID}/version"
        try:
            logging.debug(f"Fetching latest version info from: {url}")
            response = requests.get(url)
            response.raise_for_status()
            return response.json()[0]
        except requests.exceptions.HTTPError as e:    
            logging.error(f"HTTP Error occurred while fetching version info: {e}")
    
    def create_server(self):
        latest = self._getLatestVersionInfo()
        version_id = latest["id"]
        self.current_server_name = f"{self.server_name} - {latest['name']}"
        logging.info(f"Creating server with name: {self.current_server_name} and version ID: {version_id}")
        logging.debug(f"Latest version info: {latest}")
        
        environment_variables = {
            "MINECRAFT_VERSION": latest["game_versions"][0],
            "MOD_LOADER_TYPE": latest["loaders"][0],
        }
        
        try:
            self.client.servers.create_server(
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
                description=f"Server for {self.current_server_name}. Testing purposes only. Will be deleted after testing.",
            )
            logging.info(f"Successfully created server: {self.current_server_name}")
        except Exception as e:
            logging.error(f"Failed to create server: {e}")
            
    def deleteServer(self):
        """Delete the server if it exists."""
        if not hasattr(self, 'current_server_name') or not self.current_server_name:
            logging.warning("No server name set, skipping deletion")
            return
            
        try:
            for server in self.client.servers.list_servers():
                for data in server:
                    if data["attributes"]["name"] == self.current_server_name:
                        server_id = data["attributes"]["id"]
                        logging.info(f"Deleting server with ID: {server_id}")
                        try:
                            self.client.servers.delete_server(server_id)
                            logging.info(f"Successfully deleted server: {self.current_server_name}")
                        except Exception as e:
                            logging.error(f"Failed to delete server: {e}")
                        return
            logging.info(f"No server found with name: {self.current_server_name}")
        except Exception as e:
            logging.error(f"Error while trying to delete server: {e}")