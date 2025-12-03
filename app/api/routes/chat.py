"""Chat API routes - Unified streaming for Agents and Flows"""
import json
import time
import uuid
from typing import Dict, Any, AsyncIterator, Union, List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatMessage,
    ToolOutputMessage,
    FlowCompletionRequest,
)
from app.api.services.agent_service import AgentService
from app.api.services.flow_service import FlowService
from app.config import LLMSettings
from app.logger import logger
from app.prompt.character import ROLEPLAY_PROMPT
from app.schema import ExecutionEvent
from app.utils.enums import ToolName, InputMode
from app.utils import remove_empty_lines

router = APIRouter(prefix="/v1", tags=["chat"])

# Tool names that should be inlined in content
INLINE_TOOL_NAMES = {ToolName.SEND_TELEGRAM_MESSAGE, ToolName.SPEAK_IN_PERSON}


def _get_model_name(request) -> str:
    """Get model name from request or default config"""
    if hasattr(request, 'model_info') and request.model_info:
        return request.model_info.model
    
    from app.config import config
    default_config = config.llm.get("openai") or config.llm.get("default")
    if default_config:
        return default_config.model if hasattr(default_config, "model") else "gpt-4o"
    return "gpt-4o"


async def generate_streaming_response(
    runnable,
    user_input: str,
    response_id: str,
    model: str,
    input_mode: Optional[InputMode] = None,
) -> AsyncIterator[str]:
    """Generate streaming SSE response from any Runnable (Agent or Flow).
    
    This unified function handles both Agents and Flows since they now
    emit the same ExecutionEvent type.
    
    Args:
        runnable: Agent or Flow instance
        user_input: User input text
        response_id: Response ID for SSE chunks
        model: Model name for response
        input_mode: Optional input mode
        
    Yields:
        SSE formatted strings
    """
    created = int(time.time())
    
    try:
        logger.info(f"Running {runnable.name} with streaming events...")
        kwargs = {}
        if input_mode:
            kwargs["input_mode"] = input_mode
        
        async for event in runnable.run_stream(user_input, **kwargs):
            chunk = None
            
            if event.type == "token":
                if event.content:
                    cleaned_content = remove_empty_lines(event.content)
                    if not cleaned_content:
                        continue
                    delta_payload = {"content": cleaned_content}
                    if event.message_type:
                        delta_payload["tool_event"] = {
                            "type": "tool_output",
                            "message_type": event.message_type,
                            "message_id": event.message_id,
                        }
                    if event.stage:
                        delta_payload["flow_stage"] = event.stage
                    if event.node_id:
                        delta_payload["node_id"] = event.node_id
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": delta_payload,
                            "finish_reason": None
                        }]
                    }
            
            elif event.type == "tool_status":
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or "",
                            "flow_stage": event.stage or "",
                        },
                        "finish_reason": None
                    }]
                }
            
            elif event.type == "tool_output":
                if event.content:
                    cleaned_content = remove_empty_lines(event.content)
                    if not cleaned_content:
                        continue
                    chunk = {
                        "id": response_id,
                        "object": "chat.completion.chunk",
                        "created": created,
                        "model": model,
                        "choices": [{
                            "index": 0,
                            "delta": {
                                "content": event.content,
                                "tool_event": {
                                    "type": "tool_output",
                                    "message_type": event.message_type,
                                    "message_id": event.message_id,
                                },
                                "flow_stage": event.stage or "",
                            },
                            "finish_reason": None
                        }]
                    }
            
            elif event.type in ("step", "flow_step"):
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or "",
                            "flow_stage": event.stage or "",
                        },
                        "finish_reason": None
                    }]
                }
            
            elif event.type == "final":
                if event.content:
                    cleaned_content = remove_empty_lines(event.content)
                    if cleaned_content:
                        chunk = {
                            "id": response_id,
                            "object": "chat.completion.chunk",
                            "created": created,
                            "model": model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": cleaned_content},
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
                # Send finish chunk
                finish_chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {},
                        "finish_reason": "stop"
                    }]
                }
                yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
                return
            
            elif event.type == "error":
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or "",
                            "flow_stage": event.stage or "",
                        },
                        "finish_reason": None
                    }]
                }
            
            if chunk:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        
        # If we didn't get a final event, send finish chunk
        finish_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(finish_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error("Error in streaming response: %s", e, exc_info=True)
        error_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {"tool_status": f"❌ 错误: {str(e)}"},
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


async def gather_response(
    runnable,
    user_input: str,
    input_mode: Optional[InputMode] = None
) -> tuple[str, List[ToolOutputMessage]]:
    """Run any Runnable and collect final content + tool outputs.
    
    Args:
        runnable: Agent or Flow instance
        user_input: User input text
        input_mode: Optional input mode
        
    Returns:
        Tuple of (content, tool_outputs)
    """
    content_segments: List[str] = []
    tool_outputs_map: Dict[str, ToolOutputMessage] = {}

    kwargs = {}
    if input_mode:
        kwargs["input_mode"] = input_mode
    
    async for event in runnable.run_stream(user_input, **kwargs):
        if event.type == "token":
            if event.message_type and event.message_type.lower() not in {tool.value for tool in INLINE_TOOL_NAMES}:
                key = event.message_id or event.message_type
                entry = tool_outputs_map.setdefault(
                    key,
                    ToolOutputMessage(
                        tool_name=event.message_type,
                        content="",
                        tool_call_id=event.message_id,
                    ),
                )
                entry.content += event.content or ""
            else:
                if event.content:
                    content_segments.append(event.content)
        elif event.type == "tool_output":
            if event.message_type and event.message_type.lower() in {tool.value for tool in INLINE_TOOL_NAMES}:
                if event.content:
                    content_segments.append(event.content)
            elif event.message_type and event.content:
                key = event.message_id or event.message_type
                entry = tool_outputs_map.setdefault(
                    key,
                    ToolOutputMessage(
                        tool_name=event.message_type,
                        content="",
                        tool_call_id=event.message_id,
                    ),
                )
                entry.content += event.content
        elif event.type == "final":
            break

    raw_content = "".join(content_segments)
    content = remove_empty_lines(raw_content).strip()
    tool_outputs = [output for output in tool_outputs_map.values() if output.content]
    return content, tool_outputs


def _upsert_character(character_id: str, character_name: str, roleplay_prompt: str):
    """Upsert character to archive database"""
    try:
        from app.storage.archive_character_repository import ArchiveCharacterRepository
        archive_char_repo = ArchiveCharacterRepository()
        archive_char_repo.upsert_character(
            character_id=character_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            avatar=None,
        )
        logger.debug(f"Upserted character {character_id} to archive database")
    except Exception as e:
        logger.warning(f"Failed to upsert character to archive database: {e}")


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> Union[Dict[str, Any], StreamingResponse]:
    """OpenAI-compatible chat completions endpoint using Agent"""
    try:
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        session_id = request.session_id
        
        # Extract character info
        character_name = "Stacy"
        roleplay_prompt = ROLEPLAY_PROMPT
        character_id = None
        if request.character:
            character_name = request.character.name
            roleplay_prompt = request.character.roleplay_prompt or ROLEPLAY_PROMPT
            character_id = request.character.character_id
            _upsert_character(character_id, character_name, roleplay_prompt)
        
        # Extract LLM settings
        llm_settings = None
        if request.model_info:
            llm_settings = LLMSettings(
                model=request.model_info.model,
                base_url=request.model_info.base_url,
                api_key=request.model_info.api_key or "",
                max_tokens=request.model_info.max_tokens,
                temperature=request.model_info.temperature,
                api_type=request.model_info.api_type,
            )
        
        # Validate input
        if not request.user_input or not request.user_input.strip():
            raise HTTPException(status_code=400, detail="user_input is required")
        if not request.input_mode:
            raise HTTPException(status_code=400, detail="input_mode is required")
        
        user_input = request.user_input.strip()
        input_mode = request.input_mode
        participants = request.participants if hasattr(request, 'participants') else None
        
        # Create agent
        agent = AgentService.create_agent(
            session_id=session_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            character_id=character_id,
            llm_settings=llm_settings,
            visible_for_characters=participants,
        )
        
        logger.info(f"Processing chat request for session {session_id}: {user_input[:50]}...")
        
        # Handle streaming
        if request.stream:
            response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            model = _get_model_name(request)
            
            return StreamingResponse(
                generate_streaming_response(
                    runnable=agent,
                    user_input=user_input,
                    response_id=response_id,
                    model=model,
                    input_mode=input_mode,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        
        # Non-streaming
        response_content, tool_outputs = await gather_response(agent, user_input, input_mode)
        
        response = ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=_get_model_name(request),
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(
                    role="assistant",
                    content=response_content or "",
                    tool_outputs=tool_outputs or None,
                ),
                finish_reason="stop"
            )]
        )
        
        response_dict = response.model_dump()
        response_dict["session_id"] = session_id
        return response_dict
        
    except RuntimeError as e:
        if "Cannot run" in str(e):
            raise HTTPException(status_code=503, detail="Service is busy")
        raise HTTPException(status_code=503, detail="Service not available")
    except Exception as e:
        logger.error("Error processing chat request: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/flow/completions", response_model=None)
