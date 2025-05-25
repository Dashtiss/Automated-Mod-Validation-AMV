import discord
from discord.ext import commands
from discord import (
    Intents,
    Message,
    Embed,
    Colour
)
import logging
import os
import re
import asyncio
import httpx

# import settings

class Bot(commands.Bot):
    def __init__(self, settings, logger: logging.Logger, stream_handler: logging.StreamHandler):
        """
        Initializes the Discord bot.

        Args:
            settings: Bot settings (not directly used in this snippet but good practice).
            logger (logging.Logger): The logger instance for logging bot activities.
        """
        self.settings = settings
        self.logger = logger
        # discord.utils.setup_logging(level=logging.ERROR, handler=stream_handler, formatter=stream_handler.formatter)


        # Initialize the commands.Bot parent class with a command prefix and all intents.
        super().__init__(command_prefix='!', intents=Intents.all())
        self.logger.info("Bot initialized with settings.")
        self.logger.debug(f"Initializing bot with channel ID: {settings.CHANNEL_ID} and regex: '{settings.CHECKER_REGEX}'.")

        # Compile the regex pattern for efficient searching.
        try:
            self.Checker_Regex = re.compile(settings.CHECKER_REGEX)
            self.logger.debug("Regex pattern compiled successfully.")
        except re.error as e:
            # Log an error and raise an exception if the regex pattern is invalid.
            self.logger.error(f"Invalid regex pattern: {settings.CHECKER_REGEX}. Error: {e}")
            raise e

        self.channel_id = settings.CHANNEL_ID
        # Remove the default 'help' command to avoid conflicts or unwanted behavior.
        self.remove_command('help')
        self.logger.debug("Default 'help' command removed.")

    async def on_ready(self):
        """
        Event handler that runs when the bot successfully connects to Discord.
        It logs the bot's login information and attempts to send an online message
        to the specified channel.
        """
        self.logger.info(f'Logged in as {self.user.name} - {self.user.id}')
        self.logger.info('------')
        self.logger.debug("Bot is ready and connected to Discord.")

        channel = None
        # First, try to get the channel from the bot's cache. This is generally fast.
        channel = self.get_channel(self.channel_id)
        self.logger.debug(f"Attempting to retrieve channel ID {self.channel_id} from cache.")


        # If the channel is not found in cache, iterate through guilds and try to fetch it.
        # This makes an API call and is more reliable for channels that might not be
        # immediately available in the cache on startup.
        if not channel:
            self.logger.info(f"Channel with ID {self.channel_id} not found in cache. Attempting to fetch from guilds...")
            self.logger.debug(f"Iterating through {len(self.guilds)} guilds to find channel.")
            for guild in self.guilds:
                self.logger.debug(f"Checking guild: {guild.name} (ID: {guild.id})")
                try:
                    fetched_channel = await guild.fetch_channel(self.channel_id)
                    if fetched_channel:
                        channel = fetched_channel
                        self.logger.info(f"Channel fetched successfully from guild '{guild.name}': {channel.name} (ID: {channel.id})")
                        self.logger.debug(f"Successfully fetched channel {channel.name} via API call.")
                        break # Found the channel, no need to check other guilds
                except discord.NotFound:
                    self.logger.debug(f"Channel ID {self.channel_id} not found in guild {guild.name}.")
                    continue
                except discord.Forbidden:
                    self.logger.warning(f"Bot lacks permissions to fetch channels in guild: {guild.name} (ID: {guild.id})")
                    continue
                except Exception as e:
                    self.logger.error(f"An unexpected error occurred while fetching channel in guild {guild.name}: {e}")
                    continue

        if channel:
            self.logger.info(f"Channel found: {channel.name} (ID: {channel.id})")
            self.logger.debug(f"Attempting to send online message to channel {channel.name}.")
            self.channel_id = channel.id # Update the channel_id to the found channel's ID.
            try:
                # Send an online message to the found channel.
                await channel.send("AMV bot is online and tracking messages!")
                self.logger.debug("Online message sent successfully.")
            except discord.Forbidden:
                self.logger.error(f"Bot does not have permissions to send messages in channel: {channel.name} (ID: {channel.id})")
            except discord.HTTPException as e:
                self.logger.error(f"Failed to send message to channel {channel.name} (ID: {channel.id}). HTTP Error: {e}")
            except Exception as e:
                self.logger.error(f"An unexpected error occurred while sending message to channel {channel.name}: {e}")
        else:
            # If the channel is still not found after all attempts, log an error and
            # list all available channels for debugging purposes. Then, close the bot.
            self.logger.error(f"Channel with ID {self.channel_id} not found after all attempts.")
            self.logger.info("Listing all available channels for debugging:")
            for ch in self.get_all_channels():
                self.logger.info(f"Channel ID: {ch.id}, Channel Name: {ch.name}")
            self.logger.debug("Closing bot due to target channel not being found.")
            await self.close() # Close the bot if the target channel isn't found.


    async def on_message(self, message: Message):
        """
        Event handler that runs whenever a message is sent in any channel the bot can see.

        Args:
            message (discord.Message): The message object that was sent.
        """
        self.logger.debug(f"Received message from {message.author} in channel {message.channel.name} (ID: {message.channel.id}): '{message.content}'")

        # Ignore messages sent by the bot itself to prevent infinite loops.
        if message.author == self.user:
            self.logger.debug("Ignoring message from self.")
            return

        # Process messages only if they are in the target channel.
        if message.channel.id == self.channel_id:
            self.logger.debug(f"Message from {message.author} is in target channel ({message.channel.name}). Content: '{message.content}'")
            # Check if the message content matches the compiled regex pattern.
            if self.Checker_Regex.search(message.content):
                self.logger.info(f"Message matches regex, Running Update")
                self.logger.debug("Sending regex match confirmation message.")

                # Send a confirmation message to the channel.

                self.embed = Embed(title="Update", description="Update has been sent to the main server. Updates will be posted in here", color=Colour.blue())
                self.embed.set_footer(text="AMV Bot")
                self.embed_message = await message.channel.send(embed=self.embed)
                self.logger.debug("Confirmation message sent successfully.")

                # Call the sendUpdate method to send a request to the main server.
                await self.sendUpdate() # Added 'await' here
                self.logger.debug("sendUpdate method called.")
                await asyncio.sleep(3) # Added sleep to prevent spamming the server
                task = asyncio.create_task(self.checkStatus()) # Added task creation
                self.logger.debug("Task for checkStatus created.")
                await task

            else:
                self.logger.info(f"Message does not match regex: '{message.content}'")
                self.logger.debug("Message did not match regex pattern.")
        else:
            self.logger.debug(f"Ignoring message from non-target channel: {message.channel.name} (ID: {message.channel.id}).")

    async def sendUpdate(self): # Made this method async
        """
        Sends an asynchronous POST request to the main server to start testing.
        """
        url = "http://127.0.0.1:8080/ModUpdate" # Added http:// scheme
        try:
            async with httpx.AsyncClient() as client: # Use AsyncClient for better practice
                r = await client.post(url) # Await the httpx post request
                r.raise_for_status() # Raise an exception for 4xx/5xx responses

            self.logger.info("Update sent successfully.")
            self.logger.debug(f"Response: {r.status_code} - {r.text}")
            
            
        except httpx.RequestError as e:
            self.logger.error(f"An error occurred while requesting {e.request.url!r}: {e}")
        except httpx.HTTPStatusError as e:
            self.logger.error(f"Failed to send update. HTTP Status Error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            self.logger.error(f"An unexpected error occurred during sendUpdate: {e}")
            
    async def checkStatus(self):
        """
        Checks the status of the Update
        """
        embed = self.embed
        embed.title = "Update Status"
        embed_message = self.embed_message
        
        max_retries = 5
        retry_count = 0
        url = "http://127.0.0.1:8080/UpdateStatus"
        
        while True:
            
            try:
                async with httpx.AsyncClient() as client: # Use AsyncClient for better practice
                    r = await client.get(url) # Await the httpx get request
                    r.raise_for_status() # Raise an exception for 4xx/5xx responses
                    

            except httpx.RequestError as e:
                self.logger.error(f"An error occurred while requesting {e.request.url!r}: {e}")
                embed.description = "An error occurred while checking the status."
                embed.color = Colour.red()
                embed.set_footer(text="AMV Bot - Error")
                
                retry_count += 1
            except httpx.HTTPStatusError as e:
                self.logger.error(f"Failed to send update. HTTP Status Error: {e.response.status_code} - {e.response.text}")
                embed.description = "An error occurred while checking the status."
                embed.color = Colour.red()
                embed.set_footer(text="AMV Bot - Error")
                retry_count += 1
            except Exception as e:
                self.logger.error(f"An unexpected error occurred during sendUpdate: {e}")
                embed.description = "An error occurred while checking the status."
                embed.color = Colour.red()
                embed.set_footer(text="AMV Bot - Error")
                retry_count += 1
            
            finally:
                if retry_count >= max_retries:
                    embed.description = "Max retries reached. Stopping status checks."
                    embed.color = Colour.red()
                    embed.set_footer(text="AMV Bot - Max Retries Reached")
                    await embed_message.edit(embed=embed)
                    break

                
                
            await embed_message.edit(embed=embed)
            await asyncio.sleep(3)

