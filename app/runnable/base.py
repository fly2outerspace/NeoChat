"""Runnable - Core abstraction for executable units

This module defines the Runnable protocol, which is the fundamental abstraction
for all executable units in the system. Both Agents and Flows are Runnables.

A Runnable is simply something that can:
1. Accept an ExecutionContext
2. Yield a stream of ExecutionEvents
3. Be composed with other Runnables
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, AsyncIterator, List, Optional

from pydantic import BaseModel, Field, model_validator

from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionEventType, ExecutionState

if TYPE_CHECKING:
    from app.runnable.pipeline import Pipeline
    from app.runnable.parallel import ParallelGroup


class Runnable(BaseModel, ABC):
    """Abstract base class for all executable units
    
    This is the core abstraction that unifies Agents and Flows.
    Any Runnable can:
    1. Execute independently via run_stream()
    2. Be composed with other Runnables using | and & operators
    3. Be nested within other Runnables (e.g., Flow containing Flows)
    
    Subclasses must implement:
    - run_stream(): The core execution method that yields events
    
    Attributes:
        id: Unique identifier for this Runnable instance
        name: Human-readable name
        state: Current execution state
    """
    
    # Identification
    id: Optional[str] = Field(default=None, description="Unique identifier (auto-generated if not provided)")
    name: str = Field(..., description="Human-readable name")
    
    # Execution state
    state: ExecutionState = Field(
        default=ExecutionState.IDLE,
        description="Current execution state"
    )
    
    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses
    
    @model_validator(mode="after")
    def generate_id(self) -> "Runnable":
        """Auto-generate id if not provided"""
        if not self.id:
            import uuid
            # Generate id based on class name and name
            class_name = self.__class__.__name__.lower()
            short_uuid = uuid.uuid4().hex[:8]
            object.__setattr__(self, 'id', f"{class_name}-{self.name}-{short_uuid}")
        return self
    
    @asynccontextmanager
    async def state_context(self, new_state: ExecutionState):
        """Context manager for safe state transitions
        
        Automatically handles state transitions and error handling.
        On error, state is set to ERROR.
        On exit, state is restored to previous value.
        
        Args:
            new_state: The state to transition to
            
        Yields:
            None
            
        Example:
            async with self.state_context(ExecutionState.RUNNING):
                # Do work here
                pass
        """
        if not isinstance(new_state, ExecutionState):
            raise ValueError(f"Invalid state: {new_state}")
        
        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = ExecutionState.ERROR
            raise
        finally:
            self.state = previous_state
    
    @abstractmethod
    async def run_stream(
        self,
        context: ExecutionContext
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute and yield a stream of events
        
        This is the core method that all Runnables must implement.
        It takes an ExecutionContext and yields ExecutionEvents.
        
        Args:
            context: The execution context containing input and shared state
            
        Yields:
            ExecutionEvent: Events generated during execution
            
        Raises:
            RuntimeError: If the Runnable is not in IDLE state
        """
        pass
    
    async def run(self, context: ExecutionContext) -> str:
        """Execute and collect all tokens into a string
        
        This is a convenience method that collects all token events
        and returns them as a single string.
        
        Args:
            context: The execution context
            
        Returns:
            Concatenated string of all token content
        """
        tokens = []
        async for event in self.run_stream(context):
            if event.type == ExecutionEventType.TOKEN and event.content:
                tokens.append(event.content)
        return "".join(tokens)
    
    def __or__(self, other: "Runnable") -> "Pipeline":
        """Support pipeline operator: runnable1 | runnable2
        
        Creates a Pipeline that executes runnables sequentially.
        The output context of the first becomes input to the second.
        
        Args:
            other: Another Runnable to chain after this one
            
        Returns:
            Pipeline containing both Runnables
        """
        from app.runnable.pipeline import Pipeline
        return Pipeline(
            id=f"pipeline-{self.id}-{other.id}",
            name=f"{self.name} | {other.name}",
            stages=[self, other]
        )
    
    def __and__(self, other: "Runnable") -> "ParallelGroup":
        """Support parallel operator: runnable1 & runnable2
        
        Creates a ParallelGroup that executes runnables in parallel.
        Both receive the same input context.
        
        Args:
            other: Another Runnable to run in parallel
            
        Returns:
            ParallelGroup containing both Runnables
        """
        from app.runnable.parallel import ParallelGroup
        return ParallelGroup(
            id=f"parallel-{self.id}-{other.id}",
            name=f"{self.name} & {other.name}",
            runnables=[self, other]
        )
    
    def with_path(self, event: ExecutionEvent, *path_segments: str) -> ExecutionEvent:
        """Add execution path to an event
        
        Helper method to add path information to events for tracing.
        
        Args:
            event: The event to modify
            *path_segments: Path segments to prepend
            
        Returns:
            New event with updated execution_path
        """
        new_path = list(path_segments) + (event.execution_path or [])
        return event.model_copy(update={"execution_path": new_path})