async def flow_completions(request: FlowCompletionRequest) -> Union[Dict[str, Any], StreamingResponse]:
    """Flow-based chat completions endpoint"""
    try:
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id is required")
        session_id = request.session_id
        
        # Extract LLM settings
        llm_settings = None
        if request.model_info:
            llm_settings = LLMSettings(
                model=request.model_info.model,
                base_url=request.model_info.base_url,
                api_key=request.model_info.api_key or "",
                max_tokens=request.model_info.max_tokens,
                temperature=request.model_info.temperature,
                api_type=request.model_info.api_type,
            )
        
        # Extract character info
        character_name = "character_flow"
        roleplay_prompt = None
        character_id = None
        if request.character:
            character_name = request.character.name
            roleplay_prompt = request.character.roleplay_prompt
            character_id = request.character.character_id
            if character_id:
                _upsert_character(character_id, character_name, roleplay_prompt or "")
        
        # Validate input
        if not request.user_input or not request.user_input.strip():
            raise HTTPException(status_code=400, detail="user_input is required")
        
        user_input = request.user_input.strip()
        input_mode = request.input_mode or InputMode.PHONE
        participants = request.participants if hasattr(request, 'participants') else None
        
        # Create flow
        flow = FlowService.create_flow(
            flow_type=request.flow_type,
            session_id=session_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            llm_settings=llm_settings,
            visible_for_characters=participants,
            character_id=character_id,
        )
        
        logger.info(f"Processing flow request for session {session_id}: {user_input[:50]}...")
        
        # Handle streaming
        if request.stream:
            response_id = f"flowcmpl-{uuid.uuid4().hex[:8]}"
            model = _get_model_name(request)
            
            return StreamingResponse(
                generate_streaming_response(
                    runnable=flow,
                    user_input=user_input,
                    response_id=response_id,
                    model=model,
                    input_mode=input_mode,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        
        # Non-streaming
        response_content, _ = await gather_response(flow, user_input, input_mode)
        
        response = ChatCompletionResponse(
            id=f"flowcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=_get_model_name(request),
            choices=[ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_content or ""),
                finish_reason="stop"
            )]
        )
        
        response_dict = response.model_dump()
        response_dict["session_id"] = session_id
        return response_dict
        
    except RuntimeError as e:
        if "Cannot run" in str(e):
            raise HTTPException(status_code=503, detail="Service is busy")
        raise HTTPException(status_code=503, detail="Service not available")
    except Exception as e:
        logger.error("Error processing flow request: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
