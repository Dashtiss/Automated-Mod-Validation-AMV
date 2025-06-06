# Proxmox Management

This module handles all interactions with the Proxmox API for VM management.

## Features

- VM creation and deletion
- VM status monitoring
- Resource management
- Template management

## Usage

```python
from src.proxmox.manager import ProxmoxManager

# Initialize the manager
manager = ProxmoxManager(
    api_url="https://your-proxmox-server:8006",
    api_token="your-token-name=your-token-value"
)

# Create a VM
success = manager.create_vm(
    node="proxmox",
    vmid=100,
    name="test-vm",
    template="template-vm",
    memory=2048,
    cores=2
)

# Monitor VM status
status = manager.get_vm_status("proxmox", 100)
```

## Configuration

Required environment variables in your `.env` file:

```env
PROXMOX_API_URL=https://your-proxmox-server:8006
PROXMOX_API_KEY=your-token-name=your-token-value
```

## Integration with AMV

The Proxmox manager is used by the AMV Engine to:

1. Create testing environments for mod validation
2. Manage VM resources efficiently
3. Clean up resources after testing is complete

For more details on the overall architecture, see the main [README.md](../../README.md).
