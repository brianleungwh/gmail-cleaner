#!/usr/bin/env python3
"""
Gmail Cleaner Web Application
FastAPI server with WebSocket support for real-time updates
"""

import asyncio
import json
import webbrowser
from typing import Dict, Set
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel

from app.gmail_service import GmailService, DomainInfo


app = FastAPI(title="Gmail Cleaner", description="Clean your Gmail inbox with ease")

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

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
    limit: int = None


class AuthRequest(BaseModel):
    pass


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main application page"""
    return RedirectResponse(url="/static/index.html")


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


@app.post("/auth")
async def authenticate():
    """Authenticate with Gmail API"""
    # Set up progress callback
    gmail_service.set_progress_callback(progress_callback)
    
    # Attempt authentication
    success = gmail_service.authenticate()
    
    if success:
        return {"status": "authenticated", "message": "Successfully connected to Gmail"}
    else:
        raise HTTPException(status_code=400, detail="Authentication failed")


@app.post("/collect")
async def collect_domains():
    """Start domain collection process"""
    global collected_domains
    
    if not gmail_service.service:
        raise HTTPException(status_code=400, detail="Not authenticated. Please authenticate first.")
    
    try:
        # Set up progress callback
        gmail_service.set_progress_callback(progress_callback)
        
        # Start collection
        collected_domains = await gmail_service.collect_domains()
        
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
                    "sample_subjects": info.sample_subjects
                }
                for domain, info in sorted_domains.items()
            },
            "total_domains": len(collected_domains)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Collection failed: {str(e)}")


@app.post("/cleanup")
async def cleanup_emails(request: CleanupRequest):
    """Clean up emails based on selected domains"""
    if not gmail_service.service:
        raise HTTPException(status_code=400, detail="Not authenticated. Please authenticate first.")
    
    try:
        # Set up progress callback
        gmail_service.set_progress_callback(progress_callback)
        
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


@app.get("/domains")
async def get_collected_domains():
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
                "sample_subjects": info.sample_subjects
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


if __name__ == "__main__":
    import uvicorn
    
    # Open browser automatically
    def open_browser():
        webbrowser.open("http://localhost:8000")
    
    # Start server with auto-reload for development
    print("Starting Gmail Cleaner Web Application...")
    print("Opening browser at http://localhost:8000")
    
    # Delay browser opening slightly to ensure server is ready
    import threading
    import time
    def delayed_open():
        time.sleep(1)
        open_browser()
    
    browser_thread = threading.Thread(target=delayed_open)
    browser_thread.daemon = True
    browser_thread.start()
    
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")