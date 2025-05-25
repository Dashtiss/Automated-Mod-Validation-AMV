# Automated Mod Validation (AMV)

> ⚠️ **Alpha Stage Notice**: This project is currently in early alpha development and is actively being worked on. Features and documentation will be regularly updated.

## Project Vision

AMV is an automated testing framework designed to validate Minecraft mods through systematic testing and validation. The system automates the entire process of setting up, testing, and reporting mod compatibility and stability.

### What AMV Does

- Automatically deploys and manages test environments using Proxmox VMs
- Sets up and controls Minecraft servers through a Server Panel
- Performs automated mod testing with both client and server validation
- Collects and analyzes crash reports and performance metrics
- Reports results through both web interface and Discord notifications

## Current Development Status

The project is in Phase 2 (Alpha), focusing on:
- Connect to Proxmox API
- Implement VM management
- Connect to Server Panel API
- Implement server management
- Set up SSH connections

## End Goals

AMV aims to provide:
1. **Automated Testing**: Full automation of mod testing processes
2. **Comprehensive Validation**: Testing mods across different Minecraft versions and configurations
3. **Real-time Reporting**: Instant notifications and detailed reports via Discord and web interface
4. **Scalable Architecture**: Support for testing multiple mods simultaneously
5. **User-Friendly Interface**: Easy configuration and result monitoring

## Technical Stack

- VM Management: Proxmox
- Server Management: Game Server Panel
- Client Automation: Minecraft Client Scripts
- Communication: Discord Bot Integration
- Reporting: Web Interface

## Project Timeline

For detailed development phases and timeline, see [TODO.md](TODO.md)
For the development checklist, see [CHECKLIST.md](CHECKLIST.md)

## Contributing

As this project is in active development, we're not yet accepting contributions. Stay tuned for updates!
