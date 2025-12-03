"""CharacterFlow: Flow with StrategyAgent, SpeakAgent, and TelegramAgent"""
import uuid
from typing import Any, Dict, List, Optional

from app.agent.base import BaseAgent
from app.agent.speak import SpeakAgent
from app.agent.strategy import StrategyAgent
from app.agent.telegram import TelegramAgent
from app.flow.base import FlowNode
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
    SendTelegramMessage,
    SpeakInPerson,
    Strategy,
    Terminate,
    ToolCollection,
    WebSearch,
)


class CharacterFlow(SequentialFlow):
    """CharacterFlow: A flow with sequential agents
    
    Flow structure:
    1. StrategyAgent: Makes strategic decisions about communication channel
    2. SpeakAgent or TelegramAgent: Executes the conversation based on strategy
    """
    
    name: str = "character_flow"
    roleplay_prompt: str = ""
    
    # LLM instances
    chat_llm: Optional[LLM] = None
    strategy_llm: Optional[LLM] = None
    
    def _initialize_llms(self):
        """Initialize default LLM instances if not provided"""
        if self.chat_llm is None:
            self.chat_llm = LLM(config_name="openai")
        if self.strategy_llm is None:
            self.strategy_llm = LLM(config_name="openai")
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes for CharacterFlow"""
        
        def create_strategy_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for strategy agent"""
            memory = Memory(session_id=ctx.session_id)
            return StrategyAgent(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.strategy_llm,
                memory=memory,
                available_tools=ToolCollection(
                    Strategy(),
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
        
        def create_speak_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for speak agent"""
            memory = Memory(session_id=ctx.session_id)
            return SpeakAgent(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.chat_llm,
                memory=memory,
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def create_telegram_agent(ctx: ExecutionContext) -> Runnable:
            """Factory function for telegram agent"""
            memory = Memory(session_id=ctx.session_id)
            return TelegramAgent(
                session_id=ctx.session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.chat_llm,
                memory=memory,
                visible_for_characters=ctx.visible_for_characters or self.visible_for_characters,
            )
        
        def strategy_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for strategy agent input"""
            return ctx.merge(
                request=ctx.user_input or "",
                input_mode=ctx.data.get("input_mode"),
            )
        
        def strategy_output_adapter(runnable: Runnable, ctx: ExecutionContext) -> Dict[str, Any]:
            """Extract strategy output and update context"""
            decision = None
            strategy = ""
            
            if hasattr(runnable, 'tool_results') and runnable.tool_results:
                for tool_call_id, tool_result in runnable.tool_results.items():
                    if tool_result.args and "decision" in tool_result.args:
                        decision = tool_result.args.get("decision")
                        strategy = tool_result.args.get("strategy", "")
                        break
            
            if decision is None or not decision:
                logger.warning(f" {self.name} strategy agent did not provide valid decision")
                return {}
            
            return {"decision": decision, "strategy": strategy}
        
        def speak_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for speak agent input"""
            return ctx.merge(
                request=ctx.user_input or "",
                strategy=ctx.data.get("strategy", ""),
            )
        
        def telegram_input_adapter(ctx: ExecutionContext) -> ExecutionContext:
            """Transform context for telegram agent input"""
            return ctx.merge(
                request=ctx.user_input or "",
                strategy=ctx.data.get("strategy", ""),
            )
        
        def select_next_node(ctx: ExecutionContext) -> Optional[str]:
            """Select next node based on strategy decision"""
            decision = ctx.data.get("decision")
            
            if decision is None or not decision:
                logger.info(f" {self.name} no strategy decision, ending flow")
                return None
            
            decision = str(decision).lower()
            if decision == "speakinperson":
                logger.info(f" {self.name} routing to: speak")
                return "speak"
            elif decision == "telegram":
                logger.info(f" {self.name} routing to: telegram")
                return "telegram"
            else:
                logger.warning(f" {self.name} invalid decision: {decision}, ending flow")
                return None
        
        return [
            FlowNode(
                id="strategy",
                name="strategy",
                runnable_factory=create_strategy_agent,
                input_adapter=strategy_input_adapter,
                output_adapter=strategy_output_adapter,
                next_node_selector=select_next_node,
            ),
            FlowNode(
                id="speak",
                name="speak",
                runnable_factory=create_speak_agent,
                input_adapter=speak_input_adapter,
            ),
            FlowNode(
                id="telegram",
                name="telegram",
                runnable_factory=create_telegram_agent,
                input_adapter=telegram_input_adapter,
            ),
        ]
    
    def __init__(self, **data):
        """Initialize CharacterFlow and build nodes"""
        if "flow_id" not in data:
            data["flow_id"] = f"flow-{uuid.uuid4().hex[:8]}"
        super().__init__(**data)
        self._initialize_llms()
        self.nodes = self.build_nodes()
        logger.info(f" {self.name} flow initialized")
