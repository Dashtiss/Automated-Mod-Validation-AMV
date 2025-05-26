import logging
from proxmoxer import ProxmoxAPI
from typing import Optional, Dict, Any
import time

class ProxmoxManager:
    def __init__(self, api_url: str, api_token: str, verify_ssl: bool = True):
        """
        Initialize ProxmoxManager with API credentials.
        
        Args:
            api_url: Proxmox API URL (e.g., 'https://proxmox.example.com:8006')
            api_token: API token for authentication
            verify_ssl: Whether to verify SSL certificates
        """
        self.proxmox = ProxmoxAPI(
            api_url,
            token_name=api_token.split('=')[0],
            token_value=api_token.split('=')[1],
            verify_ssl=verify_ssl
        )
        self.logger = logging.getLogger(__name__)

    def create_vm(self, node: str, vmid: int, name: str, template: str, 
                 memory: int = 2048, cores: int = 2, storage: str = 'local') -> bool:
        """
        Create a new VM from a template.
        
        Args:
            node: Proxmox node name
            vmid: VM ID to assign
            name: Name for the new VM
            template: Template name to clone from
            memory: Memory in MB
            cores: Number of CPU cores
            storage: Storage pool name
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Clone the template
            self.proxmox.nodes(node).qemu(template).clone.post(
                newid=vmid,
                name=name,
                full=1  # Full clone
            )
            
            # Wait for clone to complete
            self._wait_for_task(node)
            
            # Configure the VM
            self.proxmox.nodes(node).qemu(vmid).config.put(
                memory=memory,
                cores=cores,
                name=name
            )
            
            self.logger.info(f"Successfully created VM {name} with ID {vmid}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to create VM: {str(e)}")
            return False

    def start_vm(self, node: str, vmid: int) -> bool:
        """Start a VM."""
        try:
            self.proxmox.nodes(node).qemu(vmid).status.start.post()
            return True
        except Exception as e:
            self.logger.error(f"Failed to start VM {vmid}: {str(e)}")
            return False

    def stop_vm(self, node: str, vmid: int) -> bool:
        """Stop a VM."""
        try:
            self.proxmox.nodes(node).qemu(vmid).status.stop.post()
            return True
        except Exception as e:
            self.logger.error(f"Failed to stop VM {vmid}: {str(e)}")
            return False

    def delete_vm(self, node: str, vmid: int) -> bool:
        """Delete a VM."""
        try:
            self.proxmox.nodes(node).qemu(vmid).delete()
            return True
        except Exception as e:
            self.logger.error(f"Failed to delete VM {vmid}: {str(e)}")
            return False

    def get_vm_status(self, node: str, vmid: int) -> Optional[Dict[str, Any]]:
        """Get VM status."""
        try:
            return self.proxmox.nodes(node).qemu(vmid).status.current.get()
        except Exception as e:
            self.logger.error(f"Failed to get VM status for {vmid}: {str(e)}")
            return None

    def _wait_for_task(self, node: str, timeout: int = 300):
        """Wait for any running tasks to complete."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            tasks = self.proxmox.nodes(node).tasks.get()
            running_tasks = [t for t in tasks if t['status'] == 'running']
            if not running_tasks:
                return
            time.sleep(2)
        raise TimeoutError("Timeout waiting for task to complete")
