"""ChatParallelFlow: Parallel flow with WriterAgent in background and CharacterFlow in response

This flow runs WriterAgent (silent strategy agent) in the background while CharacterFlow handles the main response.
WriterAgent executes silently without streaming output, perfect for background tasks.
"""

from typing import List, Optional

from app.agent.writer import WriterAgent
from app.flow.base import FlowNode
from app.flow.character_flow import CharacterFlow
from app.flow.parallel_flow import ParallelFlow
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
    Strategy,
    Terminate,
    ToolCollection,
    WebSearch,
)


class ChatParallelFlow(ParallelFlow):
    """ChatParallelFlow: Parallel flow with WriterAgent in background
    
    Flow structure:
    1. Background: WriterAgent (runs silently in background, no streaming output)
    2. Response: CharacterFlow (handles main conversation flow with streaming)
    
    WriterAgent executes tools silently without emitting events to the HTTP response stream.
    """
    
    name: str = "chat_parallel_flow"
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
        """Build the flow nodes for ChatParallelFlow"""
        
        def create_background_writer_agent(ctx: ExecutionContext) -> Runnable:
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
        
        def writer_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for background writer agent input"""
            return ctx.merge(
                request=ctx.user_input or "",
                input_mode=ctx.data.get("input_mode"),
            )
        
        def character_flow_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for character flow input"""
            return ctx.merge(
                request=ctx.user_input or "",
                input_mode=ctx.data.get("input_mode"),
            )
        
        return [
            FlowNode(
                id="background_writer",
                name="background_writer",
                runnable_factory=create_background_writer_agent,
                input_adapter=writer_input_adapter,
                is_background=True,  # Run in background
            ),
            FlowNode(
                id="character_flow",
                name="character_flow",
                runnable_factory=create_character_flow,
                input_adapter=character_flow_input_adapter,
                is_background=False,  # Run in response stream
            ),
        ]
    
    def __init__(self, **data):
        """Initialize ChatParallelFlow and build nodes"""
        super().__init__(**data)
        self._initialize_llms()
        self.nodes = self.build_nodes()
        logger.info(f" {self.name} flow initialized with {len(self.nodes)} nodes")

