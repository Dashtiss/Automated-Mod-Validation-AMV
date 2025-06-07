# Automated Mod Validation (AMV)

> ⚠️ **Beta Stage Notice**: This project is in beta development with core features implemented and actively being enhanced. Documentation is regularly updated to reflect the current state.

## Project Vision

AMV is an automated testing framework designed to validate Minecraft mods through systematic testing and validation. The system automates the entire process of setting up, testing, and reporting mod compatibility and stability.

### What AMV Does

- Manages Minecraft servers through Pterodactyl Panel with automatic setup and cleanup
- Monitors and updates mods automatically from Modrinth using version tracking
- Provides comprehensive mod testing across different Minecraft versions and mod loaders
- Features smart version selection with loader preferences (Fabric, Forge, NeoForge)
- Includes robust error handling and retry mechanisms
- Reports updates and status through Discord bot integration

## Current Development Status

The project is in Phase 2 (Beta), with the following features implemented:

Core Features:
- AsyncIO-based core engine orchestrating all components
- Comprehensive logging system with JSON formatting
- Error handling and retry mechanisms across all operations
- RESTful API endpoints for system control

Server Management:
- Pterodactyl integration for server control
- Automated server deployment and cleanup
- Smart mod file management
- Server status monitoring

Mod Management:
- Automatic mod version tracking
- Smart loader selection (Fabric/Forge/NeoForge)
- Mod file uploading and validation
- Version compatibility checking

Discord Integration:
- Real-time status updates
- Command handling for server control
- Embedded status messages
- Automatic error reporting

In Progress:
- Proxmox VM integration (currently disabled)
- Web interface for monitoring
- Client-side automation
- Performance metrics collection

## End Goals

AMV aims to provide:

1. **Automated Testing**: Full automation of mod testing processes
2. **Comprehensive Validation**: Testing mods across different Minecraft versions and configurations
3. **Real-time Reporting**: Instant notifications and detailed reports via Discord and web interface
4. **Scalable Architecture**: Support for testing multiple mods simultaneously
5. **User-Friendly Interface**: Easy configuration and result monitoring

## Technical Stack

- VM Management: Proxmox
- Server Management: Pterodactyl Panel
- Communication: Discord Bot Integration
- APIs: FastAPI (REST endpoints), Modrinth API
- Development: Python with AsyncIO

## Project Timeline

For detailed development phases and timeline, see [TODO.md](TODO.md)
For the development checklist, see [CHECKLIST.md](CHECKLIST.md)

## Contributing

As this project is in active development, we're accepting contributions. Please help this project out with ideas and more.
