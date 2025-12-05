"""Base Flow - Composite Runnable implementation

BaseFlow is the abstract base class for all flows. It extends Runnable
to provide a unified execution framework.

A Flow is a composite Runnable - it contains and orchestrates child Runnables
(which can be Agents or other Flows).
"""

from abc import abstractmethod
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Union

from pydantic import Field, model_validator

from app.logger import logger
from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.runnable.node import RunnableNode
from app.schema import ExecutionEvent, ExecutionEventType, ExecutionState


class FlowNode(RunnableNode):
    """Flow node definition for composing Runnables (Agents or Flows)
    
    Each node contains a factory for creating a Runnable,
    with optional adapters for input/output transformation.
    
    Attributes:
        id: Unique node identifier
        name: Human-readable node name
        runnable_factory: Factory function that creates a Runnable from ExecutionContext
        input_adapter: Function to transform context before execution
        output_adapter: Function to extract output and update context
        next_node_selector: Function to select next node ID
        is_background: If True, runs in background (for ParallelFlow)
    """
    
    # Override to make optional for backward compatibility with subclass construction
    runnable_factory: Optional[Callable[[ExecutionContext], Runnable]] = Field(
        default=None,
        description="Factory function that creates a Runnable from ExecutionContext"
    )
    
    # Adapters using ExecutionContext
    input_adapter: Optional[Callable[[ExecutionContext], ExecutionContext]] = Field(
        default=None,
        description="Function to transform context before passing to Runnable"
    )
    output_adapter: Optional[Callable[[Runnable, ExecutionContext], Optional[ExecutionContext]]] = Field(
        default=None,
        description="Function to extract output and return updated context (or None if no updates)"
    )
    
    # Routing
    next_node_selector: Optional[Callable[[ExecutionContext], Optional[str]]] = Field(
        default=None,
        description="Function to select next node ID based on context"
    )
    
    class Config:
        arbitrary_types_allowed = True


class BaseFlow(Runnable):
    """Abstract base class for managing multi-agent flows
    
    BaseFlow extends Runnable to be part of the unified execution framework.
    It orchestrates multiple Runnables (Agents or sub-Flows).
    
    As a Runnable, BaseFlow can:
    1. Execute independently
    2. Be composed with other Runnables using | and & operators  
    3. Be nested within other Flows
    
    Attributes:
        id: Unique flow instance ID (inherited from Runnable)
        session_id: Session ID for this flow instance
        name: Flow name
        nodes: List of flow nodes to execute
        _context: Shared ExecutionContext between nodes
    """
    
    session_id: str = Field(..., description="Session ID for this flow instance")
    
    nodes: List[FlowNode] = Field(
        default_factory=list, description="List of flow nodes to execute"
    )
    
    character_id: Optional[str] = Field(
        default=None,
        description="Character ID for this flow"
    )
    
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that can see messages from this flow"
    )
    
    # Internal context (use _context to avoid serialization)
    _context: Optional[ExecutionContext] = None
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def on_event(self, event: ExecutionEvent) -> None:
        """Hook for handling flow events. Override for custom handling."""
        pass
    
    async def execute_node(
        self,
        node: FlowNode,
        context: ExecutionContext
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute a single flow node.
        
        Args:
            node: The node to execute
            context: Current execution context
            
        Yields:
            ExecutionEvent: Events from the node's execution
        """
        try:
            # Get runnable factory and create instance
            if not node.runnable_factory:
                raise ValueError(f"Node {node.id} has no runnable_factory")
            
            runnable = node.runnable_factory(context)
            logger.info(f" {self.name} node '{node.id}' executing {type(runnable).__name__}")
            
            # Prepare input context using adapter
            node_context = context
            if node.input_adapter:
                node_context = node.input_adapter(context)
            
            # Execute runnable (Agent or Flow) with streaming
            async for event in runnable.run_stream(node_context):
                # Skip done events from child runnables
                if event.type == ExecutionEventType.DONE:
                    logger.debug(f" {self.name} node '{node.id}' runnable completed")
                    continue
                
                # Add flow info to event
                event_with_flow = event.with_flow_info(
                    flow_id=self.id,
                    node_id=node.id,
                    stage=node.name
                )
                self.on_event(event_with_flow)
                yield event_with_flow
            
            # Extract output using adapter and update context
            if node.output_adapter:
                updated_context = node.output_adapter(runnable, context)
                if updated_context:
                    self._context = updated_context
                    logger.info(f" {self.name} node '{node.id}' updated context")
            
        except Exception as e:
            logger.error(f"Error in node '{node.id}': {e}", exc_info=True)
            yield ExecutionEvent(
                type=ExecutionEventType.ERROR,
                content=f"Node {node.name} failed: {str(e)}",
                flow_id=self.id,
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
            **kwargs: Additional context data
            
        Yields:
            ExecutionEvent: Streaming events during execution.
        """
        pass
    
    async def run(self, context: Union[ExecutionContext, str, None] = None, **kwargs) -> str:
        """Execute the flow and return result string."""
        buffer = []
        async for event in self.run_stream(context, **kwargs):
            if event.type == ExecutionEventType.TOKEN and event.content:
                buffer.append(event.content)
        return "".join(buffer) if buffer else ""
    
    @abstractmethod
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes. Subclasses must implement this."""
        pass
    
    def _init_context(
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
