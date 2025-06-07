"""Discord bot for AMV updates."""
from typing import Optional, Dict, Any
from discord.ext import commands
import datetime
import discord
import logging
import signal
import re
import asyncio
from discord import (
    Intents,
    Message,
    Embed,
    Colour,
    TextChannel,
    Guild,
    ActivityType,
    Status,
    HTTPException,
    Forbidden,
    NotFound,
    RateLimited
)
from httpx import AsyncClient, Response, RequestError, HTTPStatusError

class Bot(commands.Bot):
    def __init__(
        self,
        settings: Any,
        logger: logging.Logger,
    ) -> None:
        self.settings: Any = settings
        self.logger: logging.Logger = logger
        self.channel_id: int = int(settings.CHANNEL_ID)  # Ensure channel_id is an integer
        self.embed: Optional[Embed] = None
        self.embed_message: Optional[Message] = None
        self._shutdown_lock = asyncio.Lock()
        self._is_shutting_down: bool = False
        self._http_client: Optional[AsyncClient] = None
        
        # Configure debug logging
        self.logger.debug(f"Initializing bot with channel_id: {self.channel_id}")
        
        # Initialize the bot with all intents
        intents = Intents.all()
        super().__init__(command_prefix='!', intents=intents)
        self.logger.debug("Bot superclass initialized successfully")

        try:
            self.checker_regex: re.Pattern = re.compile(settings.CHECKER_REGEX)
            self.logger.debug(f"Regex pattern compiled successfully: {settings.CHECKER_REGEX}")
        except re.error as e:
            self.logger.error(f"Invalid regex pattern: {settings.CHECKER_REGEX}. Error: {e}")
            raise

        # Remove default help command
        self.remove_command('help')
        self.logger.info("Bot initialized with settings.")

    async def _shutdown(self) -> None:
        """Handle graceful shutdown of the bot."""
        async with self._shutdown_lock:
            if self._is_shutting_down:
                return

            self._is_shutting_down = True
            self.logger.info("Bot shutdown initiated...")
            
            try:
                # Close HTTP client if it exists
                if self._http_client:
                    await self._http_client.aclose()
                
                # Update status message if possible
                if self.embed and self.embed_message:
                    try:
                        self.embed.title = "Bot Shutting Down"
                        self.embed.description = "Bot is shutting down gracefully. Updates will be halted."
                        self.embed.color = Colour.orange()
                        await self.embed_message.edit(embed=self.embed)
                    except Exception as e:
                        self.logger.error(f"Failed to update shutdown status: {e}")
                
                # Cancel all tasks owned by the bot
                tasks = [t for t in asyncio.all_tasks() 
                        if t is not asyncio.current_task() 
                        and not t.done()]
                
                if tasks:
                    self.logger.info(f"Cancelling {len(tasks)} remaining tasks...")
                    for task in tasks:
                        task.cancel()
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait briefly for tasks to cleanly exit
                await asyncio.sleep(0.5)
                
                if not self.is_closed():
                    await self.close()
                    
                self.logger.info("Bot shutdown completed successfully")
            except Exception as e:
                self.logger.error(f"Error during bot shutdown: {e}", exc_info=True)
            finally:
                self._is_shutting_down = False
    
    async def close(self) -> None:
        """Override close to ensure proper cleanup."""
        if self.is_closed():
            return
        try:
            await super().close()
        except Exception as e:
            self.logger.error(f"Error during bot close: {e}")
    
    async def setup_channel(self) -> Optional[TextChannel]:
        """Set up and validate the target channel."""
        self.logger.debug("Attempting to set up channel...")
        channel = self.get_channel(self.channel_id)
        if isinstance(channel, TextChannel):
            return channel
            
        for guild in self.guilds:
            try:
                channel = await guild.fetch_channel(self.channel_id)
                if isinstance(channel, TextChannel):
                    return channel
            except discord.NotFound:
                continue
        return None

    async def on_ready(self) -> None:
        """Handle bot ready event and channel setup."""
        if self.user:
            self.logger.info(f'Logged in as {self.user.name} - {self.user.id}')
        
        self.logger.debug(f"Connected to {len(self.guilds)} guilds")
        for guild in self.guilds:
            self.logger.debug(f"Connected to guild: {guild.name} ({guild.id})")
        
        channel: Optional[TextChannel] = await self.setup_channel()
        
        if channel:
            try:
                await channel.send("AMV bot is online and tracking messages!")
                self.logger.info(f"Connected to channel: {channel.name}")
            except discord.Forbidden:
                self.logger.error(f"Cannot send messages to {channel.name}")
        else:
            self.logger.error(f"Target channel {self.channel_id} not found")
            await self.close()
            
        await self.change_presence(
            activity=discord.activity.CustomActivity(
                name="Monitoring updates",
                type=discord.ActivityType.watching
            ),
            status=discord.Status.idle
        )

    async def on_message(self, message: Message) -> None:
        """Handle incoming messages."""
        if message.author == self.user:
            return

        channel_name = getattr(message.channel, 'name', 'DM')
        guild_name = getattr(message.guild, 'name', 'No Guild')
        self.logger.debug(f"Message received from {message.author} in {guild_name}/{channel_name}")

        if message.content.lower() == '!deleteserver':
            url: str = "http://127.0.0.1:8080/api/v1/server"
            try:
                async with AsyncClient() as client:
                    response: Response = await client.delete(url)
                    response.raise_for_status()
                    self.logger.info(f"Delete server request successful: {response.status_code}")
                    self.logger.debug(f"Response data: {response.text}")
                    await message.channel.send("Servers deleted successfully.")
            except (RequestError, HTTPStatusError) as e:
                self.logger.error(f"Delete server request failed: {str(e)}")
                self.logger.debug(f"Error details: {e}", exc_info=True)
                await message.channel.send("Failed to delete servers.")
                return

        match = self.checker_regex.search(message.content)
        if match:
            self.logger.info(f"Update trigger matched: '{match.group()}'")
            await self._handle_update_message(message)
        else:
            self.logger.debug("Message did not match update pattern")

    async def _handle_update_message(self, message: Message) -> None:
        """Handle messages that match the update pattern."""
        channel_name = getattr(message.channel, 'name', 'Unknown Channel')
        self.logger.info(f"Processing update message in channel: {channel_name}")
        
        self.embed = Embed(
            title="Update",
            description="Update has been sent to the main server.",
            color=Colour.blue()
        )
        self.logger.debug("Created update embed")
        self.embed.set_footer(text="AMV Bot")
        
        try:
            self.embed_message = await message.channel.send(embed=self.embed)
            self.logger.debug("Update embed sent successfully")
        except Exception as e:
            self.logger.error(f"Failed to send embed: {e}")
            return

        await self.send_update()
        await asyncio.sleep(3)
        await self.check_status()

    async def send_update(self) -> None:
        """Send update request to the main server."""
        url: str = "http://127.0.0.1:8080/api/v1/mod/update"
        self.logger.debug(f"Sending update request to: {url}")
        
        async with AsyncClient() as client:
            try:
                self.logger.debug("Sending POST request...")
                response: Response = await client.post(url)
                response.raise_for_status()
                self.logger.info(f"Update request successful: {response.status_code}")
                self.logger.debug(f"Response data: {response.text}")
            except (RequestError, HTTPStatusError) as e:
                self.logger.error(f"Update request failed: {str(e)}")
                self.logger.debug(f"Error details: {e}", exc_info=True)
                await self._update_embed_error("Failed to send update")

    async def check_status(self) -> None:
        """Check update status from the main server continuously until complete."""
        self.logger.debug("Starting continuous status check...")
        if not self.embed or not self.embed_message:
            return
        
        await self.change_presence(
            activity=discord.activity.CustomActivity(
                name="Checking Newest Update",
                type=discord.ActivityType.competing
            ),
            status=discord.Status.online
        )
        
        url: str = "http://127.0.0.1:8080/api/v1/mod/status"
        max_retries: int = 30  # Increased to allow for longer processing
        retry_count: int = 0
        retry_delay: int = 3  # Seconds between retries

        while retry_count < max_retries:
            try:
                self.logger.debug(f"Status check attempt {retry_count + 1}/{max_retries}")
                async with AsyncClient() as client:
                    response: Response = await client.get(url)
                    response.raise_for_status()
                    status_data = response.json()
                    self.logger.debug(f"Status response: {status_data}")
                    
                    # Update the embed with current status
                    await self._update_embed_status(status_data)
                    
                    # Check if process is complete or failed
                    status = status_data.get("status", "").lower()
                    if status in ["success", "complete", "completed"]:
                        self.logger.info("Update process completed successfully")
                        break
                    elif status in ["failed", "error"]:
                        self.logger.error("Update process failed")
                        break
                    
                    # If still in progress, continue monitoring
                    retry_count += 1
                    await asyncio.sleep(retry_delay)
                    
            except Exception as e:
                self.logger.error(f"Status check failed: {str(e)}")
                self.logger.debug(f"Error details: {e}", exc_info=True)
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.warning("Max retries reached for status check")
                    await self._update_embed_error("Max retries reached - status check timed out")
                await asyncio.sleep(retry_delay)
        
        # Update presence based on final status
        await self.change_presence(
            activity=discord.activity.CustomActivity(
                name="Monitoring updates",
                type=discord.ActivityType.watching
            ),
            status=discord.Status.idle
        )
    async def _update_embed_status(self, status_data: Dict[str, Any]) -> None:
        """
        Update embed with status information.
        Args:
            status_data (Dict[str, Any]): Status data from server
        """
        if not self.embed or not self.embed_message:
            return

        status = status_data.get("status", "Unknown")
        message = status_data.get("message", "No message provided")
        details = status_data.get("details", {})
        data = status_data.get("data", {})

        # Update embed title and description
        self.embed.title = f"Update Status: {status}"
        self.embed.description = message
        self.embed.clear_fields()

        # Handle different types of status updates
        if "engine_status" in data:
            # Status request response
            engine_status = data["engine_status"]
            self.embed.add_field(
                name="Engine Status",
                value="\n".join([f"• {k}: {v}" for k, v in engine_status.items()]),
                inline=False
            )

            # Add Pterodactyl status if available
            if "pterodactyl" in data:
                pterodactyl_info = data["pterodactyl"]
                self.embed.add_field(
                    name="Pterodactyl Status",
                    value="\n".join([f"• {k}: {v}" for k, v in pterodactyl_info.items()]),
                    inline=False
                )

            # Add Proxmox status if available
            if "proxmox" in data:
                proxmox_info = data["proxmox"]
                self.embed.add_field(
                    name="Proxmox Status",
                    value="\n".join([f"• {k}: {v}" for k, v in proxmox_info.items()]),
                    inline=False
                )

            # Add Discord bot status if available
            if "discord_bot" in data:
                bot_info = data["discord_bot"]
                self.embed.add_field(
                    name="Discord Bot Status",
                    value="\n".join([f"• {k}: {v}" for k, v in bot_info.items()]),
                    inline=False
                )

        elif details:
            # Mod update response
            for key, value in details.items():
                if isinstance(value, dict):
                    self.embed.add_field(
                        name=key.replace("_", " ").title(),
                        value="\n".join([f"• {k}: {v}" for k, v in value.items()]),
                        inline=False
                    )
                else:
                    self.embed.add_field(
                        name=key.replace("_", " ").title(),
                        value=str(value),
                        inline=True
                    )

        # Set color based on status
        if status.lower() == "success":
            self.embed.color = Colour.green()
        elif status.lower() == "failed":
            self.embed.color = Colour.red()
        else:
            self.embed.color = Colour.blue()

        # Add timestamp
        timestamp = details.get("timestamp") or data.get("timestamp")
        if timestamp:
            self.embed.timestamp = datetime.datetime.fromisoformat(timestamp)

        # Update the message
        try:
            await self.embed_message.edit(embed=self.embed)
        except Exception as e:
            self.logger.error(f"Failed to update embed: {e}")
            self.logger.debug(f"Attempted to update with status data: {status_data}")

    async def _update_embed_error(self, error_message: str) -> None:
        """
        Update embed with error message.
        Args:
            error_message (str): Error message to display
        """
        if self.embed and self.embed_message:
            self.embed.title = "Error"
            self.embed.description = error_message
            self.embed.color = Colour.red()
            timestamp = datetime.datetime.now()
            self.embed.timestamp = timestamp
            self.embed.clear_fields()
            self.embed.add_field(
                name="Error Time",
                value=timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                inline=False
            )
            await self.embed_message.edit(embed=self.embed)


