from typing import Optional, Dict, Any
import discord
from discord.ext import commands
from discord import (
    Intents,
    Message,
    Embed,
    Colour,
    TextChannel,
    Guild
)
import logging
import re
import asyncio
from httpx import AsyncClient, Response, RequestError, HTTPStatusError
import signal
import aiohttp

class Bot(commands.Bot):
    def __init__(
        self,
        settings: Any,
        logger: logging.Logger,
        stream_handler: logging.StreamHandler
    ) -> None:
        self.settings: Any = settings
        self.logger: logging.Logger = logger
        self.channel_id: int = settings.CHANNEL_ID
        self.embed: Optional[Embed] = None
        self.embed_message: Optional[Message] = None
        super().__init__(command_prefix='!', intents=Intents.all())

        try:
            self.checker_regex: re.Pattern = re.compile(settings.CHECKER_REGEX)
            self.logger.debug("Regex pattern compiled successfully.")
        except re.error as e:
            self.logger.error(f"Invalid regex pattern: {settings.CHECKER_REGEX}. Error: {e}")
            raise

        self.remove_command('help')
        self.logger.info("Bot initialized with settings.")
        
        # Set up signal handlers
        signal.signal(signal.SIGINT, lambda s, f: asyncio.create_task(self._shutdown()))

    async def _shutdown(self) -> None:
        """Handle graceful shutdown of the bot."""
        self.logger.info("Bot shutdown initiated...")
        try:
            if self.embed and self.embed_message:
                try:
                    self.embed.title = "Bot Shutting Down"
                    self.embed.description = "Bot is shutting down. Updates will be halted."
                    self.embed.color = Colour.orange()
                    await self.embed_message.edit(embed=self.embed)
                except Exception as e:
                    self.logger.error(f"Failed to update shutdown status: {e}")
            
            await self.close()
            self.logger.info("Bot shutdown complete")
        except Exception as e:
            self.logger.error(f"Error during bot shutdown: {e}")

    async def setup_channel(self) -> Optional[TextChannel]:
        """Set up and validate the target channel."""
        self.logger.debug("Attempting to set up channel...")
        channel: Optional[TextChannel] = self.get_channel(self.channel_id)
        
        if not channel:
            self.logger.debug(f"Channel {self.channel_id} not found in cache, searching guilds...")
            for guild in self.guilds:
                self.logger.debug(f"Searching for channel in guild: {guild.name}")
                try:
                    channel = await guild.fetch_channel(self.channel_id)
                    if channel:
                        self.logger.info(f"Channel {self.channel_id} found in guild {guild.name}")
                        break
                except discord.NotFound:
                    self.logger.debug(f"Channel not found in guild {guild.name}")
                except discord.Forbidden:
                    self.logger.warning(f"No access in guild: {guild.name}")
                except discord.HTTPException as e:
                    self.logger.error(f"HTTP error in guild {guild.name}: {e}")
                except discord.RateLimited as e:
                    self.logger.warning(f"Rate limited in guild {guild.name}: {e}")
                    await asyncio.sleep(e.retry_after)
                except Exception as e:
                    self.logger.error(f"Error in guild {guild.name}: {e}")
        
        return channel

    async def on_ready(self) -> None:
        """Handle bot ready event and channel setup."""
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
        self.logger.debug(f"Message received from {message.author} in {message.guild.name}/{message.channel.name}")
        self.logger.debug(f"Message content: {message.content}")

        if message.author == self.user:
            self.logger.debug("Message from self, ignoring")
            return

        if int(message.channel.id) != int(self.channel_id):
            self.logger.debug(f"Channel mismatch: {message.channel.id} != {self.channel_id}")
            return

        match = self.checker_regex.search(message.content)
        if match:
            self.logger.info(f"Update trigger matched: '{match.group()}'")
            await self._handle_update_message(message)
        else:
            self.logger.debug("Message did not match update pattern")

    async def _handle_update_message(self, message: Message) -> None:
        """Handle messages that match the update pattern."""
        self.logger.info(f"Processing update message in channel: {message.channel.name}")
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
        url: str = "http://127.0.0.1:8080/ModUpdate"
        self.logger.debug(f"Sending update request to: {url}")
        
        connector = aiohttp.TCPConnector()
        from AMV_Engine import shutdown_manager
        shutdown_manager.add_connector(connector)
        
        async with AsyncClient(transport=aiohttp.TCPConnector()) as client:
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
        """Check update status from the main server."""
        self.logger.debug("Starting status check...")
        if not self.embed or not self.embed_message:
            return
        
        
        await self.change_presence(
            activity=discord.activity.CustomActivity(
                name="Checking Newest Update",
                type=discord.ActivityType.competing
            ),
            status=discord.Status.online
        )
        url: str = "http://127.0.0.1:8080/UpdateStatus"
        max_retries: int = 5
        retry_count: int = 0

        while retry_count < max_retries:
            try:
                self.logger.debug(f"Status check attempt {retry_count + 1}/{max_retries}")
                async with AsyncClient() as client:
                    response: Response = await client.get(url)
                    response.raise_for_status()
                    self.logger.debug(f"Status response: {response.text}")
                    await self._update_embed_status(response.json())
            except Exception as e:
                self.logger.error(f"Status check failed: {str(e)}")
                self.logger.debug(f"Error details: {e}", exc_info=True)
                retry_count += 1
                if retry_count >= max_retries:
                    self.logger.warning("Max retries reached for status check")
                    await self._update_embed_error("Max retries reached")
            await asyncio.sleep(3)
            
        
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
        if self.embed and self.embed_message:
            self.embed.title = "Update Status"
            self.embed.description = str(status_data.get("status", "Unknown status")).title()
            self.embed.color = Colour.green() if status_data.get("status") == "Success" else Colour.dark_blue()
            await self.embed_message.edit(embed=self.embed)

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
            await self.embed_message.edit(embed=self.embed)


