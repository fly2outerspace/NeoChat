"""Session management API routes"""
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    SessionResponse,
    SessionListResponse,
)
from app.storage.session_repository import SQLiteSessionRepository
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["sessions"])


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions() -> SessionListResponse:
    """List all sessions from the current database"""
    try:
        repository = SQLiteSessionRepository()
        sessions = repository.list_sessions()
        
        session_responses = [
            SessionResponse(
                id=session["id"],
                name=session["name"],
                created_at=session["created_at"],
                updated_at=session["updated_at"],
                message_count=session.get("message_count", 0) if isinstance(session, dict) else 0,
            )
            for session in sessions
        ]
        
        return SessionListResponse(sessions=session_responses)
    except Exception as e:
        logger.error(f"Error listing sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

