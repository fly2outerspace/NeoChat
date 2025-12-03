"""Runnable Node - Node definition for Flow composition

A RunnableNode wraps a Runnable (Agent or Flow) with adapters
for input/output transformation and routing logic.
"""

from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from pydantic import BaseModel, Field

from app.runnable.context import ExecutionContext

if TYPE_CHECKING:
    from app.runnable.base import Runnable


class RunnableNode(BaseModel):
    """Node definition for Flow composition
    
    Each node in a Flow contains:
    1. A factory function to create the Runnable (Agent or another Flow)
    2. Optional input/output adapters for context transformation
    3. Optional routing logic for conditional execution
    4. Flags for parallel execution behavior
    
    Attributes:
        id: Unique node identifier
        name: Human-readable node name
        runnable_factory: Function that creates a Runnable from context
        input_adapter: Optional function to transform input context
        output_adapter: Optional function to extract output and update context
        next_selector: Optional function to select next node ID
        is_background: If True, runs in background after HTTP response ends
        can_stop_response: If True, completion can trigger HTTP response stop
    """
    
    # Identification
    id: str = Field(..., description="Unique node identifier")
    name: str = Field(..., description="Human-readable node name")
    
    # Executor factory - creates Agent or Flow from context
    runnable_factory: Callable[[ExecutionContext], "Runnable"] = Field(
        ...,
        description="Factory function that creates a Runnable from context"
    )
    
    # Input adapter - transforms context before execution
    input_adapter: Optional[Callable[[ExecutionContext], ExecutionContext]] = Field(
        default=None,
        description="Function to transform context before passing to Runnable"
    )
    
    # Output adapter - extracts results and updates context
    output_adapter: Optional[Callable[["Runnable", ExecutionContext], Dict[str, Any]]] = Field(
        default=None,
        description=(
            "Function to extract output from Runnable and return context updates. "
            "Return empty dict {} if no valid output to prevent overwriting with nulls."
        )
    )
    
    # Routing - selects next node for conditional flows
    next_selector: Optional[Callable[[ExecutionContext], Optional[str]]] = Field(
        default=None,
        description=(
            "Function to select next node ID based on context. "
            "Return node ID to continue, None to end the flow."
        )
    )
    
    # Parallel execution flags
    is_background: bool = Field(
        default=False,
        description="If True, this node runs in background after HTTP response ends"
    )
    can_stop_response: bool = Field(
        default=True,
        description="If True, this node's completion can trigger HTTP response stop"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def create_runnable(self, context: ExecutionContext) -> "Runnable":
        """Create a Runnable instance using the factory
        
        Args:
            context: Current execution context
            
        Returns:
            New Runnable instance
        """
        return self.runnable_factory(context)
    
    def adapt_input(self, context: ExecutionContext) -> ExecutionContext:
        """Apply input adapter to context
        
        Args:
            context: Original context
            
        Returns:
            Transformed context (or original if no adapter)
        """
        if self.input_adapter:
            return self.input_adapter(context)
        return context
    
    def adapt_output(
        self,
        runnable: "Runnable",
        context: ExecutionContext
    ) -> Dict[str, Any]:
        """Apply output adapter to extract results
        
        Args:
            runnable: The executed Runnable
            context: Current context
            
        Returns:
            Dictionary of context updates (empty dict if no updates)
        """
        if self.output_adapter:
            return self.output_adapter(runnable, context) or {}
        return {}
    
    def select_next(self, context: ExecutionContext) -> Optional[str]:
        """Select the next node ID
        
        Args:
            context: Current context
            
        Returns:
            Next node ID, or None to end the flow
        """
        if self.next_selector:
            return self.next_selector(context)
        return None

