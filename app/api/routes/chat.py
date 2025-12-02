"""Chat API routes"""
import json
import time
import uuid
import asyncio
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
from app.agent.base import AgentState
from app.config import LLMSettings
from app.logger import logger
from app.prompt.character import ROLEPLAY_PROMPT
from app.schema import AgentStreamEvent, FlowEvent
from app.utils.enums import ToolName
from app.utils.enums import InputMode
from app.utils import remove_empty_lines

router = APIRouter(prefix="/v1", tags=["chat"])

# Streaming mode configuration
# "line": stream by line (逐行流式)
# "char": stream by character (逐字流式)
STREAMING_MODE = "char"  # Change this to switch between modes
INLINE_TOOL_NAMES = {ToolName.SEND_TELEGRAM_MESSAGE, ToolName.SPEAK_IN_PERSON}


async def gather_agent_response(agent, user_input: str, input_mode: Optional[InputMode] = None) -> tuple[str, List[ToolOutputMessage]]:
    """Run agent via run_stream and collect final content + tool outputs."""
    content_segments: List[str] = []
    tool_outputs_map: Dict[str, ToolOutputMessage] = {}

    # Pass input_mode as kwargs if provided
    kwargs = {}
    if input_mode:
        kwargs["input_mode"] = input_mode
    async for event in agent.run_stream(user_input, **kwargs):
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

    # Join all content segments and remove empty lines for cleaner output
    raw_content = "".join(content_segments)
    content = remove_empty_lines(raw_content).strip()
    tool_outputs = [output for output in tool_outputs_map.values() if output.content]
    return content, tool_outputs

