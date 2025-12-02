"""Base Flow framework for orchestrating multiple agents"""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, List, Literal, Optional
from contextlib import asynccontextmanager

from pydantic import BaseModel, Field

from app.agent.base import BaseAgent
from app.logger import logger
from app.schema import AgentStreamEvent, FlowEvent, FlowState, Message


class FlowNode(BaseModel):
    """Represents a node in a flow graph
    
    Each node contains an agent factory and adapters for input/output transformation.
    """
    
    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Human-readable node name")
    agent_factory: Callable[[Dict[str, Any]], BaseAgent] = Field(
        ..., description="Factory function that creates an agent instance from context"
    )
    input_adapter: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None,
        description="Function to transform flow context into agent input (returns kwargs for agent.run_stream)"
    )
    output_adapter: Optional[Callable[[BaseAgent, Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Function to extract agent output and update flow context. "
            "IMPORTANT: If the agent did not provide valid output, return an empty dict {} "
            "to prevent updating context with empty/null values. Only return non-empty dict "
            "when valid data is available."
        )
    )
    next_node_selector: Optional[Callable[[Dict[str, Any]], Optional[str]]] = Field(
        default=None,
        description=(
            "Function to select next node ID based on context. Returns node ID or None to continue sequentially. "
            "IMPORTANT: If required context data is not found or invalid, return None to end the flow. "
            "Do not proceed to next node when required data is missing."
        )
    )
    
    class Config:
        arbitrary_types_allowed = True


class BaseFlow(BaseModel, ABC):
    """Abstract base class for managing multi-agent flows
    
    Provides foundational functionality for orchestrating multiple agents,
    managing flow state, and streaming events across agents.
    
    This is the base class that contains common functionality shared by all flow types.
    Specific flow implementations (like SequentialFlow) should inherit from this class.
    """
    
    # Core attributes
    flow_id: str = Field(..., description="Unique flow instance ID")
    session_id: str = Field(..., description="Session ID for this flow instance")
    name: str = Field(..., description="Flow name")
    
    # Flow state
    state: FlowState = Field(
        default=FlowState.IDLE, description="Current flow state"
    )
    
    # Flow nodes
    nodes: List[FlowNode] = Field(
        default_factory=list, description="List of flow nodes to execute"
    )
    
    # Flow context (shared state between nodes)
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Shared context between nodes"
    )
    
    # Character visibility attributes
    character_id: Optional[str] = Field(
        default=None,
        description="Character ID for this flow (used for filtering messages when querying)"
    )
    
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that messages from this flow should be visible to (None means visible to all)"
    )
    
    
    class Config:
        arbitrary_types_allowed = True
    
    @asynccontextmanager
    async def state_context(self, new_state: FlowState):
        """Context manager for safe flow state transitions.
        
        Args:
            new_state: The state to transition to during the context.
            
        Yields:
            None: Allows execution within the new state.
            
        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, FlowState):
            raise ValueError(f"Invalid state: {new_state}")
        
        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = FlowState.ERROR
            raise e
        finally:
            self.state = previous_state
    
    def on_event(self, event: FlowEvent) -> None:
        """Hook for handling flow events.
        
        Subclasses can override this to add custom event handling,
        logging, monitoring, etc.
        
        Args:
            event: The flow event to handle
        """
        pass
    
    def _wrap_event(
        self,
        node: FlowNode,
        agent_event: AgentStreamEvent,
        stage: Optional[str] = None
    ) -> FlowEvent:
        """Wrap an AgentStreamEvent into a FlowEvent.
        
        Args:
            node: The node that generated the event
            agent_event: The original agent event
            stage: Optional stage name (defaults to node.name)
            
        Returns:
            FlowEvent with flow-specific metadata
        """
        return FlowEvent(
            type=agent_event.type,
            content=agent_event.content,
            step=agent_event.step,
            total_steps=agent_event.total_steps,
            message_type=agent_event.message_type,
            message_id=agent_event.message_id,
            metadata=agent_event.metadata,
            flow_id=self.flow_id,
            node_id=node.id,
            stage=stage or node.name,
        )
    
    async def execute_node(
        self,
        node: FlowNode,
        context: Dict[str, Any]
    ) -> AsyncIterator[FlowEvent]:
        """Execute a single flow node.
        
        Args:
            node: The node to execute
            context: Current flow context
            
        Yields:
            FlowEvent: Events from the node's agent execution
        """
        try:
            # Create agent instance using factory
            agent = node.agent_factory(context)
            
            # Prepare agent input using input adapter
            agent_input = {}
            if node.input_adapter:
                agent_input = node.input_adapter(context)
            else:
                # Default: pass user_input from context
                agent_input = {
                    "request": context.get("user_input", ""),
                    **{k: v for k, v in context.items() if k != "user_input"}
                }
            
            # Execute agent with streaming
            async for agent_event in agent.run_stream(**agent_input):
                # Skip agent's final event - it's an internal state signal
                # Flow termination is controlled by flow itself, not by agent completion
                if agent_event.type == "final":
                    logger.debug(f" {self.name} node '{node.id}' agent completed, skipping final event")
                    continue
                
                flow_event = self._wrap_event(node, agent_event)
                self.on_event(flow_event)
                yield flow_event
            
            # Extract output using output adapter
            # IMPORTANT: output_adapter should return empty dict {} if agent did not provide valid output
            # This prevents updating context with empty/null values. Only non-empty dicts will update context.
            if node.output_adapter:
                updated_context = node.output_adapter(agent, context)
                # Only update context if adapter returned non-empty dict (valid output)
                if updated_context:
                    self.context.update(updated_context)
                    logger.info(f" {self.name} node '{node.id}' output adapter updated context with keys: {list(updated_context.keys())}")
                else:
                    logger.info(f" {self.name} node '{node.id}' output adapter returned empty dict, skipping context update")
            
        except Exception as e:
            logger.error(f"Error: The {self.name}'s node '{node.id}' execution hit a snag: {e}")
            error_event = FlowEvent(
                type="error",
                content=f"Node {node.name} execution failed: {str(e)}",
                flow_id=self.flow_id,
                node_id=node.id,
                stage=node.name,
            )
            self.on_event(error_event)
            yield error_event
            raise
    
    async def run(self, user_input: Optional[str] = None, **kwargs) -> str:
        """Execute the flow's main loop asynchronously.
        
        Args:
            user_input: Optional initial user input to process.
            **kwargs: Additional context variables
            
        Returns:
            A string summarizing the execution results.
        """
        buffer = []
        async for event in self.run_stream(user_input, **kwargs):
            if event.type == "token" and event.content:
                buffer.append(event.content)
        return "".join(buffer) if buffer else ""
    
    @abstractmethod
    async def run_stream(
        self,
        user_input: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[FlowEvent]:
        """Execute the flow's main loop with streaming events.
        
        Args:
            user_input: Optional initial user input to process.
            **kwargs: Additional context variables to add to flow context
            
        Yields:
            FlowEvent: Streaming events during execution.
            
        Raises:
            RuntimeError: If the flow is not in IDLE state at start.
        """
        pass
    
    @abstractmethod
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes.
        
        Subclasses must implement this to define their specific node configuration.
        
        Returns:
            List of FlowNode instances
        """
        pass

