"""Core engine for AMV that orchestrates all components."""
from typing import Optional, Dict, Any, Union
import asyncio
import datetime
import uuid
from fastapi import FastAPI, Request
import uvicorn
import httpx
from typing import cast

from src.pterodactyl.pterodactyl import PterodactylManager
from src.discord_bot.bot import Bot
from .logging_config import setup_logging
from .mod_manager import ModVersionManager
from .api_router import APIRouterManager
import settings

class AMVEngine:
    def __init__(self, settings_obj: Any) -> None:
        """Initialize AMV Engine with configuration."""
        self.settings = settings_obj
        self.app: FastAPI = FastAPI(
            title="AMV API",
            description="API for Automatic Mod Validator",
            version="1.0.0"
        )
        self.proxmox_manager: Optional[Any] = None  # Temporarily disabled
        self.pterodactyl_manager: Optional[PterodactylManager] = None
        self.bot: Optional[Bot] = None
        self.mod_manager = ModVersionManager(settings_obj)
        self.logger = setup_logging(__name__)

        # Add middleware
        @self.app.middleware("http")
        async def add_request_id(request: Request, call_next):
            """Add unique request ID to each request."""
            request_id = str(uuid.uuid4())
            request.state.request_id = request_id  # Set the request_id in state
            self.logger.debug(f"Processing request {request_id}: {request.method} {request.url.path}")
            try:
                response = await call_next(request)
                return response
            except Exception as e:
                self.logger.error(f"Error processing request {request_id}: {e}")
                raise
        
        # Set up API router
        api_router = APIRouterManager(self)
        self.app.include_router(api_router.router)

    async def initialize(self) -> None:
        """Initialize all components."""
        await self._init_proxmox()
        await self._init_pterodactyl()

        # Create a FastAPI server config
        config = uvicorn.Config(
            app=self.app,
            host=self.settings.API_HOST,
            port=self.settings.API_PORT,
            loop="auto"
        )
        server = uvicorn.Server(config)
        
        # Initialize bot with type checking
        self.bot = Bot(self.settings, logger=self.logger)
        self.logger.info("Discord bot initialized successfully")
        
        # Run bot and server concurrently
        try:
            if not self.settings.BOTTOKEN:
                raise ValueError("Bot token not configured")
            await asyncio.gather(
                self.bot.start(self.settings.BOTTOKEN),
                server.serve()
            )
        except Exception as e:
            self.logger.error(f"Failed to run services: {e}", exc_info=True)
            raise

    async def _init_pterodactyl(self) -> None:
        """Initialize Pterodactyl integration."""
        try:
            if not all([
                self.settings.PTERODACTYL_API_KEY,
                self.settings.PTERODACTYL_API_URL,
                self.settings.PTERODACTYL_EGG_ID,
                self.settings.PTERODACTYL_NEST_ID,
            ]):
                self.logger.warning("Pterodactyl configuration incomplete, skipping initialization")
                return

            self.pterodactyl_manager = PterodactylManager(
                api_key=str(self.settings.PTERODACTYL_API_KEY),
                base_url=str(self.settings.PTERODACTYL_API_URL),
                egg_id=int(self.settings.PTERODACTYL_EGG_ID),
                nest_id=int(self.settings.PTERODACTYL_NEST_ID),
                server_name="AMV Server",
            )
            self.logger.info("Pterodactyl manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Pterodactyl manager: {e}", exc_info=True)
            self.pterodactyl_manager = None
            raise

    async def _init_proxmox(self) -> None:
        """Initialize Proxmox integration."""
        self.logger.info("Proxmox integration temporarily disabled")
        pass

    async def get_status(self) -> Dict[str, str]:
        """Get current status of the engine."""
        try:
            has_server = "false"
            if self.pterodactyl_manager:
                # Get full server status
                server_status = await self.pterodactyl_manager.get_status()
                has_server = server_status.get("has_server", "false")

            is_installed = "false"
            if self.pterodactyl_manager:
                is_installed = str(await self.pterodactyl_manager.IsInstalled()).lower()

            return {
                "status": "RUNNING" if has_server == "true" else "NOT_RUNNING",
                "has_server": has_server,
                "is_installed": is_installed
            }
        except Exception as e:
            self.logger.error(f"Error getting engine status: {e}", exc_info=True)
            return {
                "status": "ERROR",
                "has_server": "false",
                "is_installed": "false",
                "error": str(e)
            }

    async def _get_update_status(self, stage: str, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Helper method to generate standardized status updates."""
        base_status: Dict[str, Any] = {
            "status": "In Progress",
            "stage": stage,
            "timestamp": datetime.datetime.now().isoformat(),
            "mod_info": {
                "name": self.settings.MOD_INFO["title"],
                "slug": self.settings.MOD_INFO["slug"],
                "version": self.settings.LATEST_VERSION
            },
            "server_info": {
                "id": self.pterodactyl_manager.server_id if self.pterodactyl_manager else None,
                "name": self.pterodactyl_manager.current_server_name if self.pterodactyl_manager else None
            }
        }
        if details:
            base_status.update(details)
        return base_status

    async def delete_server(self) -> None:
        """Delete the current Minecraft server in Pterodactyl."""
        if self.pterodactyl_manager:
            result = await self.pterodactyl_manager.deleteServer()
            if result:
                self.logger.info("Server deleted successfully")
            else:
                self.logger.warning("Server deletion failed or no server found")
        else:
            self.logger.warning("No Pterodactyl manager initialized, cannot delete server")
    
    async def cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        try:
            if self.pterodactyl_manager:
                self.logger.info("Cleaning up Pterodactyl resources...")
                await self.pterodactyl_manager.deleteServer()

            if self.proxmox_manager:
                self.logger.info("Cleaning up Proxmox resources...")
                # Add cleanup code for Proxmox VMs here

            if self.bot and not self.bot.is_closed():
                self.logger.info("Closing Discord bot...")
                await self.bot.close()

        except Exception as e:
            self.logger.error(f"Error during cleanup: {e}")
            raise
        finally:
            self.logger.info("Cleanup complete")

    async def handle_mod_update(self) -> bool:
        """Handle a mod update request."""
        try:
            self.logger.info("Starting mod update process...")
            if not self.pterodactyl_manager:
                raise RuntimeError("Pterodactyl manager not initialized")

            # Use the mod manager to handle the update
            return await self.mod_manager.update_mod(self.pterodactyl_manager)
        except Exception as e:
            self.logger.error(f"Failed to handle mod update: {e}", exc_info=True)
            raise

    async def _handle_mod_update_request(self):
        """Handle POST request to /ModUpdate."""
        try:
            success = await self.handle_mod_update()
            return {
                "status": "Success" if success else "Failed",
                "message": "Update request processed" if success else "Update request failed",
                "details": {
                    "mod_name": self.settings.MOD_INFO["title"],
                    "server_id": self.pterodactyl_manager.server_id if self.pterodactyl_manager else None,
                    "server_name": self.pterodactyl_manager.current_server_name if self.pterodactyl_manager else None,
                    "proxmox_status": "disabled",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.logger.error(f"Failed to handle mod update request: {e}", exc_info=True)
            return {
                "status": "Failed", 
                "message": f"Update request failed: {str(e)}",
                "details": error_details
            }

    async def _handle_status_request(self):
        """Handle GET request to /UpdateStatus."""
        try:
            base_status = await self.get_status()
            detailed_status = {
                "status": "Success",
                "message": "Status retrieved successfully",
                "data": {
                    "engine_status": base_status,
                    "pterodactyl": {
                        "server_id": self.pterodactyl_manager.server_id if self.pterodactyl_manager else None,
                        "server_name": self.pterodactyl_manager.current_server_name if self.pterodactyl_manager else None,
                        "is_initialized": bool(self.pterodactyl_manager)
                    },
                    "proxmox": {
                        "status": "disabled",
                        "is_initialized": bool(self.proxmox_manager)
                    },
                    "discord_bot": {
                        "is_ready": bool(self.bot and self.bot.is_ready()),
                        "connected_guilds": len(self.bot.guilds) if self.bot else 0
                    },
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }
            return detailed_status
        except Exception as e:
            error_details = {
                "error_type": type(e).__name__,
                "error_message": str(e),
                "timestamp": datetime.datetime.now().isoformat()
            }
            self.logger.error(f"Failed to get status: {e}", exc_info=True)
            return {
                "status": "Failed",
                "message": f"Status check failed: {str(e)}",
                "details": error_details
            }
