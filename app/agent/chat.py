import asyncio
import uuid
from typing import AsyncIterator, List, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.logger import logger
from app.prompt.chat import SYSTEM_PROMPT
from app.schema import ExecutionEvent, ExecutionState, Message
from app.utils import get_current_time
from app.utils.enums import MessageCategory


class ChatAgent(BaseAgent):
    """Chat agent class that extends BaseAgent with simple one-step chat behavior (no tool calls)"""

    name: str = "chat"
    description: str = "an agent that engages in simple conversations without tool calls."
    system_prompt: str = SYSTEM_PROMPT
    
    # Message type for streaming events (subclasses should override)
    message_type: str = "chat"
    
    # Chat-specific attributes
    roleplay_prompt: Optional[str] = None
    
    # Set max_steps to 1 for one-step completion
    max_steps: int = 1

    def prepare_system_messages(self) -> list[Message]:
        """Prepare system messages for the agent"""
        current_time = get_current_time(session_id=self.session_id)
        system_msgs = []
        if self.roleplay_prompt:
            system_msgs.append(Message.system_message(self.roleplay_prompt, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters))
        if self.system_prompt:
            system_msgs.append(Message.system_message(self.system_prompt, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters))
        return system_msgs

    def prepare_messages(self) -> list[Message]:
        """Prepare messages for the agent"""
        messages = []
        messages.extend(self.messages)
        return messages

    async def step_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Execute a single step with streaming events"""
        system_msgs = self.prepare_system_messages()
        messages = self.prepare_messages()
        
        # Combine system messages with regular messages (ask doesn't support system_msgs parameter)
        all_messages = system_msgs + messages if system_msgs else messages
        
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        
        # Generate unique message_id for this streaming session (similar to tool_call_id format)
        message_id = f"call_{uuid.uuid4().hex[:8]}"
        
        # Use queue to collect streaming chunks
        delta_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
        collected_content: List[str] = []
        
        async def on_delta(delta):
            """Callback to collect streaming deltas (may be str or dict)"""
            # Only collect string deltas (content chunks), ignore dict deltas (tool calls, stream_end, etc.)
            if isinstance(delta, str):
                await delta_queue.put(delta)
        
        async def call_llm():
            """Call LLM and signal completion"""
            try:
                response = await self.llm.ask(
                    messages=all_messages,
                    stream=True,
                    on_delta=on_delta,
                )
                await delta_queue.put(None)  # Signal completion
                return response
            except Exception as e:
                await delta_queue.put(None)  # Signal completion even on error
                raise e
        
        # Start LLM call in background
        llm_task = asyncio.create_task(call_llm())
        
        # Stream chunks as they arrive
        while True:
            delta = await delta_queue.get()
            if delta is None:  # Completion signal
                break
            collected_content.append(delta)
            yield ExecutionEvent(
                type="token",
                content=delta,
                step=self.current_step,
                total_steps=self.max_steps,
                message_type=self.message_type,
                message_id=message_id,
            )
        
        # Get final response
        llm_error = None
        try:
            full_response = await llm_task
            if not full_response:
                full_response = "".join(collected_content)
        except Exception as e:
            logger.error(f"Error: The {self.name}'s LLM call hit a snag: {e}")
            llm_error = e
            full_response = "".join(collected_content)
        
        # Log response info (similar to ToolCallAgent style)
        logger.info(f" {self.name}'s ask response: {full_response}")
        
        # Add complete assistant message to memory and set state
        if full_response and full_response.strip():
            # Valid response received
            self.add_assistant_message(full_response, current_time)
            self.result = full_response
            # Mark as finished after one step
            self.state = ExecutionState.FINISHED
        else:
            # No valid response received - mark as error to prevent stuck state
            error_msg = "错误: 未收到有效响应"
            if llm_error:
                error_msg = f"错误: LLM 调用失败 - {str(llm_error)}"
            else:
                logger.warning(f" {self.name} received empty response from LLM (streaming)")
            
            self.result = ""
            self.state = ExecutionState.ERROR
            # Emit error event for frontend
            yield ExecutionEvent(
                type="error",
                content=error_msg,
                step=self.current_step,
                total_steps=self.max_steps,
                message_type=self.message_type,
            )
    
    def add_assistant_message(self, content: str, created_at: Optional[str] = None) -> None:
        """Add assistant message to memory.
        
        Subclasses can override this method to customize message creation,
        e.g., setting specific category for different message types.
        
        Args:
            content: Message content
            created_at: Optional timestamp. If None, uses current time.
        """
        if created_at is None:
            created_at = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        assistant_msg = Message.assistant_message(
            content, 
            speaker=self.name, 
            created_at=created_at,
            visible_for_characters=self.visible_for_characters
        )
        self.memory.add_message(assistant_msg)

