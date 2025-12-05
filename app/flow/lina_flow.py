"""LinaFlow: Sequential flow with UserAgent followed by parallel execution

Flow: UserAgent → (WriterAgent [background] + CharacterFlow [response])

This flow combines:
1. UserAgent: Processes user input (with COMMAND skip logic)
2. Parallel execution:
   - WriterAgent: Runs silently in background
   - CharacterFlow: Handles main conversation with streaming
"""
import uuid
from typing import List, Optional

from app.agent.user import UserAgent
from app.agent.writer import WriterAgent
from app.flow.base import FlowNode
from app.flow.character_flow import CharacterFlow
from app.flow.parallel_flow import ParallelFlow
from app.flow.sequential_flow import SequentialFlow
from app.llm import LLM
from app.logger import logger
from app.memory import Memory
from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.tool import (
    DialogueHistory,
    Reflection,
    RelationTool,
    ScenarioReader,
    ScenarioWriter,
    ScheduleReader,
    ScheduleWriter,
    Terminate,
    ToolCollection,
    WebSearch,
)


class _InnerParallelFlow(ParallelFlow):
    """Inner parallel flow for LinaFlow
    
    Runs WriterAgent in background and CharacterFlow in response stream.
    """
    
    name: str = "lina_parallel"
    roleplay_prompt: str = ""
    
    # LLM instances (set by parent LinaFlow)
    chat_llm: Optional[LLM] = None
    infer_llm: Optional[LLM] = None
    
    def build_nodes(self) -> List[FlowNode]:
        """Build parallel nodes: WriterAgent (background) + CharacterFlow (response)"""
        
        def create_writer_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for background writer agent"""
            memory = Memory(session_id=ctx.session_id)
            return WriterAgent(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.infer_llm,
                memory=memory,
                available_tools=ToolCollection(
                    Reflection(),
                    Terminate(),
                    WebSearch(),
                    DialogueHistory(session_id=ctx.session_id, character_id=self.character_id),
                    ScheduleReader(session_id=ctx.session_id, character_id=self.character_id),
                    ScheduleWriter(session_id=ctx.session_id, character_id=self.character_id),
                    ScenarioReader(session_id=ctx.session_id, character_id=self.character_id),
                    ScenarioWriter(session_id=ctx.session_id, character_id=self.character_id),
                    RelationTool(session_id=ctx.session_id, character_id=self.character_id),
                ),
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def create_character_flow(ctx: ExecutionContext) -> Runnable:
            """Factory function for character flow"""
            return CharacterFlow(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                chat_llm=self.chat_llm,
                infer_llm=self.infer_llm,
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def passthrough_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Pass through context unchanged"""
            return ctx
        
        return [
            FlowNode(
                id="background_writer",
                name="background_writer",
                runnable_factory=create_writer_agent,
                input_adapter=passthrough_adapter,
                is_background=True,  # Run in background
            ),
            FlowNode(
                id="character_flow",
                name="character_flow",
                runnable_factory=create_character_flow,
                input_adapter=passthrough_adapter,
                is_background=False,  # Run in response stream
            ),
        ]
    
    def __init__(self, **data):
        """Initialize inner parallel flow"""
        if "id" not in data:
            data["id"] = f"lina-parallel-{uuid.uuid4().hex[:8]}"
        super().__init__(**data)
        self.nodes = self.build_nodes()


class LinaFlow(SequentialFlow):
    """LinaFlow: UserAgent → Parallel(WriterAgent + CharacterFlow)
    
    Flow structure:
    1. UserAgent: Processes and stores user input to memory
       - If input_mode is COMMAND, skip to end (no further processing)
    2. Parallel execution (if not skipped):
       - WriterAgent: Background task for reflection/writing
       - CharacterFlow: Main conversation flow with streaming
    
    This design:
    - Separates user input processing from response generation
    - Runs background tasks without blocking the response stream
    - Supports COMMAND input mode to skip agent processing
    """
    
    name: str = "lina"
    roleplay_prompt: str = ""
    
    # LLM instances
    chat_llm: Optional[LLM] = None
    infer_llm: Optional[LLM] = None
    
    def _initialize_llms(self):
        """Initialize default LLM instances if not provided"""
        if self.chat_llm is None:
            self.chat_llm = LLM(config_name="openai")
        if self.infer_llm is None:
            self.infer_llm = LLM(config_name="openai")
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes for LinaFlow"""
        
        # ==================== UserAgent ====================
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
        
        def user_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Pass through context with user input for UserAgent"""
            return ctx
        
        def user_output_adapter(runnable: Runnable, ctx: ExecutionContext) -> Optional[ExecutionContext]:
            """Extract skip_next_node flag from UserAgent and update context"""
            skip_next_node = getattr(runnable, 'skip_next_node', False)
            if skip_next_node:
                logger.info(f" {self.name} UserAgent set skip_next_node=True, will skip parallel execution")
            return ctx.merge(skip_next_node=skip_next_node)
        
        def select_next_after_user(ctx: ExecutionContext) -> Optional[str]:
            """Select next node based on skip_next_node flag
            
            If input_mode was COMMAND, skip parallel execution and end flow.
            Otherwise, proceed to parallel node.
            """
            if ctx.data.get("skip_next_node", False):
                logger.info(f" {self.name} skipping parallel node due to COMMAND input")
                return None  # End flow
            return "parallel"  # Proceed to parallel execution
        
        # ==================== Parallel Execution ====================
        def create_parallel_flow(ctx: ExecutionContext) -> Runnable:
            """Factory function for inner parallel flow or just CharacterFlow
            
            WriterAgent is triggered every 5 dialogue turns (speaker's messages with category 1 or 2).
            """
            # Count dialogue messages for this character
            dialogue_count = Memory.count_dialogue_messages(
                session_id=ctx.session_id,
                speaker=self.name,
            )
            
            # Trigger WriterAgent every 5 dialogue turns
            should_run_writer = dialogue_count > 0 and dialogue_count % 5 == 0
            
            if should_run_writer:
                logger.info(f" {self.name} dialogue count={dialogue_count}, triggering WriterAgent")
                return _InnerParallelFlow(
                    session_id=ctx.session_id,
                    name=self.name,
                    roleplay_prompt=self.roleplay_prompt,
                    character_id=self.character_id,
                    chat_llm=self.chat_llm,
                    infer_llm=self.infer_llm,
                    visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
                )
            else:
                logger.info(f" {self.name} dialogue count={dialogue_count}, skipping WriterAgent")
                # Just return CharacterFlow without WriterAgent
                return CharacterFlow(
                    session_id=ctx.session_id,
                    name=self.name,
                    roleplay_prompt=self.roleplay_prompt,
                    character_id=self.character_id,
                    chat_llm=self.chat_llm,
                    infer_llm=self.infer_llm,
                    visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
                )
        
        def parallel_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for parallel execution - clear user_input to avoid duplicate storage"""
            # User input already processed by UserAgent, clear it
            return ctx.merge(user_input=None)
        
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
                id="parallel",
                name="parallel_execution",
                runnable_factory=create_parallel_flow,
                input_adapter=parallel_input_adapter,
                # No next_node_selector - this is the terminal node
            ),
        ]
    
    def __init__(self, **data):
        """Initialize LinaFlow and build nodes"""
        if "id" not in data:
            data["id"] = f"lina-{uuid.uuid4().hex[:8]}"
        super().__init__(**data)
        self._initialize_llms()
        self.nodes = self.build_nodes()
        logger.info(f" {self.name} flow initialized with {len(self.nodes)} nodes")

