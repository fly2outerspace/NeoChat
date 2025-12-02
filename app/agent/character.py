from typing import AsyncIterator, List, Optional, Literal

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.schema import AgentStreamEvent, Message, ToolCall
from app.memory import Memory
from app.utils.enums import MessageCategory, InputMode
from app.utils.streaming import stream_by_category
from app.utils.mapping import (
    TOOL_CATEGORY_MAP,
    CATEGORY_TO_INDICATOR_MAP,
    get_category_from_input_mode,
)
from app.prompt.character import NEXT_STEP_PROMPT, SYSTEM_PROMPT    
from app.utils import get_current_time, get_current_datetime
from app.logger import logger
from app.tool.base import ToolResult
from app.utils.enums import ToolName, MessageType

class Character(ToolCallAgent):
    """Character agent class that extends ToolCallAgent with character-specific behavior"""

    name: str = "character"
    description: str = "an agent that represents a character with personality and behavior."
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    # Character-specific attributes
    roleplay_prompt: Optional[str] = None
    tool_choices: Literal["none", "auto", "required"] = "required"


    @property
    def messages(self) -> List[Message]:
        """Retrieve messages using time-based filtering (Character-specific)"""
        return self.memory.messages
    
    def _format_messages(self, messages: List[Message]) -> str:
        """Format messages into a compressed string representation"""
        formatted_messages = []
        for msg in messages:
            # Get created_at timestamp
            if msg.category in {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}:
                indicator = CATEGORY_TO_INDICATOR_MAP.get(msg.category, "")
                msg.content = f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}"
            elif msg.category == MessageCategory.SYSTEM_INSTRUCTION:
                msg.content = f"{msg.created_at} - SYSTEM_INSTRUCTION: **[{msg.content}]**"
                msg.content += f"\nSYSTEM_INSTRUCTION must be followed strictly."
            else:
                # keep unchanged
                pass
            formatted_messages.append(msg)
        return formatted_messages

    def handle_user_input(self, request: str, **kwargs):
        current_time = get_current_time(session_id=self.session_id)
        # Get category based on input_mode from kwargs, default to PHONE
        input_mode = kwargs.get("input_mode", InputMode.PHONE)
        if input_mode != InputMode.SKIP:
            category = get_category_from_input_mode(input_mode)
            user_msg = Message.user_message(request, speaker="user", created_at=current_time, category=category, visible_for_characters=self.visible_for_characters)
            self.memory.add_message(user_msg)
        
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
        # Use underlying memory messages instead of the Memory object itself
        # to avoid yielding (field_name, value) tuples from the Pydantic model.
        # Use session-specific virtual time
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        messages, _ = Memory.get_messages_around_time(self.session_id, time_point=current_time, hours=72.0, max_messages=50, character_id=self.character_id)

        # Get today's date in YYYY-MM-DD format (using session-specific virtual time)
        current_dt = get_current_datetime(session_id=self.session_id)
        today_date = current_dt.date().strftime('%Y-%m-%d')
        schedule_entries = Memory.get_schedule_entries_by_date(self.session_id, today_date, character_id=self.character_id)
        
        # Format schedule entries
        if schedule_entries:
            schedule_text = "\n".join([
                f"schedule entry(ID:{entry.entry_id}):\n"
                f"content: {entry.content}\n"
                f"start_at: {entry.start_at}\n"
                f"end_at: {entry.end_at}"
                for entry in schedule_entries
            ])
        else:
            schedule_text = "No schedule found. Arrange your today's schedule first."
        
        aid_content = f"""current time: {current_time}\n\ntoday's schedule:\n{schedule_text}"""
        aid_message = Message.system_message(aid_content, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters)
        messages.append(aid_message)
        if self.next_step_prompt:
            next_step_msg = Message.system_message(self.next_step_prompt, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters)
            messages.append(next_step_msg)
        return self._format_messages(messages)

    async def handle_tool_result_stream(
        self, command: ToolCall, result: ToolResult
    ) -> AsyncIterator[AgentStreamEvent]:
        """Handle tool result with immediate streaming for output tools"""
        message_type = command.function.name
        
        # Store ToolResult for flow adapters to access
        self.tool_results[command.id] = result
        
        # Get text content for display
        content = str(result) or ""
        
        # Emit structured data if args exist
        if result.args:
            yield AgentStreamEvent(
                type="tool_output",
                content=None,
                message_type=message_type,
                message_id=command.id,
                step=self.current_step,
                total_steps=self.max_steps,
                metadata={
                    "structured_data": result.args,
                    "result_type": command.function.name
                }
            )
        
        # Get category from mapping, default to TOOL for character layer
        # For other tools not in the mapping, use TOOL category
        category = TOOL_CATEGORY_MAP.get(command.function.name, MessageCategory.TOOL)
        
        # For output tools (telegram/speak_in_person), stream the result with pseudo-streaming
        if category in {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON}:
            # Use category-specific streaming mode (typewriter for speak_in_person, line-by-line for telegram)
            async for chunk in stream_by_category(content, category):
                yield AgentStreamEvent(
                    type="tool_output",
                    content=chunk,
                    message_type=message_type,
                    message_id=command.id,
                    step=self.current_step,
                    total_steps=self.max_steps,
                )
            # Add tool response to memory (mark as user-facing category)
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            tool_msg = Message.tool_message(
                content=content, tool_name=command.function.name, tool_call_id=command.id, speaker=self.name, created_at=current_time, category=category,
                visible_for_characters=self.visible_for_characters
            )
            self.memory.add_message(tool_msg)
        else:
            # Normalize the result
            logger.info(
                f" Tool '{command.function.name}' completed its mission!"
            )
            
            # display reflection as inner thought here
            if command.function.name == ToolName.REFLECTION:
                message_type = MessageType.INNER_THOUGHT

            # Stream the tool output so frontend can display progress
            for chunk in self._chunk_content(content):
                yield AgentStreamEvent(
                    type="token",
                    content=chunk,
                    step=self.current_step,
                    total_steps=self.max_steps,
                    message_type=message_type,
                    message_id=command.id,
                )
            # Add tool response to memory with TOOL category
            current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
            tool_msg = Message.tool_message(
                content=content, tool_name=command.function.name, tool_call_id=command.id, speaker=self.name, created_at=current_time, category=category,
                visible_for_characters=self.visible_for_characters
            )
            self.memory.add_message(tool_msg)
