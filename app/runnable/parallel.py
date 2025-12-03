"""Parallel - Parallel composition of Runnables

A ParallelGroup executes multiple Runnables concurrently,
merging their event streams.
"""

import asyncio
from typing import AsyncIterator, List, Union

from pydantic import Field

from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionState
from app.logger import logger


class ParallelGroup(Runnable):
    """Parallel group for concurrent execution of Runnables
    
    Executes all Runnables in parallel, merging their event streams.
    All Runnables receive the same input context.
    
    Supports the & operator for parallel composition:
        parallel = agent1 & agent2 & agent3
    
    Attributes:
        runnables: List of Runnables to execute in parallel
    """
    
    runnables: List[Runnable] = Field(
        default_factory=list,
        description="Runnables to execute in parallel"
    )
    
    async def run_stream(
        self,
        context: ExecutionContext
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute all Runnables in parallel
        
        Args:
            context: Execution context (shared by all Runnables)
            
        Yields:
            ExecutionEvent: Merged events from all Runnables
        """
        if self.state != ExecutionState.IDLE:
            raise RuntimeError(f"Cannot run from state: {self.state}")
        
        # Queue to collect events from all runnables
        event_queue: asyncio.Queue[Union[ExecutionEvent, tuple]] = asyncio.Queue()
        
        async def run_to_queue(runnable: Runnable, idx: int):
            """Run a single Runnable and put events in queue"""
            try:
                async for event in runnable.run_stream(context):
                    if event.type != "final":
                        # Add path and put in queue
                        path_event = self.with_path(event, self.id, f"parallel_{idx}_{runnable.name}")
                        await event_queue.put(path_event)
                # Signal completion
                await event_queue.put(("done", idx, runnable.name))
            except asyncio.CancelledError:
                logger.debug(f"Parallel runnable {runnable.name} cancelled")
                await event_queue.put(("done", idx, runnable.name))
            except Exception as e:
                logger.error(f"Error in parallel runnable {runnable.name}: {e}")
                await event_queue.put(ExecutionEvent(
                    type="error",
                    content=f"Parallel task {runnable.name} failed: {e}",
                    execution_path=[self.id, f"parallel_{idx}_{runnable.name}"]
                ))
                await event_queue.put(("done", idx, runnable.name))
        
        async with self.state_context(ExecutionState.RUNNING):
            # Start all tasks
            tasks = [
                asyncio.create_task(run_to_queue(r, i))
                for i, r in enumerate(self.runnables)
            ]
            
            # Collect events until all tasks complete
            done_count = 0
            total_count = len(self.runnables)
            
            try:
                while done_count < total_count:
                    item = await event_queue.get()
                    
                    if isinstance(item, tuple) and item[0] == "done":
                        done_count += 1
                        logger.debug(f"Parallel task {item[2]} completed ({done_count}/{total_count})")
                    else:
                        yield item
            except Exception as e:
                logger.error(f"Error in parallel group: {e}")
                # Cancel remaining tasks
                for task in tasks:
                    if not task.done():
                        task.cancel()
                raise
        
        # Yield final event
        yield ExecutionEvent(
            type="final",
            execution_path=[self.id]
        )
    
    def __and__(self, other: Runnable) -> "ParallelGroup":
        """Add another Runnable to this parallel group
        
        Args:
            other: Runnable to add
            
        Returns:
            New ParallelGroup with the additional Runnable
        """
        return ParallelGroup(
            id=f"{self.id}-extended",
            name=f"{self.name} & {other.name}",
            runnables=[*self.runnables, other]
        )

