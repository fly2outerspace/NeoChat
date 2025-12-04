from typing import List, Optional, Literal, AsyncIterator

from pydantic import Field

from app.agent.toolcall import ToolCallAgent
from app.logger import logger
from app.memory import Memory
from app.prompt.strategy import NEXT_STEP_PROMPT, SYSTEM_PROMPT
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionEventType, Message, ToolCall
from app.storage.scenario_store import ScenarioStore
from app.tool import Terminate, Strategy, ToolCollection, ToolResult, RelationTool
from app.utils import get_current_time, get_current_datetime
from app.utils.enums import InputMode, MessageCategory, MessageType, ToolName
from app.utils.mapping import get_category_from_input_mode, CATEGORY_TO_INDICATOR_MAP, TOOL_CATEGORY_MAP
from app.utils.streaming import stream_by_category

class StrategyAgent(ToolCallAgent):
    """Strategy agent class that extends ToolCallAgent with strategic planning behavior"""

    name: str = "strategy"
    description: str = "an agent that focuses on strategic planning and long-term decision-making."
    system_prompt: str = SYSTEM_PROMPT
    next_step_prompt: str = NEXT_STEP_PROMPT
    
    available_tools: ToolCollection = Field(
        default_factory=lambda: ToolCollection(
            Terminate(), Strategy()
        )
    )

    tool_choices: Literal["none", "auto", "required"] = "required"
    
    roleplay_prompt: Optional[str] = None
    history_messages: List[Message] = Field(default_factory=list)
    special_tool_names: List[str] = Field(default_factory=lambda: [ToolName.TERMINATE, ToolName.STRATEGY])


    # Note: This agent's messages don't include historical tool messages, so messages from user onwards in this execution won't be formatted. It's better to format user messages separately.
    def _format_messages(self, messages: List[Message]) -> List[Message]:
        """Format messages for strategy agent
        Filter messages with tool calls into a clean assistant-user dialogue list
        - System messages: kept unchanged
        - Assistant/tool messages (category 1,2,3): converted to assistant with formatted content
        - User messages: formatted with timestamp, indicator, and speaker
        Format: {created_at} - {indicator} - {speaker}: {content}
        
        Args:
            messages: List of messages to format
            
        Returns:
            Formatted message list
        """
        formatted_messages = []
        # Categories to process: TELEGRAM(1), SPEAK_IN_PERSON(2), THOUGHT(3)
        target_categories = {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}
        
        for msg in messages:
            if msg.role == "system":
                formatted_messages.append(msg)
            elif msg.role in {"assistant", "tool"}:
                if msg.category in target_categories:
                    # Convert assistant or tool message to assistant message with formatted content
                    indicator = CATEGORY_TO_INDICATOR_MAP.get(msg.category, "")
                    formatted_content = f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}"
                    if msg.speaker != self.name: # TODO: Should use character_id for filtering instead of speaker in the future
                        formatted_msg = Message.user_message(
                            content=formatted_content,
                            speaker=msg.speaker,
                            created_at=msg.created_at,
                            category=msg.category,
                            visible_for_characters=self.visible_for_characters
                        )
                    else:
                        formatted_msg = Message.assistant_message(
                            content=formatted_content,
                            speaker=msg.speaker,
                            created_at=msg.created_at,
                            category=msg.category,
                            visible_for_characters=self.visible_for_characters
                        )
                    formatted_messages.append(formatted_msg)
            
        return formatted_messages

    def format_user_messages(self, messages: List[Message]) -> List[Message]:
        for i, msg in enumerate(messages):
            if msg.role == "user":
                # format user message content
                if msg.category in {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}:
                    indicator = CATEGORY_TO_INDICATOR_MAP.get(msg.category, "")
                    formatted_content = f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}"
                elif msg.category == MessageCategory.SYSTEM_INSTRUCTION:
                    formatted_content = f"{msg.created_at} - SYSTEM_INSTRUCTION: **[{msg.content}]**"
                    formatted_content += f"\nSYSTEM_INSTRUCTION must be followed strictly."
                else:
                    formatted_content = msg.content

                user_msg = Message.user_message(
                    content=formatted_content,
                    speaker=msg.speaker,
                    created_at=msg.created_at,
                    category=msg.category,
                    visible_for_characters=self.visible_for_characters
                )
                messages[i] = user_msg
        return messages

    def handle_user_input(self, context: ExecutionContext):
        """Handle user input from ExecutionContext"""
        request = context.user_input
        
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        self.history_messages, _ = Memory.get_messages_around_time(self.session_id, time_point=current_time, hours=24.0, max_messages=150, character_id=self.character_id)

        if "input_mode" not in context.data:
            logger.warning(f" {self.name} input_mode not found in context.data, using default input_mode: {InputMode.PHONE}")
            input_mode = InputMode.PHONE
        else:
            input_mode = context.data.get("input_mode")
        if input_mode != InputMode.SKIP and request:
            category = get_category_from_input_mode(input_mode)
            user_msg = Message.user_message(request, speaker="user", created_at=current_time, category=category, visible_for_characters=self.visible_for_characters)
            self.memory.add_message(user_msg)

    def prepare_system_messages(self) -> list[Message]:
        """Prepare system messages for the agent"""
        current_time = get_current_time(session_id=self.session_id)
        long_term_memory, relationship = self.prepare_memory_content()
        logger.info(f"{self.name}'s long_term_memory: \n{long_term_memory}")
        logger.info(f"{self.name}'s relationship: \n{relationship}")
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
        
    def prepare_aid_messages(self) -> list[Message]:
        current_time = get_current_time(session_id=self.session_id)
        time_content = f"Current time: {current_time}"
        aid_message = Message.system_message(
            time_content,
            speaker=self.name,
            created_at=current_time,
            visible_for_characters=self.visible_for_characters,
        )
        return [aid_message]

    def prepare_messages(self) -> list[Message]:
        """Prepare messages for the agent"""
        messages = self._format_messages(self.history_messages)
        messages.extend(self.messages)
        current_time = get_current_time(session_id=self.session_id)
        aid_message = self.prepare_aid_messages()
        messages.extend(aid_message)

        if self.next_step_prompt:
            next_step_msg = Message.system_message(self.next_step_prompt, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters)
            messages.append(next_step_msg)
        messages = self.format_user_messages(messages)
        return messages

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
 
        # Normalize the result
        logger.info(
            f" Tool '{command.function.name}' completed its mission!"
        )
        
        # display strategy as inner thought here
        if command.function.name == ToolName.STRATEGY:
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
