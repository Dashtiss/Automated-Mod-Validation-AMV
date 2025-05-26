"""Common utilities for the AMV project."""
import logging
import sys
from typing import Optional
from types import FrameType
import signal
import asyncio

def setup_logging(debug: bool = False) -> None:
    """Configure logging based on environment settings.
    
    Args:
        debug (bool): Whether to enable debug logging
    """
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format='[%(levelname)s] {%(asctime)s} - %(message)s',
        handlers=[logging.StreamHandler()],
        force=True
    )
    
    # Quiet down uvicorn access logs but keep error logging
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").handlers.clear()

class ShutdownManager:
    """Manages graceful shutdown of application components."""
    
    def __init__(self):
        """Initialize shutdown manager."""
        self.tasks = set()
        self.connectors = set()
    
    def add_task(self, task: asyncio.Task) -> None:
        """Add a task to be managed during shutdown."""
        self.tasks.add(task)
    
    def add_connector(self, connector) -> None:
        """Add a connector to be closed during shutdown."""
        self.connectors.add(connector)
    
    async def cleanup(self) -> None:
        """Perform cleanup of all tasks and connections."""
        logging.info("Starting cleanup sequence...")
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Close all connectors
        for connector in self.connectors:
            if not connector.closed:
                await connector.close()
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        logging.info("Cleanup sequence complete")
