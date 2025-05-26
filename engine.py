import logging
from .managers.pterodactyl import PterodactylManager

class AMVEngine:
    def __init__(self):
        self.logger = logging.getLogger('AMVEngine')
        self.pterodactyl = None

    async def initialize(self, config: dict):
        try:
            # Initialize Pterodactyl manager with correct parameters
            self.pterodactyl = PterodactylManager(
                url=config['pterodactyl']['url'],
                api_key=config['pterodactyl']['api_key']
            )
            await self.pterodactyl.initialize()
        except Exception as e:
            self.logger.critical(f"Failed to initialize AMV Engine: {str(e)}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """Cleanup all resources."""
        self.logger.info("Cleaning up engine resources...")
        if self.pterodactyl:
            await self.pterodactyl.cleanup()
        self.logger.info("Cleanup complete")
