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

    async def setup_channel(self) -> Optional[TextChannel]:
        """
        Set up and validate the target channel.
        Returns:
            Optional[TextChannel]: The found channel or None
        """
        channel: Optional[TextChannel] = self.get_channel(self.channel_id)
        
        if not channel:
            for guild in self.guilds:
                try:
                    channel = await guild.fetch_channel(self.channel_id)
                    if channel:
                        break
                except discord.NotFound:
                    self.logger.debug(f"Channel not found in guild {guild.name}")
                except discord.Forbidden:
                    self.logger.warning(f"No access in guild: {guild.name}")
                except Exception as e:
                    self.logger.error(f"Error in guild {guild.name}: {e}")
        
        return channel

    async def on_ready(self) -> None:
        """Handle bot ready event and channel setup."""
        self.logger.info(f'Logged in as {self.user.name} - {self.user.id}')
        
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

    async def on_message(self, message: Message) -> None:
        """
        Handle incoming messages.
        Args:
            message (Message): Discord message object
        """
        if message.author == self.user or message.channel.id != self.channel_id:
            return

        if self.checker_regex.search(message.content):
            await self._handle_update_message(message)

    async def _handle_update_message(self, message: Message) -> None:
        """
        Handle messages that match the update pattern.
        Args:
            message (Message): Discord message object
        """
        self.embed = Embed(
            title="Update",
            description="Update has been sent to the main server.",
            color=Colour.blue()
        )
        self.embed.set_footer(text="AMV Bot")
        self.embed_message = await message.channel.send(embed=self.embed)

        await self.send_update()
        await asyncio.sleep(3)
        await self.check_status()

    async def send_update(self) -> None:
        """Send update request to the main server."""
        url: str = "http://127.0.0.1:8080/ModUpdate"
        
        async with AsyncClient() as client:
            try:
                response: Response = await client.post(url)
                response.raise_for_status()
                self.logger.info("Update sent successfully")
            except (RequestError, HTTPStatusError) as e:
                self.logger.error(f"Update request failed: {e}")
                await self._update_embed_error("Failed to send update")

    async def check_status(self) -> None:
        """Check update status from the main server."""
        if not self.embed or not self.embed_message:
            return

        url: str = "http://127.0.0.1:8080/UpdateStatus"
        max_retries: int = 5
        retry_count: int = 0

        while retry_count < max_retries:
            try:
                async with AsyncClient() as client:
                    response: Response = await client.get(url)
                    response.raise_for_status()
                    # Process response here
                    await self._update_embed_status(response.json())
            except Exception as e:
                self.logger.error(f"Status check failed: {e}")
                retry_count += 1
                if retry_count >= max_retries:
                    await self._update_embed_error("Max retries reached")
            await asyncio.sleep(3)

    async def _update_embed_status(self, status_data: Dict[str, Any]) -> None:
        """
        Update embed with status information.
        Args:
            status_data (Dict[str, Any]): Status data from server
        """
        if self.embed and self.embed_message:
            self.embed.title = "Update Status"
            self.embed.description = str(status_data.get("status", "Unknown status"))
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

