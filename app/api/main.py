"""FastAPI application main file"""
import json
import os
import sys
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, FileResponse

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import chat, search, character, model, time, archive
from app.logger import logger
from app.config import config
from app.storage.meilisearch_service import MeilisearchService
from app.storage.model_init import init_default_models


def get_frontend_static_path() -> Path | None:
    """
    Get the path to frontend static files.
    Returns None if not found (development mode).
    
    In packaged mode (PyInstaller), files are in:
    - exe_dir/_internal/frontend (if bundled with COLLECT)
    - or sys._MEIPASS/frontend (if using onefile mode)
    
    In development mode:
    - frontend/web-chat/out (after npm build)
    """
    # Check if running in PyInstaller bundle
    if getattr(sys, 'frozen', False):
        # Running in PyInstaller bundle
        exe_dir = Path(sys.executable).parent
        
        # Check _internal directory first (COLLECT mode)
        static_path = exe_dir / "_internal" / "frontend"
        if static_path.exists() and (static_path / "index.html").exists():
            logger.info(f"Found frontend in _internal: {static_path}")
            return static_path
        
        # Check MEIPASS (onefile mode)
        if hasattr(sys, '_MEIPASS'):
            base_path = Path(sys._MEIPASS)
            static_path = base_path / "frontend"
            if static_path.exists() and (static_path / "index.html").exists():
                logger.info(f"Found frontend in MEIPASS: {static_path}")
                return static_path
        
        # Check relative to executable
        static_path = exe_dir / "frontend"
        if static_path.exists() and (static_path / "index.html").exists():
            logger.info(f"Found frontend next to exe: {static_path}")
            return static_path
    
    # Development mode: check for built frontend
    dev_static_path = Path(__file__).parent.parent.parent / "frontend" / "web-chat" / "out"
    if dev_static_path.exists() and (dev_static_path / "index.html").exists():
        logger.info(f"Found frontend in dev mode: {dev_static_path}")
        return dev_static_path
    
    return None


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log all HTTP requests with body and headers"""
    
    async def dispatch(self, request: Request, call_next):
        # Log request headers
        headers = dict(request.headers)
        logger.debug(f"Request Headers: {json.dumps(headers, indent=2, ensure_ascii=False)}")
        
        # Read request body
        body = b""
        try:
            body = await request.body()
            if body:
                # Try to parse as JSON
                try:
                    body_json = json.loads(body.decode())
                    logger.debug(f"Request Body (JSON): {json.dumps(body_json, indent=2, ensure_ascii=False)}")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    # If not JSON, log as string (truncate if too long)
                    body_str = body.decode('utf-8', errors='replace')
                    if len(body_str) > 1000:
                        logger.info(f"Request Body (Text, truncated): {body_str[:1000]}...")
                    else:
                        logger.info(f"Request Body (Text): {body_str}")
        except Exception as e:
            logger.warning(f"Failed to read request body: {e}")
        
        # Recreate request with body (since body can only be read once)
        # Create a new receive function that returns the cached body
        body_sent = [False]  # Use list to allow modification in nested function
        
        async def receive():
            if body_sent[0]:
                # After sending the body, return empty body to indicate completion
                # This is the correct ASGI way to signal no more data
                return {"type": "http.request", "body": b"", "more_body": False}
            body_sent[0] = True
            # Return the cached body with more_body=False to indicate it's complete
            return {"type": "http.request", "body": body, "more_body": False}
        
        # Create a new Request object with the recreated receive function
        # This is safer than modifying the existing request object
        scope = request.scope
        new_request = Request(scope, receive)
        
        # Process request with the new request object
        response = await call_next(new_request)
        
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events"""
    # Startup: Initialize settings database (character and model tables)
    logger.info("Initializing settings database...")
    try:
        from app.storage.settings_database import init_settings_database
        init_settings_database()
        logger.info("Settings database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize settings database: {e}", exc_info=True)
        # Don't fail startup if settings database initialization fails
    
    # Startup: Initialize database
    logger.info("Initializing database...")
    # Initialize default database file directly to avoid recursion
    from app.storage.database import init_database_for_path, DB_PATH
    init_database_for_path(DB_PATH)
    logger.info("Database initialized successfully")
    
    # Startup: Initialize database manager and default archive
    logger.info("Initializing database manager...")
    try:
        from app.storage.database_manager import DatabaseManager
        db_manager = DatabaseManager()
        db_manager.initialize_working_database()
        logger.info("Database manager initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database manager: {e}", exc_info=True)
        # Don't fail startup if archive initialization fails
    
    # Startup: Initialize default model configurations (in settings database)
    logger.info("Initializing default model configurations...")
    try:
        init_default_models()
        logger.info("Default models initialized successfully")
    except Exception as e:
        logger.warning(f"Failed to initialize default models: {e}", exc_info=True)
        # Don't fail startup if model initialization fails
    
    # Startup: Initialize Meilisearch service (global singleton)
    meilisearch_config = config.meilisearch
    meilisearch_service = MeilisearchService()  # Get singleton instance
    
    if meilisearch_config:
        # Initialize service with configuration
        meilisearch_service.initialize(
            executable_path=meilisearch_config.executable_path,
            db_path=meilisearch_config.db_path,
            http_addr=meilisearch_config.http_addr,
            api_key=os.getenv("MEILISEARCH_API_KEY", None),
            auto_connect=False  # We'll connect after starting if needed
        )
        
        # Auto-start if configured
        if meilisearch_config.auto_start:
            if not meilisearch_config.executable_path:
                error_msg = "Meilisearch auto_start is enabled but executable_path is not configured"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            
            try:
                if not meilisearch_service.start(wait_for_ready=True, timeout=30):
                    error_msg = "Failed to start Meilisearch - service cannot start without Meilisearch"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                
                logger.info("Meilisearch started successfully")
                
                # Note: Meilisearch will be refreshed when needed (e.g., when loading an archive)
                # So we don't need auto_sync here anymore.
            except RuntimeError:
                # Re-raise RuntimeError (our own errors)
                raise
            except Exception as e:
                error_msg = f"Error starting Meilisearch: {e} - service cannot start without Meilisearch"
                logger.error(error_msg, exc_info=True)
                raise RuntimeError(error_msg) from e
        else:
            # Try to connect to existing Meilisearch instance
            if not meilisearch_service._connect():
                error_msg = "Failed to connect to existing Meilisearch instance - service cannot start without Meilisearch"
                logger.error(error_msg)
                raise RuntimeError(error_msg)
            logger.info("Connected to existing Meilisearch instance successfully")
    
    # Store service in app state for easy access
    app.state.meilisearch_service = meilisearch_service
    
    yield
    
    # Shutdown: Stop Meilisearch if we started it
    if meilisearch_config and meilisearch_config.auto_start:
        logger.info("Stopping Meilisearch...")
        try:
            meilisearch_service.stop()
        except Exception as e:
            logger.error(f"Error stopping Meilisearch: {e}")
    
    # Shutdown: Cleanup (if needed)
    logger.info("Shutting down API server...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="NeoChat API",
    description="NeoChat Agent API Server",
    version="1.0.0",
    lifespan=lifespan,
)

