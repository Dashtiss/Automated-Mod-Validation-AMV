import asyncio
import signal
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Assuming 'settings' module exists and contains necessary configurations
import settings

# Assuming 'bot.bot.Bot' class exists
from bot.bot import Bot
import discord

# --- FastAPI Setup ---
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/ModUpdate")
async def mod_update():
    """
    Endpoint to handle mod updates.
    """
    # Your logic for handling mod updates goes here
    logging.info("Mod update received via FastAPI endpoint.")
    return {"message": "Mod update received"}

# --- Logging Configuration ---
if settings.DEVELOPMENT:
    print("DEVELOPMENT MODE ENABLED, THIS IS NOT FOR PRODUCTION")

# Determine logging level based on settings.DEBUG
log_level = logging.DEBUG if settings.DEBUG else logging.INFO

# Basic logging configuration
logging.basicConfig(
    level=log_level,
    format='[%(levelname)s] {%(asctime)s} - %(message)s'
)

# Create a stream handler for console output
stream_handler = logging.StreamHandler()
stream_handler.setLevel(log_level)
stream_handler.setFormatter(logging.Formatter('[%(levelname)s] {%(asctime)s} - %(message)s'))

# Add the stream handler to the root logger
# This prevents duplicate handlers if basicConfig already added one
if not any(isinstance(handler, logging.StreamHandler) for handler in logging.getLogger().handlers):
    logging.getLogger().addHandler(stream_handler)

# --- Environment Variable Check ---
def check_env():
    """
    Checks if all required environment variables are set in the settings module.
    """
    required_vars = [
        'BOTTOKEN',
        'CHANNEL_ID',
        'CHECKER_REGEX',
        'PTERODACTYL_API_URL',
        'PTERODACTYL_API_KEY',
        'PROXMOX_API_URL',
        'PROXMOX_API_KEY'
    ]

    all_set = True
    for var in required_vars:
        # Check if the variables in the settings.py are not None
        if getattr(settings, var, None) is None: # Use getattr with default to avoid AttributeError
            logging.error(f"Environment variable '{var}' is not set in settings.py.")
            all_set = False
    return all_set

# --- Asynchronous Task Functions ---

async def run_fastapi_server():
    """
    Runs the FastAPI server using uvicorn programmatically.
    """
    # Configure uvicorn server
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=8080,
        log_level="info", # Uvicorn's log level
        loop="asyncio" # Explicitly set asyncio loop
    )
    server = uvicorn.Server(config)
    logging.info("Starting FastAPI server on http://127.0.0.1:8080")
    await server.serve()

async def run_discord_bot_client(bot_instance: Bot, token: str):
    """
    Runs the Discord bot client.
    """
    logging.info("Starting Discord bot...")
    try:
        await bot_instance.start(token)
    except discord.LoginFailure:
        logging.error("Discord bot failed to log in. Check your BOTTOKEN.")
    except Exception as e:
        logging.error(f"An error occurred with the Discord bot: {e}")
    finally:
        # Ensure the bot client is properly closed if it stops for any reason
        if not bot_instance.is_closed():
            await bot_instance.close()
            logging.info("Discord bot client closed.")


# --- Main Orchestration Function ---
async def main_orchestrator():
    """
    Orchestrates the concurrent running of FastAPI and Discord bot.
    Handles graceful shutdown.
    """
    # Initialize Discord bot instance
    discord_bot = Bot(settings, logger=logging, stream_handler=stream_handler)

    # Create asyncio tasks for both the FastAPI server and the Discord bot
    fastapi_task = asyncio.create_task(run_fastapi_server())
    discord_bot_task = asyncio.create_task(
        run_discord_bot_client(discord_bot, settings.BOTTOKEN)
    )

    # Wait for both tasks to complete.
    # They will only complete if cancelled due to a signal.
    try:
        await asyncio.gather(fastapi_task, discord_bot_task)
    except asyncio.CancelledError:
        logging.info("Main orchestration tasks cancelled. Initiating graceful shutdown...")
    except Exception as e:
        logging.critical(f"An unhandled error occurred in main_orchestrator: {e}")
    finally:
        # Ensure Discord bot is properly closed
        if not discord_bot.is_closed():
            await discord_bot.close()
            logging.info("Discord bot client ensured to be closed.")
        logging.info("Application shutdown sequence complete.")

# --- Signal Handler for Graceful Shutdown ---
def handle_signal(sig, frame):
    """
    Handles OS signals (like Ctrl+C) to initiate graceful shutdown.
    """
    logging.info(f"Received signal {signal.Signals(sig).name}. Cancelling all tasks...")
    # Get the running event loop
    loop = asyncio.get_running_loop()
    # Cancel all running tasks in the loop
    for task in asyncio.all_tasks(loop=loop):
        task.cancel()
    # Schedule the loop to stop after tasks are cancelled
    # This is important for thread safety when called from a signal handler
    loop.call_soon_threadsafe(loop.stop)


# --- Application Entry Point ---
if __name__ == "__main__":
    # Print formatted title
    title = settings.format_title({"Authors": settings.AUTHORS, "Repo": settings.REPO_URL, "Version": settings.VERSION})
    print(title)

    # Check environment variables
    if not check_env():
        logging.critical("Required environment variables are not set. Exiting.")
        raise SystemExit(1)
    else:
        logging.info("All required environment variables are set.")
        logging.info("Starting application components...")

    # Disable FastAPI's default logger if desired (though standard logging is now used)
    # Note: `logger` was imported from `fastapi` in your original code, which is not standard.
    # If you intend to disable uvicorn's internal logging, you'd do it via uvicorn.Config.
    # For now, I've removed the problematic `logger.logger.disabled = True` line.

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_signal)  # Ctrl+C
    signal.signal(signal.SIGTERM, handle_signal) # Sent by `kill` command

    # Run the main asynchronous orchestration function
    try:
        asyncio.run(main_orchestrator())
    except KeyboardInterrupt:
        # This KeyboardInterrupt is expected if the signal handler worked,
        # but it might also catch an interrupt before the handler is fully set up.
        # The signal handler's `loop.stop()` will usually prevent this from being the primary exit.
        logging.info("KeyboardInterrupt caught. Application is shutting down.")
    except Exception as e:
        logging.critical(f"An unhandled exception occurred during application startup/runtime: {e}", exc_info=True)
        raise