async def generate_streaming_response(
    agent,
    user_input: str,
    response_id: str,
    model: str,
    session_id: str,
    input_mode: Optional[InputMode] = None,
) -> AsyncIterator[str]:
    """
    Generate streaming SSE response from agent events.
    Converts AgentStreamEvent to OpenAI-compatible SSE chunks.
    """
    created = int(time.time())
    
    try:
        # Run agent with streaming events
        logger.info(f"Running agent with streaming events...")
        # Pass input_mode as kwargs if provided
        kwargs = {}
        if input_mode:
            kwargs["input_mode"] = input_mode
        async for event in agent.run_stream(user_input, **kwargs):
            chunk = None
            
            if event.type == "token":
                if event.content:
                    # Remove empty lines from token content to avoid noisy blank lines
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
                # Tool status event: send as tool_status in delta
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or ""
                        },
                        "finish_reason": None
                    }]
                }
            
            elif event.type == "tool_output":
                if event.content:
                    # Remove empty lines from tool output content
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
                                }
                            },
                            "finish_reason": None
                        }]
                    }
            
            elif event.type == "step":
                # Step event: send as tool_status
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or ""
                        },
                        "finish_reason": None
                    }]
                }
            
            elif event.type == "final":
                # Final event: send remaining content if any, then finish
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
                                "delta": {
                                    "content": cleaned_content
                                },
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
                # Error event: send as tool_status
                chunk = {
                    "id": response_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model,
                    "choices": [{
                        "index": 0,
                        "delta": {
                            "tool_status": event.content or ""
                        },
                        "finish_reason": None
                    }]
                }
            
            # Send chunk if we created one
            if chunk:
                yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
        
        # If we didn't get a final event, send finish chunk anyway
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
        logger.error(f"Error in streaming response: {e}", exc_info=True)
        # Send error chunk
        error_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_status": f"❌ 错误: {str(e)}"
                },
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/chat/completions", response_model=None)
async def chat_completions(request: ChatCompletionRequest) -> Union[Dict[str, Any], StreamingResponse]:
    """
    OpenAI-compatible chat completions endpoint
    Creates a new agent instance for each request
    Supports both streaming (SSE) and non-streaming modes
    """
    try:
        # Get session_id from request body (required)
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id is required in request body")
        session_id = request.session_id
        
        # Extract character information if provided
        character_name = "Stacy"
        roleplay_prompt = ROLEPLAY_PROMPT  # Default prompt
        character_id = None
        if request.character:
            character_name = request.character.name
            roleplay_prompt = request.character.roleplay_prompt or ROLEPLAY_PROMPT
            character_id = request.character.character_id
            
            # Upsert character to archive/working database
            # This ensures characters used in conversations are recorded in the archive
            try:
                from app.storage.archive_character_repository import ArchiveCharacterRepository
                archive_char_repo = ArchiveCharacterRepository()
                archive_char_repo.upsert_character(
                    character_id=character_id,
                    name=character_name,
                    roleplay_prompt=roleplay_prompt,
                    avatar=None,  # Request doesn't include avatar
                )
                logger.debug(f"Upserted character {character_id} to archive database")
            except Exception as e:
                # Log error but don't fail the request
                logger.warning(f"Failed to upsert character to archive database: {e}")
        
        # Extract model information if provided
        llm_settings = None
        if request.model_info:
            # Use model configuration from request
            model_info = request.model_info
            llm_settings = LLMSettings(
                model=model_info.model,
                base_url=model_info.base_url,
                api_key=model_info.api_key or "",
                max_tokens=model_info.max_tokens,
                temperature=model_info.temperature,
                api_type=model_info.api_type,
            )
            logger.info(f"Using model configuration: {model_info.name} (ID: {model_info.model_id}, Provider: {model_info.provider})")
        else:
            # Use default config from config.toml
            logger.info(f"No model_info provided, using default config from config.toml (openai)")
        
        # Extract user input directly from request
        if not request.user_input or not request.user_input.strip():
            raise HTTPException(status_code=400, detail="user_input is required and cannot be empty")
        
        user_input = request.user_input.strip()

        if not request.input_mode:
            raise HTTPException(status_code=400, detail="input_mode is required in request body")
        input_mode = request.input_mode
        
        # Extract participants (character IDs that messages should be visible to)
        participants = request.participants if hasattr(request, 'participants') else None
        
        # Create new agent instance for this request
        # LLM will be reused through its singleton mechanism
        # Memory will be automatically loaded from storage based on session_id
        agent = AgentService.create_agent(
            session_id=session_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            character_id=character_id,
            llm_settings=llm_settings,
            visible_for_characters=participants,
        )
        
        logger.info(f"Processing chat request for session {session_id}, mode={input_mode}: {user_input[:50]}... (stream={request.stream})")
        
        # Handle streaming requests
        if request.stream:
            response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
            # Use model from model_info if available, otherwise use default from config.toml
            if request.model_info:
                model = request.model_info.model
            else:
                # Use default config from config.toml
                from app.config import config
                default_config = config.llm.get("openai") or config.llm.get("default")
                if default_config:
                    model = default_config.model if hasattr(default_config, "model") else "gpt-4o"
                else:
                    model = "gpt-4o"
            
            return StreamingResponse(
                generate_streaming_response(
                    agent=agent,
                    user_input=user_input,
                    response_id=response_id,
                    model=model,
                    session_id=session_id,
                    input_mode=input_mode,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",  # Disable nginx buffering
                }
            )
        
        # Non-streaming mode: collect events and return structured response
        response_content, tool_outputs = await gather_agent_response(agent, user_input, input_mode=input_mode)
        if response_content is None:
            response_content = ""
        
        # Build response
        response_message = ChatMessage(
            role="assistant",
            content=response_content,
            tool_outputs=tool_outputs or None,
        )
        
        choice = ChatCompletionChoice(
            index=0,
            message=response_message,
            finish_reason="stop"
        )
        
        # Generate proper response fields
        response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        # Use model from model_info if available, otherwise use default from config.toml
        if request.model_info:
            model = request.model_info.model
        else:
            # Use default config from config.toml
            from app.config import config
            default_config = config.llm.get("openai") or config.llm.get("default")
            if default_config:
                model = default_config.model if hasattr(default_config, "model") else "gpt-4o"
            else:
                model = "gpt-4o"
        
        response = ChatCompletionResponse(
            id=response_id,
            created=created,
            model=model,
            choices=[choice]
        )
        
        # Add session_id to response for frontend to use
        # Convert to dict and add session_id (custom field, not in OpenAI standard)
        response_dict = response.model_dump()
        response_dict["session_id"] = session_id
        
        return response_dict
        
    except RuntimeError as e:
        error_msg = str(e)
        # Check if it's the agent state error
        if "Cannot run agent from state" in error_msg:
            logger.warning(f"Agent is busy: {error_msg}")
            raise HTTPException(
                status_code=503,
                detail=f"Agent is currently busy. Please try again later."
            )
        # Other RuntimeError (e.g., agent not initialized)
        logger.error(f"Agent error: {error_msg}")
        raise HTTPException(status_code=503, detail="Agent service not available")
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


