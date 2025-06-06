# Source Directory

The AMV project's source code is organized into several key components that work together to provide automated Minecraft mod testing:

## Core Components (`core/`)
- `engine.py`: Main orchestration engine that coordinates all components
- Manages initialization and cleanup of all services

## Infrastructure Management
- `proxmox/`: VM creation and management through Proxmox
- `pterodactyl/`: Minecraft server deployment and control
- `services/`: Additional service integrations

## Communication
- `discord_bot/`: Discord integration for notifications and control

## Utilities (`utils/`)
- Common utilities and helper functions
- Logging and shutdown management

## Quick Start

1. Set up environment variables in `.env`:
   ```env
   PROXMOX_API_URL=https://your-proxmox-server:8006
   PROXMOX_API_KEY=your-token-name=your-token-value
   PTERODACTYL_API_URL=https://your-panel-url
   PTERODACTYL_API_KEY=your-api-key
   BOTTOKEN=your-discord-bot-token
   CHANNEL_ID=your-discord-channel-id
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Run the application:
   ```bash
   python AMV_Engine.py
   ```

Each subdirectory contains its own README.md with more detailed documentation.
