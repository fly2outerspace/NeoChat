from typing import List, Optional

from pydantic import Field

from app.agent.chat import ChatAgent
from app.runnable.context import ExecutionContext
from app.schema import Message
from app.utils.enums import ToolName
from app.utils.enums import MessageCategory
from app.utils.mapping import CATEGORY_TO_INDICATOR_MAP
from app.prompt.telegram import SYSTEM_PROMPT, ROLEPLAY_PROMPT
from app.memory import Memory
from app.utils import get_current_time
from app.storage.scenario_store import ScenarioStore
from app.prompt.telegram import HELPER_PROMPT

class TelegramAgent(ChatAgent):
    """Telegram agent class that extends ChatAgent with Telegram-specific prompts"""

    name: str = "telegram"
    description: str = "an agent that communicates through Telegram messages."
    system_prompt: str = SYSTEM_PROMPT
    
    # Message type for streaming events
    message_type: str = ToolName.SEND_TELEGRAM_MESSAGE
    
    # Telegram-specific attributes
    inner_thought: Optional[str] = Field(default="", description="Internal thought for Speak agent")

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

    def handle_user_input(self, context: ExecutionContext):
        """Handle user input from ExecutionContext"""
        strategy = context.data.get("strategy", "")
        self.inner_thought = strategy
        
    def add_assistant_message(self, content: str, created_at: Optional[str] = None) -> None:
        """Add assistant message with TELEGRAM category"""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        assistant_msg = Message.assistant_message(
            content, 
            speaker=self.name, 
            created_at=created_at,
            category=MessageCategory.TELEGRAM,
            visible_for_characters=self.visible_for_characters
        )
        self.memory.add_message(assistant_msg)

    def _format_messages(self, messages: List[Message]) -> List[Message]:
        """Format messages for telegram agent
        
        - System messages: kept unchanged
        - Assistant/tool messages (category 1,2,3): converted to assistant with formatted content
        - User messages: kept unchanged
        
        Args:
            messages: List of messages to format
            
        Returns:
            Formatted message list
        """
        formatted_messages = []
        # Categories to process: TELEGRAM(1), SPEAK_IN_PERSON(2), THOUGHT(3)
        target_categories = {MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON, MessageCategory.THOUGHT}
        
        for msg in messages:
            indicator = CATEGORY_TO_INDICATOR_MAP.get(msg.category, "")
            if msg.role in {"assistant", "tool"}:
                if msg.category in target_categories:
                    # Convert assistant or tool message to assistant message with formatted content
                    if msg.speaker != self.name: #TODO: 后续需要用character_id来过滤而不是speaker
                        formatted_msg = Message.user_message(
                            content=f"{msg.created_at} - {indicator} - {msg.speaker}: {msg.content}",
                            speaker=msg.speaker,
                            created_at=msg.created_at,
                            category=msg.category,
                            visible_for_characters=self.visible_for_characters
                        )                        
                    else:
                        formatted_msg = Message.assistant_message(
                            content=msg.content,
                            speaker=msg.speaker,
                            created_at=msg.created_at,
                            category=msg.category,
                            visible_for_characters=self.visible_for_characters
                        )
                    formatted_messages.append(formatted_msg)
            elif msg.role == "user":
                # format user message content
                if msg.category in target_categories:
                    
                    formatted_content = f"{msg.created_at} - {indicator}: {msg.content}"
                elif msg.category == MessageCategory.SYSTEM_INSTRUCTION:
                    formatted_content = f"{msg.created_at} - SYSTEM_INSTRUCTION:\n {msg.content}"
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
                formatted_messages.append(user_msg)
            else:
                formatted_messages.append(msg) # keep unchanged
        return formatted_messages

    def prepare_messages(self) -> list[Message]:
        """Prepare messages for the agent"""
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        messages, _ = Memory.get_messages_around_time(self.session_id, time_point=current_time, max_messages=100, character_id=self.character_id)
        messages = self._format_messages(messages)
        aid_content = f"""**current time**: {current_time}\n**Your Current Inner Thought:** [{self.inner_thought or "None"}] Perform as your thought but never print it out.\n{HELPER_PROMPT}"""
        aid_message = Message.system_message(aid_content, speaker=self.name, created_at=current_time, visible_for_characters=self.visible_for_characters)
        messages.append(aid_message)
        return messages