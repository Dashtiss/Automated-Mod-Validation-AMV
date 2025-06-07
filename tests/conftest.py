"""Common test fixtures and configuration."""
import os
import pytest
import logging
from typing import AsyncGenerator, Generator
import asyncio
import settings
from src.core.engine import AMVEngine
from src.pterodactyl.pterodactyl import PterodactylManager
from src.core.mod_manager import ModVersionManager

def pytest_configure(config):
    """Configure test environment."""
    # Set test mode
    os.environ["TEST_MODE"] = "1"
    
    # Configure logging for tests
    logging.basicConfig(
        level=logging.DEBUG,
        format='[%(levelname)s] {%(asctime)s} [%(name)s:%(funcName)s] - %(message)s'
    )

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create and provide an event loop for all async tests.
    
    This is a session-scoped fixture that provides the same event loop 
    for all tests in the session.
    """
    # Get the current policy
    policy = asyncio.get_event_loop_policy()
    
    # Create and set a new loop as current
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        yield loop
    finally:
        # Clean up pending tasks
        pending = asyncio.all_tasks(loop)
        
        # Cancel pending tasks
        for task in pending:
            task.cancel()
            
        # Allow tasks to complete/cancel
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            
        # Close the loop
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()
        
        # Clear the current event loop
        asyncio.set_event_loop(None)

@pytest.fixture(scope="session")
def test_settings():
    """Get test settings."""
    return settings

@pytest.fixture(scope="session")
async def mod_manager(event_loop, test_settings) -> AsyncGenerator[ModVersionManager, None]:
    """Create a mod manager instance for testing."""
    manager = ModVersionManager(test_settings)
    try:
        yield manager
    finally:
        # Clean up tasks using the provided event loop
        tasks = [t for t in asyncio.all_tasks(event_loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

@pytest.fixture(scope="session")
async def pterodactyl_manager(event_loop, test_settings) -> AsyncGenerator[PterodactylManager, None]:
    """Create a Pterodactyl manager instance for testing."""
    manager = PterodactylManager(
        api_key=test_settings.PTERODACTYL_API_KEY,
        base_url=test_settings.PTERODACTYL_API_URL,
        egg_id=test_settings.PTERODACTYL_EGG_ID,
        nest_id=test_settings.PTERODACTYL_NEST_ID,
        server_name="test-server",
        settings_obj=test_settings
    )
    try:
        yield manager
    finally:
        # Clean up the test server and tasks using the provided event loop
        await manager.deleteServer()
        tasks = [t for t in asyncio.all_tasks(event_loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

@pytest.fixture(scope="session")
async def engine(event_loop, test_settings) -> AsyncGenerator[AMVEngine, None]:
    """Create an engine instance for testing."""
    engine = AMVEngine(test_settings, test_mode=True)
    try:
        await engine.initialize()
        yield engine
    finally:
        await engine.cleanup()
        # Clean up tasks using the provided event loop
        tasks = [t for t in asyncio.all_tasks(event_loop) if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

def pytest_collection_modifyitems(items):
    """Add custom markers to test items."""
    for item in items:
        if "integration" in item.nodeid:
            item.add_marker(pytest.mark.integration)
        # Mark all tests as asyncio tests
        if not item.get_closest_marker("asyncio"):
            item.add_marker(pytest.mark.asyncio)
