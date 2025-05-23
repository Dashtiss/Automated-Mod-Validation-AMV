import textwrap
from dotenv import load_dotenv
import os


load_dotenv()

VERSION = "0.0.0-alpha.0-dev"
VERSION_NAME = "Alpha"

AUTHORS = ["Dashtiss", "Lightning-Modding"]
REPO_URL = "https://github.com/Lightning-Modding/Pterodactyl-Proxy-Manager"


DEVELOPMENT = True

DEBUG = False


BOTTOKEN = os.getenv('BOTTOKEN', None)
CHANNEL_ID = os.getenv('CHANNEL_ID', None)
CHECKER_REGEX = os.getenv('CHECKER_REGEX', None)


PTERODACTYL_API_URL = os.getenv('PTERODACTYL_API_URL', None)
PTERODACTYL_API_KEY = os.getenv('PTERODACTYL_API_KEY', None)

PROXMOX_API_URL = os.getenv('PROXMOX_API_URL', None)
PROXMOX_API_KEY = os.getenv('PROXMOX_API_KEY', None)

def format_title(info: dict) -> str:
    """
    Formats a title with additional information and ASCII art,
    inserting info below the main ASCII art block.

    Args:
        title (str): The main title (not used in the current ASCII art, but kept for signature).
        info (dict): A dictionary with keys as names and values as information to be printed.

    Returns:
        str: The formatted title with additional information and ASCII art.
    """
    ascii_art_top = """
.----------------------------------.
|                                  |
|    █████╗ ██╗   ██╗███╗   ███╗   |
|   ██╔══██╗██║   ██║████╗ ████║   |
|   ███████║██║   ██║██╔████╔██║   |
|   ██╔══██║╚██╗ ██╔╝██║╚██╔╝██║   |
|   ██║  ██║ ╚████╔╝ ██║ ╚═╝ ██║   |
|   ╚═╝  ╚═╝  ╚═══╝  ╚═╝     ╚═╝   |
"""

    empty_line = "|                                  |\n"
    closing_line = "'----------------------------------'\n"
    box_width = 34 # Characters between the pipes

    additional_info_block = ""
    additional_info_block += empty_line # Add empty line before the first info

    for key, value in info.items():
        content = f"{key}: {value}"
        # Ensure content doesn't exceed box width minus padding
        if len(content) > box_width:
             content = textwrap.shorten(content, width=box_width, placeholder="...")

        padding = (box_width - len(content)) // 2
        # Distribute padding, handling odd lengths
        formatted_line = f"|{' ' * padding}{content}{' ' * (box_width - len(content) - padding)}|\n"
        additional_info_block += formatted_line
        additional_info_block += empty_line # Add empty line after each info

    formatted_title = ascii_art_top + additional_info_block + closing_line
    return formatted_title.strip() # Use strip to remove leading/trailing whitespace caused by triple quotes