"""Integration tests for the AMV Engine."""
import os
import pytest
import logging
import asyncio
from typing import Any, AsyncGenerator
import pytest_asyncio
from src.core.engine import AMVEngine
import settings

@pytest.fixture(scope="session")
def test_settings() -> Any:
    """Get test settings."""
    return settings

@pytest_asyncio.fixture
async def engine(test_settings: Any) -> AsyncGenerator[AMVEngine, None]:
    """Create an engine instance for testing."""
    engine = AMVEngine(test_settings, test_mode=True)
    await engine.initialize()
    yield engine
    await engine.cleanup()
    
    # Clean up any remaining tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

@pytest.mark.asyncio
async def test_engine_initialization(engine: AMVEngine) -> None:
    """Test engine initialization."""
    assert engine.pterodactyl_manager is not None, "Pterodactyl manager not initialized"
    assert engine.mod_manager is not None, "Mod manager not initialized"
    assert engine.bot is None, "Bot should be None in test mode"

@pytest.mark.asyncio
async def test_full_update_flow(engine: AMVEngine) -> None:
    """Test complete update flow: download mod -> create server -> upload mod."""
    try:
        # Get latest version
        version = await engine.mod_manager.get_latest_version()
        assert version is not None, "Failed to get latest version"
        
        # Download mod
        success = await engine.mod_manager.download_mod(version["id"])
        assert success, "Failed to download mod"
        
        # Create and set up server
        assert engine.pterodactyl_manager is not None, "Pterodactyl manager not initialized"
        success = await engine.pterodactyl_manager.create_server()
        assert success, "Failed to create server"
        
        # Wait for installation
        success = await engine.pterodactyl_manager.wait_for_server_installation()
        assert success, "Server installation failed or timed out"
        
        # Upload mod
        mod_file = getattr(settings, 'MOD_FILE_PATH', None)
        assert mod_file is not None, "MOD_FILE_PATH not set"
        success = await engine.pterodactyl_manager.upload_mod_file(str(mod_file))
        assert success, "Failed to upload mod file"
        
        # Check server status
        status = await engine.pterodactyl_manager.get_status()
        assert status["has_server"] == "true", "Server not found"
        assert status["server_state"] in ["running", "ready", "installed"], f"Unexpected server state: {status['server_state']}"
        
    finally:
        # Cleanup
        if engine.pterodactyl_manager and engine.pterodactyl_manager.server_id:
            await engine.pterodactyl_manager.deleteServer()

@pytest.mark.asyncio
async def test_api_endpoints(engine: AMVEngine) -> None:
    """Test API endpoints."""
    from fastapi.testclient import TestClient
    
    client = TestClient(engine.app)
    
    # Test status endpoint
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "is_installed" in data
    
    # Test update endpoint
    response = client.post("/ModUpdate")
    assert response.status_code in [200, 202]  # 202 if async operation started
    data = response.json()
    assert "status" in data
