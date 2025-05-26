"""Core engine for AMV that orchestrates all components."""
from typing import Optional, Dict
import logging
import asyncio
from fastapi import FastAPI
from discord import Client

from src.proxmox.manager import ProxmoxManager
from src.pterodactyl.pterodactyl import PterodactylManager
from src.discord_bot.bot import Bot
import settings
class AMVEngine:
    def __init__(self, settings: settings) -> None:
        """Initialize AMV Engine with configuration."""
        self.settings = settings
        self.app: FastAPI = FastAPI()
        self.proxmox_manager: Optional[ProxmoxManager] = None
        self.pterodactyl_manager: Optional[PterodactylManager] = None
        self.bot: Optional[Bot] = None
        self.logger = logging.getLogger(__name__)
        self.stream_handler = logging.StreamHandler()
        self.stream_handler.setLevel(logging.INFO)
        self.logger.addHandler(self.stream_handler)
        self.logger.setLevel(logging.INFO)

    async def initialize(self) -> None:
        """Initialize all components."""
        await self._init_proxmox()
        await self._init_pterodactyl()
        await self._init_bot()

    async def _init_proxmox(self) -> None:
        """Initialize Proxmox connection (temporarily disabled)."""
        self.logger.info("Proxmox initialization skipped (temporarily disabled)")
        self.proxmox_manager = None  # Temporarily disabled

    async def _init_pterodactyl(self) -> None:
        """Initialize Pterodactyl connection."""
        try:
            self.pterodactyl_manager = PterodactylManager(
                api_key=self.settings.PTERODACTYL_API_KEY,
                base_url=self.settings.PTERODACTYL_API_URL,
                egg_id=self.settings.PTERODACTYL_EGG_ID,
                nest_id=self.settings.PTERODACTYL_NEST_ID,
                server_name=self.settings.MOD_INFO["title"]
            )
            self.logger.info("Pterodactyl manager initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Pterodactyl manager: {e}")
            raise

    async def _init_bot(self) -> None:
        """Initialize Discord bot."""
        try:
            self.bot = Bot(self.settings, logger=self.logger, stream_handler=self.stream_handler)
            self.logger.info("Discord bot initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize Discord bot: {e}")
            raise

    async def cleanup(self) -> None:
        """Cleanup resources before shutdown."""
        try:
            if self.pterodactyl_manager:
                self.logger.info("Cleaning up Pterodactyl resources...")
                self.pterodactyl_manager.deleteServer()

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

    async def get_status(self) -> Dict[str, str]:
        """Get current status of the engine.
        
        Returns:
            Dict[str, str]: Status information including current state and server presence
        """
        has_server = "false"
        if self.pterodactyl_manager and await self.pterodactyl_manager.check_server():
            has_server = "true"
            
        return {
                "status": "RUNNING" if has_server else "NOT_RUNNING",
                "has_server": has_server
            }
    
    async def handle_mod_update(self) -> None:
        """Handle a mod update request.
        
        This method:
        1. Creates a new Minecraft server in Pterodactyl
        2. Starts the testing process
        3. Sends notifications
        """
        try:
            # Create Minecraft server
            if not self.pterodactyl_manager:
                raise RuntimeError("Pterodactyl manager not initialized")
                
            await self.pterodactyl_manager.create_server()
            
            # Notify through Discord
            if self.bot and self.bot.is_ready():
                channel = await self.bot.get_channel(int(self.settings.CHANNEL_ID))
                if channel:
                    await channel.send(f"Starting validation for mod: {self.settings.MOD_INFO['title']}")
                    
        except Exception as e:
            self.logger.error(f"Failed to handle mod update: {e}")
            raise
