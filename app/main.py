#!/usr/bin/env python3
"""
Gmail Cleaner Web Application
FastAPI server with WebSocket support for real-time updates
"""

import asyncio
import json
import os
import webbrowser
import logging
from typing import Dict, Set, Optional, List
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from pydantic import BaseModel

from app.gmail_service import GmailService
from app.models import DomainInfo

logger.info(f"Starting Gmail Cleaner with log level: {LOG_LEVEL}")

app = FastAPI(title="Gmail Cleaner", description="Clean your Gmail inbox with ease")

# Global state
gmail_service = GmailService()
collected_domains: Dict[str, DomainInfo] = {}
connected_websockets: Set[WebSocket] = set()


class ConnectionManager:
    """Manage WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
    
    async def broadcast(self, message_type: str, data: Dict):
        """Broadcast message to all connected clients"""
        message = {"type": message_type, "data": data}
        disconnected = set()
        
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
                # Force immediate send without buffering
                await asyncio.sleep(0)
            except:
                disconnected.add(connection)
        
        # Remove disconnected clients
        for conn in disconnected:
            self.active_connections.discard(conn)


# WebSocket connection manager
manager = ConnectionManager()


# Progress callback for Gmail service
async def progress_callback(message_type: str, data: Dict):
    """Forward Gmail service progress to WebSocket clients"""
    await manager.broadcast(message_type, data)


# Request/Response models
class CleanupRequest(BaseModel):
    domains: list[str]
    dry_run: bool = True
    limit: Optional[int] = None


class CollectRequest(BaseModel):
    limit: Optional[int] = None
    excluded_domains: List[str] = []  # Domains to exclude from scan results
    use_label_protection: bool = True  # Whether custom labels protect threads
    protected_label_ids: Optional[List[str]] = None  # Specific labels to protect (None = all)


class AuthRequest(BaseModel):
    pass


@app.get("/", response_class=HTMLResponse)
def root():
    """Serve the main application page"""
    return FileResponse("app/static/index.html")


@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.get("/auth/status")
def check_auth_status():
    """Check if already authenticated"""
    from pathlib import Path

    token_path = Path("data/token.json")
    creds_path = Path("data/credentials.json")

    if token_path.exists():
        # Try to use existing token
        gmail_service.set_progress_callback(progress_callback)
        if gmail_service.authenticate():
            return {
                "authenticated": True,
                "credentials_path": str(creds_path.absolute()) if creds_path.exists() else None
            }

    return {
        "authenticated": False,
        "credentials_path": str(creds_path.absolute()) if creds_path.exists() else None
    }


@app.post("/auth/upload")
def upload_credentials(credentials: dict):
    """Handle uploaded credentials and start OAuth flow"""
    import json
    from pathlib import Path

    try:
        logger.info("Received credentials upload request")

        # Save credentials temporarily
        creds_path = Path("data/credentials.json")
        creds_path.parent.mkdir(parents=True, exist_ok=True)
        creds_path.write_text(json.dumps(credentials))
        logger.info(f"Saved credentials to {creds_path.absolute()}")

        # Create OAuth flow with uploaded credentials
        redirect_uri = 'http://localhost:8000/oauth/callback'
        auth_url = gmail_service.create_oauth_flow(redirect_uri)
        logger.debug(f"Generated auth URL: {auth_url[:50]}...")

        return {
            "status": "redirect",
            "auth_url": auth_url,
            "message": "Redirect to Google OAuth",
            "credentials_path": str(creds_path.absolute())
        }
    except Exception as e:
        logger.error(f"Error in upload_credentials: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/oauth/callback")
def oauth_callback(code: str = None, error: str = None):
    """Handle OAuth2 callback from Google"""
    if error:
        return RedirectResponse(url="/static/index.html?auth_error=" + error)

    if not code:
        return RedirectResponse(url="/static/index.html?auth_error=no_code")

    # Complete OAuth flow
    gmail_service.set_progress_callback(progress_callback)
    success = gmail_service.complete_oauth_flow(code)

    if success:
        # Redirect to main page with success
        return RedirectResponse(url="/static/index.html?auth_success=true")
    else:
        return RedirectResponse(url="/static/index.html?auth_error=oauth_failed")


@app.post("/collect")
async def collect_domains(request: CollectRequest):
    """Start domain collection process"""
    global collected_domains

    logger.info(f"Collect endpoint called with limit: {request.limit}")

    if not gmail_service.service:
        logger.warning("Not authenticated")
        raise HTTPException(status_code=400, detail="Not authenticated. Please authenticate first.")

    try:
        logger.info(f"Starting domain collection with limit: {request.limit}...")
        # Set up progress callback
        # Create a wrapper to ensure compatibility
        async def async_progress_callback(msg_type: str, data: Dict):
            logger.debug(f"Progress callback: {msg_type} - {data}")
            await manager.broadcast(msg_type, data)

        gmail_service.set_progress_callback(async_progress_callback)

        # Start collection with filtering options
        collected_domains = await gmail_service.collect_domains(
            limit=request.limit,
            excluded_domains=set(request.excluded_domains) if request.excluded_domains else None,
            use_label_protection=request.use_label_protection,
            protected_label_ids=set(request.protected_label_ids) if request.protected_label_ids else None
        )

        logger.info(f"Collection completed. Found {len(collected_domains)} domains")

        # Sort domains by count (highest first)
        sorted_domains = dict(sorted(
            collected_domains.items(),
            key=lambda x: x[1].count,
            reverse=True
        ))

        return {
            "status": "completed",
            "domains": {
                domain: {
                    "count": info.count,
                    "threads": info.threads
                }
                for domain, info in sorted_domains.items()
            },
            "total_domains": len(collected_domains)
        }

    except Exception as e:
        logger.error(f"Collection error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@app.post("/cleanup")
async def cleanup_emails(request: CleanupRequest):
    """Clean up emails based on selected domains"""
    if not gmail_service.service:
        raise HTTPException(status_code=400, detail="Not authenticated. Please authenticate first.")
    
    try:
        # Set up progress callback with async wrapper
        async def async_progress_callback(msg_type: str, data: Dict):
            logger.debug(f"Progress callback: {msg_type} - {data}")
            await manager.broadcast(msg_type, data)

        gmail_service.set_progress_callback(async_progress_callback)
        
        # Convert list to set
        junk_domains = set(request.domains)
        
        # Start cleanup
        result = await gmail_service.cleanup_emails(
            junk_domains=junk_domains,
            dry_run=request.dry_run,
            total_limit=request.limit
        )
        
        return {
            "status": "completed",
            "result": result,
            "mode": "dry_run" if request.dry_run else "live"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cleanup failed: {str(e)}")


@app.get("/labels")
def get_labels():
    """Get all custom Gmail labels for the authenticated user"""
    if not gmail_service.service:
        raise HTTPException(status_code=400, detail="Not authenticated. Please authenticate first.")

    try:
        labels = gmail_service.get_labels()
        return {"labels": labels}
    except Exception as e:
        logger.error(f"Error fetching labels: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch labels: {str(e)}")


@app.get("/domains")
def get_collected_domains():
    """Get previously collected domains"""
    if not collected_domains:
        return {"domains": {}, "total_domains": 0}

    # Sort domains by count (highest first)
    sorted_domains = dict(sorted(
        collected_domains.items(),
        key=lambda x: x[1].count,
        reverse=True
    ))

    return {
        "domains": {
            domain: {
                "count": info.count,
                "threads": info.threads
            }
            for domain, info in sorted_domains.items()
        },
        "total_domains": len(collected_domains)
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket)
    
    try:
        while True:
            # Keep connection alive and handle any client messages
            data = await websocket.receive_text()
            # Echo back for debugging (optional)
            await websocket.send_text(f"Message received: {data}")
            
    except WebSocketDisconnect:
        manager.disconnect(websocket)


# Mount static files AFTER all API routes to avoid conflicts
app.mount("/static", StaticFiles(directory="app/static", html=True), name="static")

# To run this application, use:
# uv run python -m uvicorn app.main:app --reload
