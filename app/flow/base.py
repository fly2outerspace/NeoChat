"""Base Flow - Composite Runnable implementation

BaseFlow is the abstract base class for all flows. It extends Runnable
to be compatible with the unified execution framework while maintaining
backward compatibility with the existing flow interface.

A Flow is a composite Runnable - it contains and orchestrates child Runnables
(which can be Agents or other Flows).
"""

from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from pydantic import Field

from app.agent.base import BaseAgent
from app.logger import logger
from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.runnable.node import RunnableNode
from app.schema import (
    ExecutionEvent,
    ExecutionState,
    FlowState,
)


class FlowNode(RunnableNode):
    """Flow node definition for composing agents and flows
    
    Each node contains a factory for creating an Agent or Flow,
    with optional adapters for input/output transformation.
    
    Attributes:
        id: Unique node identifier
        name: Human-readable node name
        agent_factory: Factory function that creates an Agent
        input_adapter: Function to transform context before execution
        output_adapter: Function to extract output and update context
        next_node_selector: Function to select next node ID
        is_background: If True, runs in background (for ParallelFlow)
    """
    
    # Agent factory (creates Agent from context dict)
    agent_factory: Optional[Callable[[Dict[str, Any]], BaseAgent]] = Field(
        default=None,
        description="Factory function that creates an Agent instance from context dict"
    )
    
    # Adapters
    input_adapter: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None,
        description="Function to transform flow context into agent input"
    )
    output_adapter: Optional[Callable[[BaseAgent, Dict[str, Any]], Dict[str, Any]]] = Field(
        default=None,
        description="Function to extract agent output and update flow context"
    )
    
    # Routing
    next_node_selector: Optional[Callable[[Dict[str, Any]], Optional[str]]] = Field(
        default=None,
        description="Function to select next node ID based on context"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def get_runnable_factory(self) -> Callable[[ExecutionContext], Runnable]:
        """Get a runnable factory, converting from agent_factory if needed"""
        if self.runnable_factory:
            return self.runnable_factory
        
        if self.agent_factory:
            def wrapped_factory(context: ExecutionContext) -> Runnable:
                return self.agent_factory(context.to_dict())
            return wrapped_factory
        
        raise ValueError(f"Node {self.id} has no runnable_factory or agent_factory")


class BaseFlow(Runnable):
    """Abstract base class for managing multi-agent flows
    
    BaseFlow extends Runnable to be part of the unified execution framework.
    It orchestrates multiple agents or sub-flows.
    
    As a Runnable, BaseFlow can:
    1. Execute independently
    2. Be composed with other Runnables using | and & operators  
    3. Be nested within other Flows
    
    Attributes:
        flow_id: Unique flow instance ID
        session_id: Session ID for this flow instance
        name: Flow name
        nodes: List of flow nodes to execute
        context: Shared context between nodes
    """
    
    flow_id: str = Field(..., description="Unique flow instance ID")
    session_id: str = Field(..., description="Session ID for this flow instance")
    
    nodes: List[FlowNode] = Field(
        default_factory=list, description="List of flow nodes to execute"
    )
    
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Shared context between nodes"
    )
    
    character_id: Optional[str] = Field(
        default=None,
        description="Character ID for this flow"
    )
    
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that can see messages from this flow"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        """Initialize BaseFlow"""
        if "id" not in data and "flow_id" in data:
            data["id"] = data["flow_id"]
        elif "id" not in data:
            import uuid
            data["id"] = f"flow-{uuid.uuid4().hex[:8]}"
            data["flow_id"] = data["id"]
        super().__init__(**data)
    
    @property
    def legacy_state(self) -> FlowState:
        """Get the legacy FlowState (for backward compatibility)"""
        state_mapping = {
            ExecutionState.IDLE: FlowState.IDLE,
            ExecutionState.RUNNING: FlowState.RUNNING,
            ExecutionState.PAUSED: FlowState.PAUSED,
            ExecutionState.FINISHED: FlowState.FINISHED,
            ExecutionState.ERROR: FlowState.ERROR,
        }
        return state_mapping.get(self.state, FlowState.IDLE)
    
    @asynccontextmanager
    async def state_context(self, new_state: Union[FlowState, ExecutionState]):
        """Context manager for safe flow state transitions."""
        if isinstance(new_state, FlowState):
            state_mapping = {
                FlowState.IDLE: ExecutionState.IDLE,
                FlowState.RUNNING: ExecutionState.RUNNING,
                FlowState.PAUSED: ExecutionState.PAUSED,
                FlowState.FINISHED: ExecutionState.FINISHED,
                FlowState.ERROR: ExecutionState.ERROR,
            }
            new_state = state_mapping.get(new_state, ExecutionState.IDLE)
        
        if not isinstance(new_state, ExecutionState):
            raise ValueError(f"Invalid state: {new_state}")
        
        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = ExecutionState.ERROR
            raise e
        finally:
            self.state = previous_state
    
    def on_event(self, event: ExecutionEvent) -> None:
        """Hook for handling flow events. Override for custom handling."""
        pass
    
    async def execute_node(
        self,
        node: FlowNode,
        context: Dict[str, Any]
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute a single flow node.
        
        Args:
            node: The node to execute
            context: Current flow context (Dict)
            
        Yields:
            ExecutionEvent: Events from the node's agent execution
        """
        try:
            # Create agent instance using factory
            agent = node.agent_factory(context)
            
            # Prepare agent input using input adapter
            agent_input = {}
            if node.input_adapter:
                agent_input = node.input_adapter(context)
            else:
                agent_input = {
                    "request": context.get("user_input", ""),
                    **{k: v for k, v in context.items() if k != "user_input"}
                }
            
            # Execute agent with streaming
            async for event in agent.run_stream(**agent_input):
                # Skip agent's final event
                if event.type == "final":
                    logger.debug(f" {self.name} node '{node.id}' agent completed")
                    continue
                
                # Add flow info to event
                event_with_flow = event.with_flow_info(
                    flow_id=self.flow_id,
                    node_id=node.id,
                    stage=node.name
                )
                self.on_event(event_with_flow)
                yield event_with_flow
            
            # Extract output using output adapter
            if node.output_adapter:
                updated_context = node.output_adapter(agent, context)
                if updated_context:
                    self.context.update(updated_context)
                    logger.info(f" {self.name} node '{node.id}' updated context: {list(updated_context.keys())}")
            
        except Exception as e:
            logger.error(f"Error in node '{node.id}': {e}")
            yield ExecutionEvent(
                type="error",
                content=f"Node {node.name} failed: {str(e)}",
                flow_id=self.flow_id,
                node_id=node.id,
                stage=node.name,
            )
            raise
    
    @abstractmethod
    async def run_stream(
        self,
        context: Union[ExecutionContext, str, None] = None,
        **kwargs
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute the flow with streaming events.
        
        Args:
            context: ExecutionContext, user_input string, or None
            **kwargs: Additional context variables
            
        Yields:
            ExecutionEvent: Streaming events during execution.
        """
        pass
    
    async def run(self, user_input: Optional[str] = None, **kwargs) -> str:
        """Execute the flow and return result string."""
        buffer = []
        async for event in self.run_stream(user_input, **kwargs):
            if event.type == "token" and event.content:
                buffer.append(event.content)
        return "".join(buffer) if buffer else ""
    
    @abstractmethod
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes. Subclasses must implement this."""
        pass
    
    def _init_context_from_input(
        self,
        context_or_input: Union[ExecutionContext, str, None],
        **kwargs
    ) -> ExecutionContext:
        """Initialize ExecutionContext from various input types."""
        if isinstance(context_or_input, ExecutionContext):
            if kwargs:
                return context_or_input.merge(**kwargs)
            return context_or_input
        
        user_input = context_or_input if isinstance(context_or_input, str) else None
        return ExecutionContext(
            session_id=self.session_id,
            user_input=user_input,
            character_id=self.character_id,
            visible_for_characters=self.visible_for_characters,
            data=kwargs,
        )
