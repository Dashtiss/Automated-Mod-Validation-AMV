#!/usr/bin/env python3
"""
AMV Runner Script
This script handles the initialization and running of the AMV Engine.
"""
import os
import asyncio
import logging
import signal
from types import FrameType
import sys
import uvicorn
from typing import Optional
from httpx import AsyncClient

from src.core.engine import AMVEngine
from src.utils.common import setup_logging, ShutdownManager
import settings

# Initialize global components
engine: Optional[AMVEngine] = None
shutdown_manager = ShutdownManager()

def setup_signal_handlers() -> None:
    """Setup handlers for OS signals."""
    def handle_signal(sig: int, frame: Optional[FrameType]) -> None:
        logging.info(f"Received signal {signal.Signals(sig).name}. Initiating shutdown...")
        asyncio.create_task(cleanup())

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

async def cleanup() -> None:
    """Perform cleanup tasks before shutdown."""
    global engine
    try:
        if engine:
            logging.info("Cleaning up engine resources...")
            await engine.cleanup()
    except Exception as e:
        logging.error(f"Error during cleanup: {e}")
    finally:
        logging.info("Application shutdown complete.")
        sys.exit(0)

async def check_environment() -> bool:
    """Check if all required environment variables are set."""
    required_vars = [
        'MOD_ID',
        'BOTTOKEN',
        'CHANNEL_ID',
        'CHECKER_REGEX',
        'PTERODACTYL_API_URL',
        'PTERODACTYL_API_KEY',
        'PTERODACTYL_EGG_ID'
    ]

    all_set = True
    for var in required_vars:
        if not getattr(settings, var, None):
            logging.error(f"Environment variable '{var}' is not set in `settings.py` or `.env`.")
            all_set = False
    return all_set

async def run_fastapi() -> asyncio.Task:
    """Run the FastAPI server."""
    config = uvicorn.Config(
        app=engine.app,
        host="127.0.0.1",
        port=8080,
        log_level="info"
    )
    
    server = uvicorn.Server(config)
    
    # Create a task that we can manage
    server_task = asyncio.create_task(server.serve())
    
    # Wait a short time to ensure the server is ready
    await asyncio.sleep(1)
    
    return server_task

async def main() -> None:
    """Main entry point for the AMV Engine."""
    global engine

    # Print title
    title = settings.format_title({
        "Authors": settings.AUTHORS,
        "Repo": settings.REPO_URL,
        "Version": settings.VERSION
    })
    print(title)

    # Setup logging
    setup_logging(debug=settings.DEBUG)
    logging.info("Starting AMV Engine...")

    # Check environment
    if not await check_environment():
        logging.critical("Required environment variables are missing. Exiting.")
        sys.exit(1)

    server_task = None
    try:
        # Create engine instance first
        engine = AMVEngine(settings)

        # Initialize the engine (which starts the bot)
        await engine.initialize()
        logging.info("AMV Engine initialized successfully")
        
        # Start the FastAPI server
        server_task = await run_fastapi()
        logging.info("FastAPI server started successfully")
        
        try:
            # Wait for the server task to complete (this will run until interrupted)
            await server_task
        except asyncio.CancelledError:
            pass
            
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, cleaning up...")
    except Exception as e:
        logging.critical(f"Failed to initialize AMV Engine: {e}")
        raise
    finally:
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        await cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Shutting down...")
        asyncio.run(cleanup())
    except Exception as e:
        logging.critical(f"Unexpected error: {e}")
        asyncio.run(cleanup())
        sys.exit(1)