async def generate_flow_streaming_response(
    flow,
    user_input: str,
    response_id: str,
    model: str,
    session_id: str,
    input_mode: Optional[InputMode] = None,
) -> AsyncIterator[str]:
    """
    Generate streaming SSE response from flow events.
    Converts FlowEvent to OpenAI-compatible SSE chunks.
    """
    created = int(time.time())
    
    try:
        logger.info(f"Running flow with streaming events...")
        kwargs = {}
        if input_mode:
            kwargs["input_mode"] = input_mode
        
        async for event in flow.run_stream(user_input, **kwargs):
            chunk = None
            
            if event.type == "token":
                if event.content:
                    # Remove empty lines from token content
                    cleaned_content = remove_empty_lines(event.content)
                    if not cleaned_content:
                        continue
                    delta_payload = {"content": cleaned_content}
                    # Add tool_event if message_type exists (same as agent streaming)
                    if event.message_type:
                        delta_payload["tool_event"] = {
                            "type": "tool_output",
                            "message_type": event.message_type,
                            "message_id": event.message_id,
                        }
                    # Add flow-specific metadata (optional, won't break frontend)
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
            
            elif event.type == "flow_step":
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
            
            elif event.type == "step":
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
                                "delta": {
                                    "content": cleaned_content
                                },
                                "finish_reason": None
                            }]
                        }
                        yield f"data: {json.dumps(chunk, ensure_ascii=False)}\n\n"
                
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
        
        # If we didn't get a final event, send finish chunk anyway
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
        logger.error(f"Error in flow streaming response: {e}", exc_info=True)
        error_chunk = {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {
                    "tool_status": f"❌ 错误: {str(e)}"
                },
                "finish_reason": "stop"
            }]
        }
        yield f"data: {json.dumps(error_chunk, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"


