#!/usr/bin/env python3
"""
AMV Runner Script
This script handles the initialization and running of the AMV Engine.

Usage:
    python run.py [options]

Options:
    --debug         Enable debug logging
    --test          Run in test mode (no discord bot)
    --port PORT     Specify the port for the API server (default: 8080)
    --host HOST     Specify the host for the API server (default: 127.0.0.1)
    --no-api        Disable the API server
    --check-env     Only check environment variables and exit
"""
import os
import asyncio
import logging
import signal
import sys
import uvicorn
import argparse
from types import FrameType
from typing import Optional, NamedTuple, Any
from datetime import datetime

from src.core.engine import AMVEngine
from src.utils.common import setup_logging
import settings

class AppConfig(NamedTuple):
    """Configuration for the application."""
    debug: bool
    test_mode: bool
    api_port: int
    api_host: str
    enable_api: bool
    check_env_only: bool
    run_tests: bool
    test_only: Optional[str]
    integration_tests: bool
    coverage: bool

# Initialize global components
engine: Optional[AMVEngine] = None
_is_shutting_down: bool = False

async def _cleanup() -> None:
    """Cleanup function that ensures proper shutdown of all components."""
    global engine, _is_shutting_down
    
    if _is_shutting_down:
        return
        
    _is_shutting_down = True
    
    if engine:
        try:
            await engine.cleanup()
        except Exception as e:
            logging.error(f"Error during engine cleanup: {e}")
        finally:
            engine = None
    
    _is_shutting_down = False

def signal_handler(signum: int, frame: Optional[FrameType]) -> None:
    """Handle shutdown signals."""
    sig_name = signal.Signals(signum).name if signum in signal.Signals else str(signum)
    logging.info(f"Received signal {sig_name}, initiating shutdown...")
    
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(_cleanup())
    else:
        loop.run_until_complete(_cleanup())

def parse_arguments() -> AppConfig:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="AMV Engine Runner")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("--test", action="store_true", help="Run in test mode (no discord bot)")
    parser.add_argument("--port", type=int, default=8080, help="API server port")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="API server host")
    parser.add_argument("--no-api", action="store_true", help="Disable API server")
    parser.add_argument("--check-env", action="store_true", help="Only check environment and exit")
    
    # Test-related arguments
    test_group = parser.add_argument_group('Testing')
    test_group.add_argument("--run-tests", action="store_true", help="Run the test suite")
    test_group.add_argument("--test-only", metavar="TEST_PATH", help="Run specific test(s) only")
    test_group.add_argument("--integration", action="store_true", help="Run integration tests only")
    test_group.add_argument("--coverage", action="store_true", help="Generate test coverage report")
    
    args = parser.parse_args()
    return AppConfig(
        debug=args.debug,
        test_mode=args.test,
        api_port=args.port,
        api_host=args.host,
        enable_api=not args.no_api,
        check_env_only=args.check_env,
        run_tests=args.run_tests,
        test_only=args.test_only,
        integration_tests=args.integration,
        coverage=args.coverage
    )

async def check_environment(test_mode: bool = False) -> bool:
    """Check if all required environment variables are set."""
    required_vars = [
        'MOD_ID',
        'PTERODACTYL_API_URL',
        'PTERODACTYL_API_KEY',
        'PTERODACTYL_EGG_ID'
    ]
    
    # Only check Discord-related vars if not in test mode
    if not test_mode:
        required_vars.extend([
            'BOTTOKEN',
            'CHANNEL_ID',
            'CHECKER_REGEX'
        ])

    missing_vars = []
    for var in required_vars:
        if not getattr(settings, var, None):
            missing_vars.append(var)
            
    if missing_vars:
        logging.error("Missing required environment variables:")
        for var in missing_vars:
            logging.error(f"  - {var}")
        return False
        
    logging.info("All required environment variables are set")
    return True

async def run_fastapi(host: str, port: int) -> asyncio.Task:
    """Run the FastAPI server."""
    if not engine or not engine.app:
        raise RuntimeError("Engine or FastAPI app not initialized")
        
    config = uvicorn.Config(
        app=engine.app,
        host=host,
        port=port,
        log_level="debug" if settings.DEBUG else "info"
    )
    
    server = uvicorn.Server(config)
    return asyncio.create_task(server.serve())

async def run_tests(config: AppConfig) -> bool:
    """Run the test suite."""
    import pytest
    
    # Build pytest arguments
    pytest_args = ["-v"]
    
    if config.coverage:
        pytest_args.extend(["--cov=src", "--cov-report=term-missing"])
    
    if config.test_only:
        pytest_args.append(config.test_only)
    elif config.integration_tests:
        pytest_args.append("-m integration")
    else:
        pytest_args.append("tests/")
    
    if config.debug:
        pytest_args.append("-vv")
    
    # Run tests
    logging.info(f"Running tests with arguments: {' '.join(pytest_args)}")
    result = pytest.main(pytest_args)
    
    return result == 0  # 0 means all tests passed

async def main() -> None:
    """Main entry point for the AMV Engine."""
    global engine
    
    # Parse command line arguments
    config = parse_arguments()
    
    # Setup signal handlers
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, signal_handler)
    
    # Print title
    title = settings.format_title({
        "Authors": settings.AUTHORS,
        "Repo": settings.REPO_URL,
        "Version": settings.VERSION,
        "Mode": "TEST" if config.test_mode else "NORMAL"
    })
    print(title)

    # Setup logging
    setup_logging(debug=config.debug)
    
    # Set debug mode in settings if specified
    if config.debug:
        settings.DEBUG = True
    
    logging.info("Starting AMV Engine...")
    if config.test_mode:
        logging.info("Running in TEST mode")

    # Check environment
    if not await check_environment(config.test_mode):
        logging.critical("Required environment variables are missing. Exiting.")
        sys.exit(1)
    if config.check_env_only:
        logging.info("Environment check complete. Exiting.")
        return
        
    if config.run_tests:
        logging.info("Running test suite...")
        success = await run_tests(config)
        if not success:
            logging.error("Tests failed")
            sys.exit(1)
        logging.info("All tests passed")
        return

    server_task = None
    try:
        # Create engine instance
        engine = AMVEngine(settings, test_mode=config.test_mode)
        await engine.initialize()
        
        if config.enable_api:
            try:
                server_task = await run_fastapi(config.api_host, config.api_port)
            except Exception as e:
                logging.error(f"Failed to start API server: {e}")
                await _cleanup()
                return
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt, cleaning up...")
    except Exception as e:
        logging.critical(f"Critical error in main loop: {e}")
        raise
    finally:
        if server_task:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass
        await _cleanup()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Keyboard interrupt received. Shutting down...")
        if asyncio.get_event_loop().is_running():
            asyncio.get_event_loop().run_until_complete(_cleanup())
        else:
            asyncio.run(_cleanup())
    except Exception as e:
        logging.critical(f"Unexpected error: {e}", exc_info=True)
        if asyncio.get_event_loop().is_running():
            asyncio.get_event_loop().run_until_complete(_cleanup())
        else:
            asyncio.run(_cleanup())
        sys.exit(1)
