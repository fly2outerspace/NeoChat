"""CharacterFlow: Flow with StrategyAgent, SpeakAgent, and TelegramAgent"""
import uuid
from typing import Any, Dict, List, Optional

from click.parser import ParsingState

from app.agent.base import BaseAgent
from app.agent.strategy import StrategyAgent
from app.agent.speak import SpeakAgent
from app.agent.telegram import TelegramAgent
from app.flow.base import FlowNode
from app.flow.sequential_flow import SequentialFlow
from app.llm import LLM
from app.memory import Memory
from app.logger import logger
from pydantic import Field
from app.tool import (
    SendTelegramMessage,
    SpeakInPerson,
    Strategy,
    Terminate,
    ToolCollection,
    DialogueHistory,
    WebSearch,
    ScheduleReader,
    ScheduleWriter,
    ScenarioReader,
    ScenarioWriter,
    RelationTool,
    Reflection,
)

class CharacterFlow(SequentialFlow):
    """CharacterFlow: A flow with three sequential agents
    
    Flow structure:
    1. StrategyAgent: Makes strategic decisions about communication channel and plans conversation strategy
    2. SpeakAgent or TelegramAgent: Executes the conversation based on strategy decision
    """
    
    name: str = "character_flow"  # This is the name of the character, should be set by the caller.
    roleplay_prompt: str = ""  # This is the roleplay prompt for the character, should be set by the caller.
    
    # LLM instances for different agents
    chat_llm: Optional[LLM] = None  # LLM for chat agents (SpeakAgent and TelegramAgent)
    strategy_llm: Optional[LLM] = None  # LLM for strategy agent
    
    def _initialize_llms(self):
        """Initialize default LLM instances if not provided"""
        if self.chat_llm is None:
            self.chat_llm = LLM(config_name="openai")
        if self.strategy_llm is None:
            self.strategy_llm = LLM(config_name="openai")
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes for CharacterFlow"""
        
        def create_strategy_agent(context: Dict[str, Any]) -> BaseAgent:
            """Factory function for strategy agent"""
            session_id = context.get("session_id", self.session_id)
            memory = Memory(session_id=session_id)
            return StrategyAgent(
                session_id=session_id,
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
                    DialogueHistory(session_id=session_id, character_id=self.character_id),
                    ScheduleReader(session_id=session_id, character_id=self.character_id),
                    ScheduleWriter(session_id=session_id, character_id=self.character_id),
                    ScenarioReader(session_id=session_id, character_id=self.character_id),
                    ScenarioWriter(session_id=session_id, character_id=self.character_id),
                    RelationTool(session_id=session_id, character_id=self.character_id),
                ),
                visible_for_characters=self.visible_for_characters,
            )
        
        def create_speak_agent(context: Dict[str, Any]) -> BaseAgent:
            """Factory function for speak agent"""
            session_id = context.get("session_id", self.session_id)
            memory = Memory(session_id=session_id)
            return SpeakAgent(
                session_id=session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.chat_llm,
                memory=memory,
                visible_for_characters=self.visible_for_characters,
            )
        
        def create_telegram_agent(context: Dict[str, Any]) -> BaseAgent:
            """Factory function for telegram agent"""
            session_id = context.get("session_id", self.session_id)
            memory = Memory(session_id=session_id)
            return TelegramAgent(
                session_id=session_id,
                name=self.name,
                roleplay_prompt=self.roleplay_prompt,
                character_id=self.character_id,
                llm=self.chat_llm,
                memory=memory,
                visible_for_characters=self.visible_for_characters,
            )
        
        def strategy_input_adapter(context: Dict[str, Any]) -> Dict[str, Any]:
            """Transform context for strategy agent input"""
            return {
                "request": context.get("user_input", ""),
                "input_mode": context.get("input_mode"),
            }
        
        def strategy_output_adapter(agent: StrategyAgent, context: Dict[str, Any]) -> Dict[str, Any]:
            """Extract strategy output and update context
            
            Returns:
                Dict with strategy data if valid decision found, empty dict otherwise
            """
            # Get structured data directly from tool_results
            decision = None
            strategy = ""
            
            if hasattr(agent, 'tool_results') and agent.tool_results:
                # Find strategy tool result from tool_results
                for tool_call_id, tool_result in agent.tool_results.items():
                    # Check if this tool_result has strategy args
                    if tool_result.args and "decision" in tool_result.args:
                        decision = tool_result.args.get("decision")
                        strategy = tool_result.args.get("strategy", "")
                        break
            
            # Only update context if we have a valid decision
            # If no valid decision, return empty dict to prevent updating context with empty values
            if decision is None or not decision:
                logger.warning(f" {self.name} strategy agent did not provide valid decision, skipping context update")
                return {}
            
            return {
                "decision": decision,
                "strategy": strategy
            }
        
        def speak_input_adapter(context: Dict[str, Any]) -> Dict[str, Any]:
            """Transform context for speak agent input"""
            user_input = context.get("user_input", "")
            strategy = context.get("strategy", "")
            
            return {
                "request": user_input,
                "strategy": strategy
            }
        
        def telegram_input_adapter(context: Dict[str, Any]) -> Dict[str, Any]:
            """Transform context for telegram agent input"""
            user_input = context.get("user_input", "")
            strategy = context.get("strategy", "")
            
            return {
                "request": user_input,
                "strategy": strategy
            }
        
        def select_next_node(context: Dict[str, Any]) -> Optional[str]:
            """Select next node based on strategy decision
            
            Returns:
                str: Next node ID if decision is valid
                None: End flow if no decision or invalid decision
            """
            decision = context.get("decision")
            
            # If no decision (None or empty or not in context), end the flow
            if decision is None or not decision:
                logger.info(f" {self.name} no strategy decision found in context, ending flow")
                return None
            
            decision = str(decision).lower()
            if decision == "speakinperson":
                logger.info(f" {self.name} selected next node: speak (decision: {decision})")
                return "speak"
            elif decision == "telegram":
                logger.info(f" {self.name} selected next node: telegram (decision: {decision})")
                return "telegram"
            else:
                # Invalid decision, end flow
                logger.warning(f" {self.name} invalid strategy decision: {decision}, ending flow")
                return None
        
        return [
            FlowNode(
                id="strategy",
                name="strategy",
                agent_factory=create_strategy_agent,
                input_adapter=strategy_input_adapter,
                output_adapter=strategy_output_adapter,
                next_node_selector=select_next_node,
            ),
            FlowNode(
                id="speak",
                name="speak",
                agent_factory=create_speak_agent,
                input_adapter=speak_input_adapter
            ),
            FlowNode(
                id="telegram",
                name="telegram",
                agent_factory=create_telegram_agent,
                input_adapter=telegram_input_adapter
            ),
        ]
    
    def __init__(self, **data):
        """Initialize CharacterFlow and build nodes"""
        if "flow_id" not in data:
            data["flow_id"] = f"flow-{uuid.uuid4().hex[:8]}"
        super().__init__(**data)
        # Initialize default LLMs if not provided
        self._initialize_llms()
        # Build nodes after initialization
        self.nodes = self.build_nodes()
        logger.info(f" {self.name} flow initialized with character_id={self.character_id}, visible_for_characters={self.visible_for_characters}")