# Add request logging middleware (before CORS)
app.add_middleware(RequestLoggingMiddleware)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(chat.router)
app.include_router(search.router)
app.include_router(character.router)
app.include_router(model.router)
app.include_router(time.router)
app.include_router(archive.router)
from app.api.routes import frontend_messages, sessions
app.include_router(frontend_messages.router)
app.include_router(sessions.router)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


# Mount frontend static files if available (for packaged deployment)
_frontend_path = get_frontend_static_path()
if _frontend_path:
    logger.info(f"Mounting frontend static files from: {_frontend_path}")
    
    # Serve static assets (js, css, images, etc.)
    app.mount("/_next", StaticFiles(directory=str(_frontend_path / "_next")), name="next_static")
    
    # Serve index.html for root path
    @app.get("/")
    async def serve_frontend_root():
        """Serve frontend index.html"""
        return FileResponse(str(_frontend_path / "index.html"))
    
    # Catch-all route for SPA - must be last
    @app.get("/{full_path:path}")
    async def serve_frontend_spa(full_path: str):
        """Serve frontend for SPA routes"""
        # Try to serve the exact file first
        file_path = _frontend_path / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        
        # For directories, try index.html
        if file_path.exists() and file_path.is_dir():
            index_path = file_path / "index.html"
            if index_path.exists():
                return FileResponse(str(index_path))
        
        # Otherwise, serve root index.html for SPA routing
        return FileResponse(str(_frontend_path / "index.html"))
else:
    logger.info("Frontend static files not found - running in API-only mode")
    logger.info("To enable frontend: cd frontend/web-chat && pnpm build")
    
    @app.get("/")
    async def root():
        """Root endpoint (API-only mode)"""
        return {"message": "NeoChat API Server", "status": "running", "mode": "api-only"}


if __name__ == "__main__":
    import uvicorn
    logger.info("Starting NeoChat API server...")
    uvicorn.run(app, host="0.0.0.0", port=8000)

