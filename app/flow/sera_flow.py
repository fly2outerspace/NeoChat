"""SeraFlow: Simple sequential flow with UserAgent and Character

A streamlined flow that separates user input processing from character response generation.
Flow: UserAgent (process input) → Character (generate response)
"""
import uuid
from typing import List, Optional

from app.agent.character import Character
from app.agent.user import UserAgent
from app.flow.base import FlowNode
from app.flow.sequential_flow import SequentialFlow
from app.llm import LLM
from app.logger import logger
from app.memory import Memory
from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.tool import (
    Reflection,
    RelationTool,
    ScenarioReader,
    ScenarioWriter,
    ScheduleReader,
    ScheduleWriter,
    SendTelegramMessage,
    SpeakInPerson,
    Terminate,
    ToolCollection,
)


class SeraFlow(SequentialFlow):
    """SeraFlow: A simple sequential flow for character conversations
    
    Flow structure:
    1. UserAgent: Processes and stores user input to memory
    2. Character: Generates response based on conversation context
    
    This design separates concerns:
    - UserAgent handles input categorization and storage
    - Character focuses purely on response generation
    """
    
    name: str = "sera"
    roleplay_prompt: str = ""
    
    # LLM instance for Character agent
    llm: Optional[LLM] = None
    
    def _initialize_llm(self):
        """Initialize default LLM instance if not provided"""
        if self.llm is None:
            self.llm = LLM(config_name="openai")
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes for SeraFlow"""
        
        def create_user_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for user agent"""
            memory = Memory(session_id=ctx.session_id)
            return UserAgent(
                session_id=ctx.session_id,
                name="user",
                character_id=self.character_id,
                memory=memory,
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def create_character_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for character agent"""
            memory = Memory(session_id=ctx.session_id)
            return Character(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.llm,
                memory=memory,
                available_tools=ToolCollection(
                    SpeakInPerson(),
                    SendTelegramMessage(),
                    Terminate(),
                    Reflection(session_id=ctx.session_id, character_id=self.character_id),
                    ScheduleReader(session_id=ctx.session_id, character_id=self.character_id),
                    ScheduleWriter(session_id=ctx.session_id, character_id=self.character_id),
                    ScenarioReader(session_id=ctx.session_id, character_id=self.character_id),
                    ScenarioWriter(session_id=ctx.session_id, character_id=self.character_id),
                    RelationTool(session_id=ctx.session_id, character_id=self.character_id),
                ),
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def user_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Pass through context with user input for UserAgent"""
            return ctx
        
        def character_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for character agent - no user_input to avoid duplicate storage"""
            # Clear user_input since UserAgent already processed it
            return ctx.merge(user_input=None)
        
        def user_output_adapter(runnable: Runnable, ctx: ExecutionContext) -> Optional[ExecutionContext]:
            """Extract skip_next_node flag from UserAgent and update context"""
            skip_next_node = getattr(runnable, 'skip_next_node', False)
            if skip_next_node:
                logger.info(f" {self.name} UserAgent set skip_next_node=True, will skip character")
            return ctx.merge(skip_next_node=skip_next_node)
        
        def select_next_after_user(ctx: ExecutionContext) -> Optional[str]:
            """Select next node based on skip_next_node flag
            
            If input_mode was COMMAND, skip character agent and end flow.
            Otherwise, proceed to character agent.
            """
            if ctx.data.get("skip_next_node", False):
                logger.info(f" {self.name} skipping character node due to COMMAND input")
                return None  # End flow
            return "character"  # Proceed to character
        
        return [
            FlowNode(
                id="user",
                name="user_input",
                runnable_factory=create_user_agent,
                input_adapter=user_input_adapter,
                output_adapter=user_output_adapter,
                next_node_selector=select_next_after_user,
            ),
            FlowNode(
                id="character",
                name="character_response",
                runnable_factory=create_character_agent,
                input_adapter=character_input_adapter,
                # No next_node_selector - this is the terminal node
            ),
        ]
    
    def __init__(self, **data):
        """Initialize SeraFlow and build nodes"""
        if "id" not in data:
            data["id"] = f"sera-{uuid.uuid4().hex[:8]}"
        super().__init__(**data)
        self._initialize_llm()
        self.nodes = self.build_nodes()
        logger.info(f" {self.name} flow initialized with {len(self.nodes)} nodes")

