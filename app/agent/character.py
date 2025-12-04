from typing import AsyncIterator, List, Optional, Literal

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionEventType, Message, ToolCall
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
from app.storage.scenario_store import ScenarioStore

class Character(ToolCallAgent):
    """Character agent class that extends ToolCallAgent with character-specific behavior"""

    name: str = "character"
    description: str = "an agent that represents a character with personality and behavior."
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    # Character-specific attributes
    roleplay_prompt: Optional[str] = None
    tool_choices: Literal["none", "auto", "required"] = "required"
    special_tool_names: List[str] = Field(default_factory=lambda: [ToolName.TERMINATE, ToolName.SPEAK_IN_PERSON, ToolName.SEND_TELEGRAM_MESSAGE])

    @property
    def messages(self) -> List[Message]:
        """Retrieve messages using time-based filtering (Character-specific)"""
        return self.memory.messages
    
    def _format_messages(self, messages: List[Message]) -> str:
        """Format messages into a compressed string representation"""
        formatted_messages = []
        for msg in messages:
            # Get created_at timestamp
            indicator = CATEGORY_TO_INDICATOR_MAP.get(msg.category, "")

            # 过滤所有非本人消息
            if msg.speaker != self.name:
                # 首先处理user指令消息
                if msg.category == MessageCategory.SYSTEM_INSTRUCTION:
                    formatted_msg = Message.user_message(
                        content=f"{msg.created_at} - SYSTEM_INSTRUCTION: **[{msg.content}]**\nSYSTEM_INSTRUCTION must be followed strictly.",
                        speaker=msg.speaker,
                        created_at=msg.created_at,
                        category=msg.category,
                        visible_for_characters=self.visible_for_characters
                    )
                    formatted_messages.append(formatted_msg)
                # 将其他人的受标注过的tool消息转为user消息
                elif msg.category in {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}:
                    formatted_msg = Message.user_message(
                        content=f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}",
                        speaker=msg.speaker,
                        created_at=msg.created_at,
                        category=msg.category,
                        visible_for_characters=self.visible_for_characters
                    )
                    formatted_messages.append(formatted_msg)
                # 其他的他人消息非法，直接忽略
            else:
                # 对于本人消息，格式化并保持不变
                if msg.category in {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}:
                    msg.content = f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}"
                formatted_messages.append(msg)
        return formatted_messages

    def handle_user_input(self, context: ExecutionContext):
        """Handle user input from ExecutionContext"""
        request = context.user_input
        if not request:
            return
        current_time = get_current_time(session_id=self.session_id)
        # Get category based on input_mode from context.data, default to PHONE
        input_mode = context.data.get("input_mode", InputMode.PHONE)
        if input_mode != InputMode.SKIP:
            category = get_category_from_input_mode(input_mode)
            user_msg = Message.user_message(request, speaker="user", created_at=current_time, category=category, visible_for_characters=self.visible_for_characters)
            self.memory.add_message(user_msg)
        
    def prepare_system_messages(self) -> list[Message]:
        """Prepare system messages for the agent"""
        current_time = get_current_time(session_id=self.session_id)
        long_term_memory, relationship = self.prepare_memory_content()
        system_prompt = self.system_prompt.format(
            roleplay_prompt=self.roleplay_prompt,
            long_term_memory=long_term_memory, 
            relationship=relationship
        )
        system_msg = Message.system_message(system_prompt, speaker=self.name, created_at=current_time, visible_for_characters=[self.character_id])
        return [system_msg]

    def prepare_memory_content(self) -> tuple[str, str]:
        """Prepare memory content for strategy agent.
        
        1) One message: Display all schedules and scenarios (including future plans) for the current session, sorted by start_at.
           Format: One line per item: [start_at ~ end_at] schedule content or scenario title.
        2) One message: Display all relationship entries for the current session.
        """
        # 1) Overview of all schedules + scenarios, sorted by start time
        schedule_entries = Memory.get_schedule_entries(self.session_id, character_id=self.character_id)
        
        scenario_store = ScenarioStore()
        if self.session_id:
            scenario_store.set_session(self.session_id)
        scenarios = scenario_store.list_scenarios(self.session_id, character_id=self.character_id)
        
        combined_items = []
        # Collect schedules
        for entry in schedule_entries:
            combined_items.append(
                {
                    "start_at": entry.start_at,
                    "end_at": entry.end_at,
                    "text": entry.content + f"(ID:{entry.entry_id})" or "",
                }
            )

        # Collect scenarios (prefer title, fallback to content if missing)
        for sc in scenarios:
            combined_items.append(
                {
                    "start_at": sc.start_at,
                    "end_at": sc.end_at,
                    "text": (getattr(sc, "title", "") or sc.content or "") + f"(ID:{sc.scenario_id})",
                }
            )

        combined_items.sort(key=lambda x: x["start_at"])

        if combined_items:
            lines = [
                f"[{item['start_at']} ~ {item['end_at']}] {item['text']}"
                for item in combined_items
            ]
            overview_text = "\n".join(lines)
            schedule_scenario_content = (
                "Schedule and scenario overview sorted by start time:\n" + overview_text
            )
        else:
            schedule_scenario_content = "No schedule or scenario records found."

        # 2) Overview of all relationships
        relations = Memory.get_relations(self.session_id, character_id=self.character_id)
        if relations:
            relation_lines = []
            for rel in relations:
                relation_lines.append(
                    "------\n"
                    f"relation_id: {rel.relation_id}\n"
                    f"name: {rel.name}\n"
                    f"knowledge: {rel.knowledge}\n"
                    f"progress: {rel.progress}"
                )
            relations_text = "\n".join(relation_lines)
            relations_content = "Currently recorded relationships:\n" + relations_text
        else:
            relations_content = "No relationship records found."

        return schedule_scenario_content, relations_content

    def prepare_messages(self) -> list[Message]:
        # Use underlying memory messages instead of the Memory object itself
        # to avoid yielding (field_name, value) tuples from the Pydantic model.
        # Use session-specific virtual time
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        messages, _ = Memory.get_messages_around_time(self.session_id, time_point=current_time, hours=72.0, max_messages=100, character_id=self.character_id)

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
    ) -> AsyncIterator[ExecutionEvent]:
        """Handle tool result with immediate streaming for output tools"""
        message_type = command.function.name
        
        # Store ToolResult for flow adapters to access
        self.tool_results[command.id] = result
        
        # Get text content for display
        content = str(result) or ""
        
        # Emit structured data if args exist
        if result.args:
            yield ExecutionEvent(
                type=ExecutionEventType.TOKEN,
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
                yield ExecutionEvent(
                    type=ExecutionEventType.TOKEN,
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
                yield ExecutionEvent(
                    type=ExecutionEventType.TOKEN,
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
