"""Test cases for Pterodactyl server management."""
import os
import pytest
import logging
from typing import Any, Generator
import pytest_asyncio
from src.pterodactyl.pterodactyl import PterodactylManager
from src.utils.common import setup_logging
import settings

@pytest.fixture(scope="session")
def test_settings() -> Any:
    """Get test settings."""
    return settings

@pytest_asyncio.fixture
async def pterodactyl_manager(test_settings: Any) -> PterodactylManager: # type: ignore
    """Create a Pterodactyl manager instance for testing."""
    manager = PterodactylManager(
        api_key=test_settings.PTERODACTYL_API_KEY,
        base_url=test_settings.PTERODACTYL_API_URL,
        egg_id=test_settings.PTERODACTYL_EGG_ID,
        nest_id=test_settings.PTERODACTYL_NEST_ID,
        server_name="test-server",
        settings_obj=test_settings
    )
    yield manager # type: ignore
    # Cleanup any test servers
    await manager.deleteServer()

@pytest.mark.asyncio
async def test_pterodactyl_connection(pterodactyl_manager: PterodactylManager) -> None:
    """Test basic connection to Pterodactyl panel."""
    assert await pterodactyl_manager.IsInstalled(), "Pterodactyl connection failed"

@pytest.mark.asyncio
async def test_server_creation(pterodactyl_manager: PterodactylManager) -> None:
    """Test server creation with default settings."""
    try:
        success = await pterodactyl_manager.create_server()
        assert success, "Failed to create server"
        assert pterodactyl_manager.server_id is not None, "Server ID not set"
        assert pterodactyl_manager.server_identifier is not None, "Server identifier not set"
        
        # Check if server exists
        assert await pterodactyl_manager.check_server(), "Server not found after creation"
        
    finally:
        # Cleanup
        if pterodactyl_manager.server_id:
            await pterodactyl_manager.deleteServer()

@pytest.mark.asyncio
async def test_server_installation_wait(pterodactyl_manager: PterodactylManager) -> None:
    """Test server creation and installation completion."""
    try:
        success = await pterodactyl_manager.create_server()
        assert success, "Failed to create server"
        
        # Wait for installation
        success = await pterodactyl_manager.wait_for_server_installation(timeout_seconds=300)
        assert success, "Server installation failed or timed out"
        
        # Check server status
        status = await pterodactyl_manager.get_status()
        assert status["has_server"] == "true", "Server not found"
        assert status["server_state"] in ["running", "ready", "installed"], f"Unexpected server state: {status['server_state']}"
        
    finally:
        # Cleanup
        if pterodactyl_manager.server_id:
            await pterodactyl_manager.deleteServer()

@pytest.mark.asyncio
async def test_mod_upload(pterodactyl_manager: PterodactylManager) -> None:
    """Test mod file upload to server."""
    try:
        # Create and wait for server
        success = await pterodactyl_manager.create_server()
        assert success, "Failed to create server"
        
        success = await pterodactyl_manager.wait_for_server_installation()
        assert success, "Server installation failed or timed out"
        
        # Try uploading mod file
        mod_file = getattr(settings, 'MOD_FILE_PATH', None)
        assert mod_file, "MOD_FILE_PATH not set in settings"
        
        success = await pterodactyl_manager.upload_mod_file(str(mod_file))
        assert success, "Failed to upload mod file"
        
    finally:
        # Cleanup
        if pterodactyl_manager.server_id:
            await pterodactyl_manager.deleteServer()

@pytest.mark.asyncio
async def test_server_cleanup(pterodactyl_manager: PterodactylManager) -> None:
    """Test proper server cleanup."""
    # Create server
    success = await pterodactyl_manager.create_server()
    assert success, "Failed to create server"
    server_id = pterodactyl_manager.server_id
    
    # Delete server
    success = await pterodactyl_manager.deleteServer()
    assert success, "Failed to delete server"
    
    # Verify server is gone
    assert not await pterodactyl_manager.check_server(), "Server still exists after deletion"
    assert pterodactyl_manager.server_id is None, "Server ID not cleared"
    assert pterodactyl_manager.server_identifier is None, "Server identifier not cleared"
