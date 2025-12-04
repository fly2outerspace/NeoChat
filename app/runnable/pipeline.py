"""Pipeline - Sequential composition of Runnables

A Pipeline executes multiple Runnables in sequence,
passing the context from one to the next.
"""

from typing import AsyncIterator, List

from pydantic import Field

from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionEventType, ExecutionState


class Pipeline(Runnable):
    """Pipeline for sequential execution of Runnables
    
    Executes stages one after another, with the output of each
    stage potentially updating the context for the next stage.
    
    Supports the | operator for chaining:
        pipeline = agent1 | agent2 | agent3
    
    Attributes:
        stages: List of Runnables to execute in order
    """
    
    stages: List[Runnable] = Field(
        default_factory=list,
        description="Runnables to execute in sequence"
    )
    
    async def run_stream(
        self,
        context: ExecutionContext
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute all stages sequentially
        
        Args:
            context: Initial execution context
            
        Yields:
            ExecutionEvent: Events from all stages
        """
        if self.state != ExecutionState.IDLE:
            raise RuntimeError(f"Cannot run from state: {self.state}")
        
        current_context = context
        
        async with self.state_context(ExecutionState.RUNNING):
            for i, stage in enumerate(self.stages):
                stage_name = f"stage_{i}_{stage.name}"
                
                # Execute stage and yield events with path
                async for event in stage.run_stream(current_context):
                    if event.type == ExecutionEventType.DONE:
                        # Don't yield intermediate final events
                        continue
                    
                    # Add pipeline path to event
                    yield self.with_path(event, self.id, stage_name)
                
                # Context updates would happen via output adapters in a full implementation
        
        # Yield final event for the pipeline
        yield ExecutionEvent(
            type=ExecutionEventType.DONE,
            execution_path=[self.id]
        )
    
    def __or__(self, other: Runnable) -> "Pipeline":
        """Chain another Runnable to this pipeline
        
        Args:
            other: Runnable to add to the end
            
        Returns:
            New Pipeline with the additional stage
        """
        return Pipeline(
            id=f"{self.id}-extended",
            name=f"{self.name} | {other.name}",
            stages=[*self.stages, other]
        )

