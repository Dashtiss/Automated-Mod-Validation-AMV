"""Test cases for the mod manager functionality."""
import os
import asyncio
import pytest
import logging
from typing import Any, AsyncGenerator
import pytest_asyncio
from src.core.mod_manager import ModVersionManager
import settings

@pytest.fixture(scope="session")
def test_settings() -> Any:
    """Get test settings."""
    return settings

@pytest_asyncio.fixture
async def mod_manager(test_settings: Any) -> AsyncGenerator[ModVersionManager, None]:
    """Create a mod manager instance for testing."""
    manager = ModVersionManager(test_settings)
    yield manager
    # Clean up any temporary files or resources
    mod_file = getattr(settings, 'MOD_FILE_PATH', None)
    if mod_file and os.path.exists(mod_file):
        try:
            os.remove(mod_file)
        except Exception as e:
            logging.warning(f"Failed to cleanup mod file: {e}")
    
    # Cancel any remaining tasks
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

@pytest.mark.asyncio
async def test_get_latest_version(mod_manager: ModVersionManager) -> None:
    """Test fetching latest mod version."""
    version = await mod_manager.get_latest_version()
    assert version is not None, "Failed to get latest version"
    assert "id" in version, "Version info missing ID"
    assert "name" in version, "Version info missing name"
    assert "version_number" in version, "Version info missing version number"

@pytest.mark.asyncio
async def test_download_mod(mod_manager: ModVersionManager) -> None:
    """Test downloading the latest mod version."""
    # Get latest version first
    version = await mod_manager.get_latest_version()
    assert version is not None, "Failed to get latest version"
    
    # Try downloading
    success = await mod_manager.download_mod(version["id"])
    assert success, "Failed to download mod"
    
    # Verify file exists
    mod_file = getattr(settings, 'MOD_FILE_PATH', None)
    assert mod_file is not None, "MOD_FILE_PATH not set"
    assert os.path.exists(mod_file), f"Mod file not found at {mod_file}"

@pytest.mark.asyncio
async def test_version_compatibility(mod_manager: ModVersionManager) -> None:
    """Test version compatibility checks."""
    version = await mod_manager.get_latest_version()
    assert version is not None, "Failed to get latest version"
    
    # Check game versions
    game_versions = version.get("game_versions", [])
    assert len(game_versions) > 0, "No game versions found"
    assert all(isinstance(v, str) for v in game_versions), "Invalid game version format"
    
    # Check loaders
    loaders = version.get("loaders", [])
    assert len(loaders) > 0, "No mod loaders found"
    assert all(isinstance(l, str) for l in loaders), "Invalid loader format"
    
    # Check specific loader compatibility
    fabric_compatible = any(l.lower() == "fabric" for l in loaders)
    forge_compatible = any(l.lower() == "forge" for l in loaders)
    assert fabric_compatible or forge_compatible, "Mod not compatible with Fabric or Forge"
