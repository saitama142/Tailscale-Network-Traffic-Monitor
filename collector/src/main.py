"""
Main FastAPI application for the collector.
"""
import os
import sys
import logging
from fastapi import FastAPI
from fastapi.responses import PlainTextResponse, JSONResponse
from contextlib import asynccontextmanager

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from shared.constants import API_PREFIX, CLI_VERSION
from collector.src.api import router
from collector.src.database import get_database

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Tailscale Network Monitor Collector")
    db = get_database()
    logger.info(f"Database initialized at {db.db_path}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down collector")
    db.close()


# Create FastAPI app
app = FastAPI(
    title="Tailscale Network Monitor",
    description="Real-time network traffic monitoring for Tailscale networks",
    version=CLI_VERSION,
    lifespan=lifespan
)

# Include API routes
app.include_router(router, prefix=API_PREFIX)


@app.get("/")
def root():
    """Root endpoint."""
    return {
        "service": "Tailscale Network Monitor",
        "version": CLI_VERSION,
        "status": "running",
        "api_docs": "/docs"
    }


@app.get("/install/agent.sh", response_class=PlainTextResponse)
def get_agent_installer():
    """Serve the agent installation script."""
    # Try multiple possible paths
    possible_paths = [
        "/opt/tailscale-monitor/../scripts/install-agent.sh",
        "/tmp/tailscale-monitor/scripts/install-agent.sh",
        os.path.join(os.path.dirname(__file__), "../../scripts/install-agent.sh")
    ]
    
    for script_path in possible_paths:
        if os.path.exists(script_path):
            with open(script_path, 'r') as f:
                return f.read()
    
    return PlainTextResponse(
        content="# Agent installer script not found\nexit 1",
        status_code=404
    )


@app.get("/install/agent.ps1", response_class=PlainTextResponse)
def get_agent_installer_windows():
    """Serve the Windows agent installation script."""
    script_path = os.path.join(os.path.dirname(__file__), "../../scripts/install-agent.ps1")
    
    if os.path.exists(script_path):
        with open(script_path, 'r') as f:
            return f.read()
    else:
        return PlainTextResponse(
            content="# Windows agent installer script not found\nExit 1",
            status_code=404
        )


if __name__ == "__main__":
    import uvicorn
    
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8080"))
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )
