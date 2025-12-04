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
    SSEEvent,
    SSEToolInfo,
)
from app.api.services.agent_service import AgentService
from app.api.services.flow_service import FlowService
from app.config import LLMSettings
from app.logger import logger
from app.prompt.character import ROLEPLAY_PROMPT
from app.schema import ExecutionEvent, ExecutionEventType
from app.utils.enums import ToolName, InputMode
from app.utils import remove_empty_lines

router = APIRouter(prefix="/v1", tags=["chat"])

# Tool names that should be inlined in content
INLINE_TOOL_NAMES = {ToolName.SEND_TELEGRAM_MESSAGE, ToolName.SPEAK_IN_PERSON}


def _get_model_name(request) -> str:
    """Get model name from request or default config"""
    if hasattr(request, 'chat_modelinfo') and request.chat_modelinfo:
        return request.chat_modelinfo.model
    
    from app.config import config
    default_config = config.llm.get("openai") or config.llm.get("default")
    if default_config:
        return default_config.model if hasattr(default_config, "model") else "gpt-4o"
    return "gpt-4o"


async def generate_streaming_response(
    runnable,
    user_input: str,
    input_mode: Optional[InputMode] = None,
) -> AsyncIterator[str]:
    """Generate streaming SSE response from any Runnable (Agent or Flow).
    
    Uses simplified SSEEvent format instead of verbose OpenAI format.
    
    Args:
        runnable: Agent or Flow instance
        user_input: User input text
        input_mode: Optional input mode
        
    Yields:
        SSE formatted strings
    """
    try:
        logger.info(f"Running {runnable.name} with streaming events...")
        kwargs = {}
        if input_mode:
            kwargs["input_mode"] = input_mode
        
        async for event in runnable.run_stream(user_input, **kwargs):
            sse_event = None
            
            # TOKEN: Text content (streaming text, tool output)
            if event.type == ExecutionEventType.TOKEN:
                if event.content:
                    cleaned_content = remove_empty_lines(event.content)
                    if not cleaned_content:
                        continue
                    tool_info = None
                    if event.message_type and event.message_id:
                        tool_info = SSEToolInfo(name=event.message_type, id=event.message_id)
                    sse_event = SSEEvent.create_token(
                        content=cleaned_content,
                        tool=tool_info,
                        stage=event.stage,
                        node_id=event.node_id,
                    )
            
            # STATUS: Progress/status update
            elif event.type == ExecutionEventType.STATUS:
                sse_event = SSEEvent.create_status(
                    status=event.content or "",
                    stage=event.stage,
                    node_id=event.node_id,
                )
            
            # STEP: Execution step marker
            elif event.type == ExecutionEventType.STEP:
                sse_event = SSEEvent.create_status(
                    status=event.content or "",
                    stage=event.stage,
                    node_id=event.node_id,
                )
            
            # DONE: Execution complete
            elif event.type == ExecutionEventType.DONE:
                if event.content:
                    cleaned_content = remove_empty_lines(event.content)
                    if cleaned_content:
                        yield SSEEvent.create_token(content=cleaned_content).to_sse()
                yield SSEEvent.create_done().to_sse()
                yield "data: [DONE]\n\n"
                return
            
            # ERROR: Error occurred
            elif event.type == ExecutionEventType.ERROR:
                sse_event = SSEEvent.create_error(
                    content=event.content or "Unknown error",
                    stage=event.stage,
                )
            
            if sse_event:
                yield sse_event.to_sse()
        
        # If we didn't get a final event, send done
        yield SSEEvent.create_done().to_sse()
        yield "data: [DONE]\n\n"
        
    except Exception as e:
        logger.error("Error in streaming response: %s", e, exc_info=True)
        yield SSEEvent.create_error(content=str(e)).to_sse()
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
        # TOKEN events: text content and tool output
        if event.type == ExecutionEventType.TOKEN:
            if event.message_type and event.message_type.lower() not in {tool.value for tool in INLINE_TOOL_NAMES}:
                # External tool output - collect separately
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
                # Inline tool output or regular text - add to content
                if event.content:
                    content_segments.append(event.content)
        # DONE event: execution complete
        elif event.type == ExecutionEventType.DONE:
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
        
        # Extract LLM settings from chat_modelinfo (optional, falls back to default config)
        llm_settings = None
        if request.chat_modelinfo:
            llm_settings = LLMSettings(
                model=request.chat_modelinfo.model,
                base_url=request.chat_modelinfo.base_url,
                api_key=request.chat_modelinfo.api_key or "",
                max_tokens=request.chat_modelinfo.max_tokens,
                temperature=request.chat_modelinfo.temperature,
                api_type=request.chat_modelinfo.api_type,
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
            return StreamingResponse(
                generate_streaming_response(
                    runnable=agent,
                    user_input=user_input,
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
        
        # Extract LLM settings for chat and inference models
        chat_llm_settings = None
        infer_llm_settings = None
        
        if request.chat_modelinfo:
            chat_llm_settings = LLMSettings(
                model=request.chat_modelinfo.model,
                base_url=request.chat_modelinfo.base_url,
                api_key=request.chat_modelinfo.api_key or "",
                max_tokens=request.chat_modelinfo.max_tokens,
                temperature=request.chat_modelinfo.temperature,
                api_type=request.chat_modelinfo.api_type,
            )
        
        if request.infer_modelinfo:
            infer_llm_settings = LLMSettings(
                model=request.infer_modelinfo.model,
                base_url=request.infer_modelinfo.base_url,
                api_key=request.infer_modelinfo.api_key or "",
                max_tokens=request.infer_modelinfo.max_tokens,
                temperature=request.infer_modelinfo.temperature,
                api_type=request.infer_modelinfo.api_type,
            )
        elif chat_llm_settings:
            # Use chat model for inference if only chat_modelinfo is provided
            infer_llm_settings = chat_llm_settings
        
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
        
        # Create flow with chat and inference LLM settings
        from app.llm import LLM
        chat_llm = LLM(settings=chat_llm_settings) if chat_llm_settings else None
        infer_llm = LLM(settings=infer_llm_settings) if infer_llm_settings else None
        
        flow = FlowService.create_flow(
            flow_type=request.flow_type,
            session_id=session_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            llm_settings=None,  # Don't use single llm_settings, use chat_llm and infer_llm instead
            visible_for_characters=participants,
            character_id=character_id,
            chat_llm=chat_llm,
            infer_llm=infer_llm,
        )
        
        logger.info(f"Processing flow request for session {session_id}: {user_input[:50]}...")
        
        # Handle streaming
        if request.stream:
            return StreamingResponse(
                generate_streaming_response(
                    runnable=flow,
                    user_input=user_input,
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
