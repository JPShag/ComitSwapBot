"""Simple health check HTTP server."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Any

from aiohttp import web
import structlog

logger = structlog.get_logger()


class HealthServer:
    """Simple HTTP server for health checks."""
    
    def __init__(self, port: int = 8080):
        """Initialize health server."""
        self.port = port
        self.app = web.Application()
        self.app.router.add_get('/health', self.health_handler)
        self.app.router.add_get('/status', self.status_handler)
        self.runner = None
        self.site = None
        self._status_data: Dict[str, Any] = {}
        
    async def health_handler(self, request):
        """Handle health check requests."""
        return web.json_response({
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "comit-swap-bot"
        })
        
    async def status_handler(self, request):
        """Handle detailed status requests."""
        return web.json_response({
            "status": "running",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "comit-swap-bot",
            **self._status_data
        })
        
    def update_status(self, **kwargs):
        """Update status data."""
        self._status_data.update(kwargs)
        
    async def start(self):
        """Start the health server."""
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            self.site = web.TCPSite(self.runner, '0.0.0.0', self.port)
            await self.site.start()
            logger.info("Health server started", port=self.port)
        except Exception as e:
            logger.error("Failed to start health server", error=str(e))
            
    async def stop(self):
        """Stop the health server."""
        if self.site:
            await self.site.stop()
        if self.runner:
            await self.runner.cleanup()
        logger.info("Health server stopped")
