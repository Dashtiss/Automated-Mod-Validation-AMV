"""Module for handling mod updates and version selection."""
import asyncio
import datetime
from typing import Dict, List, Optional
import httpx

from ..pterodactyl.pterodactyl import PterodactylManager
from ..utils.log_manager import log_manager

logger = log_manager.get_logger(__name__)

class ModVersionManager:
    def __init__(self, settings):
        """Initialize ModVersionManager.
        
        Args:
            settings: Application settings
        """
        self.settings = settings
        
    async def get_latest_version(self, preferred_loaders: Optional[List[str]] = None) -> Dict:
        """Get the latest version info prioritizing the specified loaders.
        
        Args:
            preferred_loaders: Preferred mod loaders in order.
                             Defaults to ['fabric'].
                
        Returns:
            Dict: Version information for the most suitable version
        """
        if preferred_loaders is None:
            preferred_loaders = ['fabric']  # Changed to prioritize Fabric
            
        url = f"https://api.modrinth.com/v2/project/{self.settings.MOD_ID}/version"
        async with httpx.AsyncClient() as client:
            try:
                logger.info(f"Fetching versions from Modrinth API: {url}")
                response = await client.get(url)
                response.raise_for_status()
                versions = response.json()
                
                if not versions:
                    logger.error("No versions found for the mod")
                    raise ValueError("No versions found for the mod")
                
                # Group versions by Minecraft version and loader
                mc_versions: Dict[str, Dict[str, List[Dict]]] = {}
                for version in versions:
                    version_name = version.get('name', 'unknown')
                    version_number = version.get('version_number', 'unknown')
                    logger.debug(
                        f"Processing version: {version_name} ({version_number})",
                        extra={
                            "version_id": version.get('id'),
                            "version_type": version.get('version_type'),
                            "loaders": version.get('loaders', [])
                        }
                    )
                    
                    for mc_ver in version.get('game_versions', []):
                        if mc_ver not in mc_versions:
                            mc_versions[mc_ver] = {}
                        
                        # Group by loader
                        for loader in version.get('loaders', []):
                            loader = loader.lower()
                            if loader not in mc_versions[mc_ver]:
                                mc_versions[mc_ver][loader] = []
                            mc_versions[mc_ver][loader].append(version)
                
                # Sort Minecraft versions semantically
                sorted_mc_versions = sorted(
                    mc_versions.keys(),
                    key=lambda v: [int(x) for x in v.split('.')] ,
                    reverse=True
                )
                
                logger.info(
                    f"Found {len(sorted_mc_versions)} Minecraft versions",
                    extra={
                        "minecraft_versions": sorted_mc_versions,
                        "preferred_loaders": preferred_loaders
                    }
                )
                
                # For each Minecraft version
                for mc_version in sorted_mc_versions:
                    logger.debug(f"Checking MC version: {mc_version}")
                    
                    # Try each preferred loader in order
                    for loader in preferred_loaders:
                        if loader in mc_versions[mc_version] and mc_versions[mc_version][loader]:
                            versions_for_loader = mc_versions[mc_version][loader]
                            # Sort versions by date
                            sorted_versions = sorted(
                                versions_for_loader,
                                key=lambda x: x.get('date_published', ''),
                                reverse=True
                            )
                            selected_version = sorted_versions[0]
                            logger.info(
                                f"Selected version {selected_version.get('name')} "
                                f"with {loader} for MC {mc_version}",
                                extra={
                                    "version_id": selected_version.get('id'),
                                    "version_name": selected_version.get('name'),
                                    "loader": loader,
                                    "minecraft_version": mc_version
                                }
                            )
                            return selected_version
                
                logger.warning(
                    "No version found with preferred loaders",
                    extra={
                        "preferred_loaders": preferred_loaders,
                        "available_versions": len(versions)
                    }
                )
                raise ValueError(f"No suitable version found with preferred loaders: {preferred_loaders}")
            except httpx.HTTPError as e:
                logger.error(
                    f"HTTP Error occurred while fetching version info: {e}",
                    extra={
                        "url": url,
                        "error_type": "http_error"
                    }
                )
                raise
            except Exception as e:
                logger.error(
                    f"Error occurred while getting latest version info: {e}",
                    extra={
                        "error_type": type(e).__name__,
                        "url": url
                    },
                    exc_info=True
                )
                raise

    async def update_mod(self, pterodactyl: PterodactylManager) -> bool:
        """Handle the mod update process.
        
        Args:
            pterodactyl: Instance of PterodactylManager
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            logger.info(
                "Starting mod update process",
                extra={"mod_id": self.settings.MOD_ID}
            )
            
            # Get latest version prioritizing Fabric
            latest_version = await self.get_latest_version(['fabric'])
            
            if not latest_version:
                logger.error("Failed to get latest version info")
                return False
                
            version_info = {
                "name": latest_version.get("name"),
                "version": latest_version.get("version_number"),
                "id": latest_version.get("id"),
                "game_versions": latest_version.get("game_versions", []),
                "loaders": latest_version.get("loaders", [])
            }
            
            logger.info(
                f"Creating server with version {version_info['name']}",
                extra={"version_info": version_info}
            )
            
            server_created = await pterodactyl.create_server(
                target_version_id=latest_version['id'],
                preferred_loaders=['fabric']
            )
            
            if not server_created:
                logger.error(
                    "Failed to create server",
                    extra={
                        "version_id": latest_version['id'],
                        "preferred_loaders": ['fabric']
                    }
                )
                return False
                
            logger.info(
                "Server created successfully",
                extra={
                    "server_id": pterodactyl.server_id,
                    "server_name": pterodactyl.current_server_name
                }
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Failed to handle mod update: {e}",
                extra={
                    "error_type": type(e).__name__,
                    "mod_id": self.settings.MOD_ID
                },
                exc_info=True
            )
            return False
