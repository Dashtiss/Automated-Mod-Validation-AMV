"""Module for handling API endpoints."""
import datetime
import time
import uuid
from typing import Dict, Any, Optional
from fastapi import HTTPException, Request

from ..utils.log_manager import log_manager

logger = log_manager.get_logger(__name__)

class APIHandler:
    def __init__(self, engine):
        """Initialize APIHandler.
        
        Args:
            engine: Instance of AMVEngine
        """
        self.engine = engine
        
    async def log_request(self, request: Request, 
                         response: Any, 
                         start_time: float,
                         error: Optional[Exception] = None):
        """Log request details including timing and response status."""
        duration = time.time() - start_time
        status = "FAILED" if error else "SUCCESS"
        
        # Get request_id from state, fallback to None if not set
        request_id = getattr(request.state, "request_id", str(uuid.uuid4()))
        
        log_data = {
            "timestamp": datetime.datetime.now().isoformat(),
            "request_id": request_id,
            "method": request.method,
            "path": str(request.url.path),
            "duration_ms": round(duration * 1000, 2),
            "status": status
        }
        
        if error:
            log_data["error"] = str(error)
            log_data["error_type"] = type(error).__name__
            logger.error(f"{request.method} {request.url.path} {status} ({log_data['duration_ms']}ms)")
            logger.debug(f"Error details: {error}", exc_info=True)
        else:
            logger.info(f"{request.method} {request.url.path} {status} ({log_data['duration_ms']}ms)")
        
    async def handle_mod_update(self, request: Request) -> Dict[str, Any]:
        """Handle mod update request."""
        start_time = time.time()
        try:
            logger.info("Received mod update request")
            success = await self.engine.handle_mod_update()
            
            response = {
                "status": "Success" if success else "Failed",
                "message": "Update request processed" if success else "Update request failed",
                "details": {
                    "mod_name": self.engine.settings.MOD_INFO["title"],
                    "server_id": (
                        self.engine.pterodactyl_manager.server_id 
                        if self.engine.pterodactyl_manager else None
                    ),
                    "server_name": (
                        self.engine.pterodactyl_manager.current_server_name 
                        if self.engine.pterodactyl_manager else None
                    ),
                    "proxmox_status": "disabled",
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }
            
            await self.log_request(request, response, start_time)
            return response
            
        except Exception as e:
            logger.error(f"Failed to handle mod update request: {e}", exc_info=True)
            response = {
                "status": "Failed",
                "message": f"Update request failed: {str(e)}",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            await self.log_request(request, response, start_time, error=e)
            raise HTTPException(status_code=500, detail=str(e))
            
    async def handle_status_request(self, request: Request) -> Dict[str, Any]:
        """Handle status request."""
        start_time = time.time()
        try:
            logger.info("Received status request")
            base_status = await self.engine.get_status()
            
            response = {
                "status": "Success",
                "message": "Status retrieved successfully",
                "data": {
                    "engine_status": base_status,
                    "pterodactyl": {
                        "server_id": (
                            self.engine.pterodactyl_manager.server_id 
                            if self.engine.pterodactyl_manager else None
                        ),
                        "server_name": (
                            self.engine.pterodactyl_manager.current_server_name 
                            if self.engine.pterodactyl_manager else None
                        ),
                        "is_initialized": bool(self.engine.pterodactyl_manager)
                    },
                    "proxmox": {
                        "status": "disabled",
                        "is_initialized": bool(self.engine.proxmox_manager)
                    },
                    "discord_bot": {
                        "is_ready": bool(self.engine.bot and self.engine.bot.is_ready()),
                        "connected_guilds": len(self.engine.bot.guilds) if self.engine.bot else 0
                    },
                    "timestamp": datetime.datetime.now().isoformat()
                }
            }
            
            await self.log_request(request, response, start_time)
            return response
            
        except Exception as e:
            logger.error(f"Failed to get status: {e}", exc_info=True)
            response = {
                "status": "Failed",
                "message": f"Status check failed: {str(e)}",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            await self.log_request(request, response, start_time, error=e)
            raise HTTPException(status_code=500, detail=str(e))
            
    async def handle_delete_server(self, request: Request) -> Dict[str, Any]:
        """Handle server deletion request."""
        start_time = time.time()
        try:
            logger.info("Received server deletion request")
            await self.engine.delete_server()
            
            response = {
                "status": "Success",
                "message": "Server deleted successfully",
                "timestamp": datetime.datetime.now().isoformat()
            }
            
            await self.log_request(request, response, start_time)
            return response
            
        except Exception as e:
            logger.error(f"Failed to delete server: {e}", exc_info=True)
            response = {
                "status": "Failed",
                "message": f"Server deletion failed: {str(e)}",
                "error": {
                    "type": type(e).__name__,
                    "message": str(e)
                }
            }
            await self.log_request(request, response, start_time, error=e)
            raise HTTPException(status_code=500, detail=str(e))