@router.post("/flow/completions", response_model=None)
async def flow_completions(request: FlowCompletionRequest) -> Union[Dict[str, Any], StreamingResponse]:
    """
    Flow-based chat completions endpoint
    Creates a flow instance for each request
    Supports both streaming (SSE) and non-streaming modes
    """
    try:
        # Get session_id from request body (required)
        if not request.session_id:
            raise HTTPException(status_code=400, detail="session_id is required in request body")
        session_id = request.session_id
        
        # Extract model information if provided
        llm_settings = None
        if request.model_info:
            model_info = request.model_info
            llm_settings = LLMSettings(
                model=model_info.model,
                base_url=model_info.base_url,
                api_key=model_info.api_key or "",
                max_tokens=model_info.max_tokens,
                temperature=model_info.temperature,
                api_type=model_info.api_type,
            )
            logger.info(f"Using model configuration: {model_info.name} (ID: {model_info.model_id}, Provider: {model_info.provider})")
        else:
            logger.info(f"No model_info provided, using default config from config.toml (openai)")
        
        # Extract character information if provided
        character_name = "character_flow"
        roleplay_prompt = None
        character_id = None
        if request.character:
            character_name = request.character.name
            roleplay_prompt = request.character.roleplay_prompt
            character_id = request.character.character_id
            
            # Upsert character to archive/working database
            # This ensures characters used in conversations are recorded in the archive
            try:
                from app.storage.archive_character_repository import ArchiveCharacterRepository
                archive_char_repo = ArchiveCharacterRepository()
                archive_char_repo.upsert_character(
                    character_id=character_id,
                    name=character_name,
                    roleplay_prompt=roleplay_prompt,
                    avatar=None,  # Request doesn't include avatar
                )
                logger.debug(f"Upserted character {character_id} to archive database")
            except Exception as e:
                # Log error but don't fail the request
                logger.warning(f"Failed to upsert character to archive database: {e}")
        
        # Extract user input
        if not request.user_input or not request.user_input.strip():
            raise HTTPException(status_code=400, detail="user_input is required and cannot be empty")
        
        user_input = request.user_input.strip()
        input_mode = request.input_mode or InputMode.PHONE
        
        # Extract participants (character IDs that messages should be visible to)
        participants = request.participants if hasattr(request, 'participants') else None
        
        # Create flow instance
        flow = FlowService.create_flow(
            flow_type=request.flow_type,
            session_id=session_id,
            name=character_name,
            roleplay_prompt=roleplay_prompt,
            llm_settings=llm_settings,
            visible_for_characters=participants,
            character_id=character_id,
        )
        
        logger.info(f"Processing flow request for session {session_id}, mode={input_mode}: {user_input[:50]}... (stream={request.stream})")
        
        # Handle streaming requests
        if request.stream:
            response_id = f"flowcmpl-{uuid.uuid4().hex[:8]}"
            if request.model_info:
                model = request.model_info.model
            else:
                from app.config import config
                default_config = config.llm.get("openai") or config.llm.get("default")
                if default_config:
                    model = default_config.model if hasattr(default_config, "model") else "gpt-4o"
                else:
                    model = "gpt-4o"
            
            return StreamingResponse(
                generate_flow_streaming_response(
                    flow=flow,
                    user_input=user_input,
                    response_id=response_id,
                    model=model,
                    session_id=session_id,
                    input_mode=input_mode,
                ),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                }
            )
        
        # Non-streaming mode: collect events and return structured response
        content_segments: List[str] = []
        async for event in flow.run_stream(user_input, input_mode=input_mode):
            if event.type == "token" and event.content:
                content_segments.append(event.content)
        
        # Join all content segments and remove empty lines for cleaner output
        raw_content = "".join(content_segments)
        response_content = remove_empty_lines(raw_content).strip()
        if response_content is None:
            response_content = ""
        
        # Build response
        response_message = ChatMessage(
            role="assistant",
            content=response_content,
        )
        
        choice = ChatCompletionChoice(
            index=0,
            message=response_message,
            finish_reason="stop"
        )
        
        response_id = f"flowcmpl-{uuid.uuid4().hex[:8]}"
        created = int(time.time())
        if request.model_info:
            model = request.model_info.model
        else:
            from app.config import config
            default_config = config.llm.get("openai") or config.llm.get("default")
            if default_config:
                model = default_config.model if hasattr(default_config, "model") else "gpt-4o"
            else:
                model = "gpt-4o"
        
        response = ChatCompletionResponse(
            id=response_id,
            created=created,
            model=model,
            choices=[choice]
        )
        
        response_dict = response.model_dump()
        response_dict["session_id"] = session_id
        
        return response_dict
        
    except RuntimeError as e:
        error_msg = str(e)
        if "Cannot run flow from state" in error_msg:
            logger.warning(f"Flow is busy: {error_msg}")
            raise HTTPException(
                status_code=503,
                detail=f"Flow is currently busy. Please try again later."
            )
        logger.error(f"Flow error: {error_msg}")
        raise HTTPException(status_code=503, detail="Flow service not available")
    except Exception as e:
        logger.error(f"Error processing flow request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

