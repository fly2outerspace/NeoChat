"""Frontend messages API routes"""
from fastapi import APIRouter, HTTPException

from app.api.schemas import (
    FrontendMessageCreateRequest,
    FrontendMessageUpdateRequest,
    FrontendMessageResponse,
    FrontendMessageListResponse,
)
from app.storage.frontend_message_repository import FrontendMessageRepository
from app.logger import logger

router = APIRouter(prefix="/v1", tags=["frontend-messages"])


@router.post("/frontend-messages", response_model=FrontendMessageResponse, status_code=201)
async def create_frontend_message(request: FrontendMessageCreateRequest) -> FrontendMessageResponse:
    """Create or update a frontend message (upsert by client_message_id)"""
    try:
        repository = FrontendMessageRepository()
        
        message_id = repository.insert_message(
            session_id=request.session_id,
            client_message_id=request.client_message_id,
            role=request.role,
            message_kind=request.message_kind,
            content=request.content,
            tool_name=request.tool_name,
            tool_call_id=request.tool_call_id,
            input_mode=request.input_mode,
            character_id=request.character_id,
            display_order=request.display_order,
            created_at=request.created_at,
        )
        
        # Fetch the created/updated message
        message = repository.get_message_by_client_id(request.session_id, request.client_message_id)
        if not message:
            raise HTTPException(status_code=500, detail="Failed to retrieve created message")
        
        return FrontendMessageResponse(
            id=message["id"],
            session_id=message["session_id"],
            client_message_id=message["client_message_id"],
            role=message["role"],
            message_kind=message["message_kind"],
            content=message["content"],
            tool_name=message.get("tool_name"),
            tool_call_id=message.get("tool_call_id"),
            input_mode=message.get("input_mode"),
            character_id=message.get("character_id"),
            display_order=message["display_order"],
            created_at=message["created_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating frontend message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.put("/frontend-messages/{message_id}", response_model=FrontendMessageResponse)
async def update_frontend_message(message_id: int, request: FrontendMessageUpdateRequest) -> FrontendMessageResponse:
    """Update an existing frontend message by database ID"""
    try:
        repository = FrontendMessageRepository()
        
        # Update the message
        updated = repository.update_message(
            message_id=message_id,
            content=request.content,
            tool_name=request.tool_name,
            created_at=request.created_at,
        )
        
        if not updated:
            raise HTTPException(status_code=404, detail=f"Message {message_id} not found")
        
        # Fetch the updated message
        with repository._get_cursor() as cursor:
            cursor.execute("""
                SELECT id, session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at
                FROM frontend_messages
                WHERE id = ?
            """, (message_id,))
            row = cursor.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail=f"Message {message_id} not found after update")
            message = dict(row)
        
        return FrontendMessageResponse(
            id=message["id"],
            session_id=message["session_id"],
            client_message_id=message["client_message_id"],
            role=message["role"],
            message_kind=message["message_kind"],
            content=message["content"],
            tool_name=message.get("tool_name"),
            tool_call_id=message.get("tool_call_id"),
            input_mode=message.get("input_mode"),
            character_id=message.get("character_id"),
            display_order=message["display_order"],
            created_at=message["created_at"],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating frontend message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/frontend-messages/{session_id}", response_model=FrontendMessageListResponse)
async def get_frontend_messages(session_id: str) -> FrontendMessageListResponse:
    """Get all frontend messages for a session"""
    try:
        repository = FrontendMessageRepository()
        messages = repository.get_messages_by_session(session_id)
        
        message_responses = [
            FrontendMessageResponse(
                id=msg["id"],
                session_id=msg["session_id"],
                client_message_id=msg["client_message_id"],
                role=msg["role"],
                message_kind=msg["message_kind"],
                content=msg["content"],
                tool_name=msg.get("tool_name"),
                tool_call_id=msg.get("tool_call_id"),
                input_mode=msg.get("input_mode"),
                character_id=msg.get("character_id"),
                display_order=msg["display_order"],
                created_at=msg["created_at"],
            )
            for msg in messages
        ]
        
        return FrontendMessageListResponse(messages=message_responses)
    except Exception as e:
        logger.error(f"Error getting frontend messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/frontend-messages/{session_id}", status_code=204)
async def delete_frontend_messages(session_id: str) -> None:
    """Delete all frontend messages for a session"""
    try:
        repository = FrontendMessageRepository()
        repository.delete_messages_by_session(session_id)
        return None
    except Exception as e:
        logger.error(f"Error deleting frontend messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.delete("/frontend-messages", status_code=204)
async def delete_all_frontend_messages() -> None:
    """Delete all frontend messages (used when loading archives)"""
    try:
        repository = FrontendMessageRepository()
        repository.delete_all_messages()
        return None
    except Exception as e:
        logger.error(f"Error deleting all frontend messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

