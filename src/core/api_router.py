"""API router configuration and endpoint definitions."""
from fastapi import APIRouter as FastAPIRouter
from fastapi import Request, HTTPException
from typing import Dict, Any

from .api_handler import APIHandler
from ..utils.log_manager import log_manager

logger = log_manager.get_logger(__name__)

class APIRouterManager:
    def __init__(self, engine):
        """Initialize API router.
        
        Args:
            engine: Instance of AMVEngine
        """
        self.engine = engine
        self.handler = APIHandler(engine)
        self.router = FastAPIRouter(prefix="/api/v1", tags=["AMV API"])
        self._setup_routes()
        
    def _setup_routes(self):
        """Set up API routes."""
        
        @self.router.post("/mod/update", summary="Update mod")
        async def update_mod(request: Request) -> Dict[str, Any]:
            """Handle mod update request.
            
            Returns:
                Dict[str, Any]: Response containing update status and details
            """
            return await self.handler.handle_mod_update(request)
            
        @self.router.get("/mod/status", summary="Get mod status")
        async def get_status(request: Request) -> Dict[str, Any]:
            """Get current mod and server status.
            
            Returns:
                Dict[str, Any]: Response containing current status of all components
            """
            return await self.handler.handle_status_request(request)
            
        @self.router.delete("/server", summary="Delete server")
        async def delete_server(request: Request) -> Dict[str, Any]:
            """Delete the current server.
            
            Returns:
                Dict[str, Any]: Response indicating success or failure
            """
            return await self.handler.handle_delete_server(request)
            
        @self.router.get("/health", summary="Health check")
        async def health_check() -> Dict[str, str]:
            """Health check endpoint.
            
            Returns:
                Dict[str, str]: Simple health status
            """
            return {"status": "healthy"}
