from typing import List, Optional, Dict, Any
import asyncio
import signal
import logging
from types import FrameType

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import discord
from discord.ext import commands

import settings
from bot.bot import Bot

# --- FastAPI Setup ---
app: FastAPI = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ModUpdate")
async def mod_update() -> Dict[str, str]:
    """
    Endpoint to handle mod updates.
    Returns:
        Dict[str, str]: Response message
    """
    logging.info("Mod update received via FastAPI endpoint.")
    return {"message": "Mod update received"}

# --- Logging Configuration ---
def setup_logging() -> None:
    """Configure logging based on environment settings."""
    if settings.DEVELOPMENT:
        print("DEVELOPMENT MODE ENABLED, THIS IS NOT FOR PRODUCTION")

    log_level: int = logging.DEBUG if settings.DEBUG else logging.INFO
    
    logging.basicConfig(
        level=log_level,
        format='[%(levelname)s] {%(asctime)s} - %(message)s'
    )

    stream_handler: logging.StreamHandler = logging.StreamHandler()
    stream_handler.setLevel(log_level)
    stream_handler.setFormatter(logging.Formatter('[%(levelname)s] {%(asctime)s} - %(message)s'))

    if not any(isinstance(handler, logging.StreamHandler) for handler in logging.getLogger().handlers):
        logging.getLogger().addHandler(stream_handler)

# --- Environment Variable Check ---
def check_env() -> bool:
    """
    Check if all required environment variables are set.
    Returns:
        bool: True if all variables are set, False otherwise
    """
    required_vars: List[str] = [
        'BOTTOKEN',
        'CHANNEL_ID',
        'CHECKER_REGEX',
        'PTERODACTYL_API_URL',
        'PTERODACTYL_API_KEY',
        'PROXMOX_API_URL',
        'PROXMOX_API_KEY'
    ]

    all_set: bool = True
    for var in required_vars:
        if getattr(settings, var, None) is None:
            logging.error(f"Environment variable '{var}' is not set in settings.py.")
            all_set = False
    return all_set

# --- Asynchronous Task Functions ---
async def run_fastapi_server() -> None:
    """Run the FastAPI server using uvicorn programmatically."""
    config: uvicorn.Config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8080,
        log_level="info",
        loop="asyncio"
    )
    server: uvicorn.Server = uvicorn.Server(config)
    logging.info("Starting FastAPI server on http://127.0.0.1:8080")
    await server.serve()

async def run_discord_bot_client(bot_instance: Bot, token: str) -> None:
    """
    Run the Discord bot client.
    Args:
        bot_instance (Bot): Instance of the Discord bot
        token (str): Discord bot token
    """
    logging.info("Starting Discord bot...")
    try:
        await bot_instance.start(token)
    except discord.LoginFailure:
        logging.error("Discord bot failed to log in. Check your BOTTOKEN.")
    except Exception as e:
        logging.error(f"An error occurred with the Discord bot: {e}")
    finally:
        if not bot_instance.is_closed():
            await bot_instance.close()
            logging.info("Discord bot client closed.")

# --- Main Orchestration Function ---
async def main_orchestrator() -> None:
    """Orchestrate the concurrent running of FastAPI and Discord bot."""
    discord_bot: Bot = Bot(settings, logger=logging, stream_handler=logging.StreamHandler())

    fastapi_task: asyncio.Task = asyncio.create_task(run_fastapi_server())
    discord_bot_task: asyncio.Task = asyncio.create_task(
        run_discord_bot_client(discord_bot, settings.BOTTOKEN)
    )

    try:
        await asyncio.gather(fastapi_task, discord_bot_task)
    except asyncio.CancelledError:
        logging.info("Main orchestration tasks cancelled. Initiating graceful shutdown...")
    except Exception as e:
        logging.critical(f"An unhandled error occurred in main_orchestrator: {e}")
    finally:
        if not discord_bot.is_closed():
            await discord_bot.close()
            logging.info("Discord bot client ensured to be closed.")
        logging.info("Application shutdown sequence complete.")

def handle_signal(sig: int, frame: Optional[FrameType]) -> None:
    """
    Handle OS signals for graceful shutdown.
    Args:
        sig (int): Signal number
        frame (Optional[FrameType]): Current stack frame
    """
    logging.info(f"Received signal {signal.Signals(sig).name}. Cancelling all tasks...")
    loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    loop.call_soon_threadsafe(loop.stop)

# --- Application Entry Point ---
if __name__ == "__main__":
    title: str = settings.format_title({
        "Authors": settings.AUTHORS,
        "Repo": settings.REPO_URL,
        "Version": settings.VERSION
    })
    print(title)

    setup_logging()

    if not check_env():
        logging.critical("Required environment variables are not set. Exiting.")
        raise SystemExit(1)
    
    logging.info("All required environment variables are set.")
    logging.info("Starting application components...")

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        asyncio.run(main_orchestrator())
    except KeyboardInterrupt:
        logging.info("KeyboardInterrupt caught. Application is shutting down.")
    except Exception as e:
        logging.critical(f"An unhandled exception occurred during application startup/runtime: {e}", exc_info=True)
        raise
