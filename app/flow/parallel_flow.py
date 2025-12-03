"""Parallel flow implementation for executing nodes concurrently

ParallelFlow executes multiple nodes in parallel, supporting:
1. Response nodes: Participate in HTTP response streaming
2. Background nodes: Continue running after HTTP response ends

This enables patterns like:
- Main chat response + background memory update
- Multiple channels sending simultaneously
- Fast response + deep analysis in background
"""

import asyncio
from typing import AsyncIterator, Dict, List, Optional, Set, Union

from pydantic import Field

from app.flow.base import BaseFlow, FlowNode
from app.logger import logger
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionState


class ParallelFlow(BaseFlow):
    """Parallel flow implementation
    
    Executes all nodes concurrently. Response nodes' events are streamed
    to the HTTP response. Background nodes continue after HTTP response ends.
    
    Node Configuration:
    - is_background=False (default): Response node, participates in HTTP response
    - is_background=True: Background node, runs after HTTP response ends
    
    Execution Flow:
    1. All nodes start executing in parallel
    2. Events from response nodes are streamed to HTTP response
    3. When ALL response nodes complete, HTTP response ends
    4. Background nodes continue running independently
    """
    
    response_timeout: Optional[float] = Field(
        default=None,
        description="Timeout for response nodes in seconds"
    )
    background_timeout: Optional[float] = Field(
        default=300.0,
        description="Timeout for background tasks in seconds"
    )
    
    # Internal state
    _background_tasks: List[asyncio.Task] = []
    _event_queue: Optional[asyncio.Queue] = None
    
    class Config:
        arbitrary_types_allowed = True
        underscore_attrs_are_private = True
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes. Override in subclasses."""
        return []
    
    async def run_stream(
        self,
        context: Union[ExecutionContext, str, None] = None,
        **kwargs
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute all nodes in parallel with streaming events.
        
        Args:
            context: ExecutionContext, user_input string, or None
            **kwargs: Additional context data
            
        Yields:
            ExecutionEvent: Events from response nodes
        """
        if self.state != ExecutionState.IDLE:
            raise RuntimeError(f"Cannot run flow from state: {self.state}")
        
        # Initialize context
        self._context = self._init_context(context, **kwargs)
        
        # Reset internal state
        self._background_tasks = []
        self._event_queue = asyncio.Queue()
        
        # Separate response and background nodes
        response_nodes = [n for n in self.nodes if not n.is_background]
        background_nodes = [n for n in self.nodes if n.is_background]
        
        logger.info(
            f" {self.name} parallel execution: "
            f"{len(response_nodes)} response, {len(background_nodes)} background"
        )
        
        async with self.state_context(ExecutionState.RUNNING):
            # Start all tasks
            response_tasks: List[asyncio.Task] = []
            
            for node in response_nodes:
                task = asyncio.create_task(
                    self._run_node_to_queue(node, is_response=True),
                    name=f"response-{node.id}"
                )
                response_tasks.append(task)
            
            for node in background_nodes:
                task = asyncio.create_task(
                    self._run_node_to_queue(node, is_response=False),
                    name=f"background-{node.id}"
                )
                self._background_tasks.append(task)
            
            # Track active response nodes
            active_response_ids: Set[str] = {n.id for n in response_nodes}
            
            # Emit start event
            yield ExecutionEvent(
                type="flow_step",
                content=f"开始并行执行 {len(response_nodes)} 个响应节点",
                flow_id=self.flow_id,
            )
            
            # Process events until all response nodes complete
            try:
                while active_response_ids:
                    try:
                        event = await asyncio.wait_for(
                            self._event_queue.get(),
                            timeout=0.1
                        )
                    except asyncio.TimeoutError:
                        if all(t.done() for t in response_tasks):
                            break
                        continue
                    
                    # Handle completion markers
                    if isinstance(event, dict) and event.get("_marker") == "node_complete":
                        node_id = event["node_id"]
                        if event["is_response"] and node_id in active_response_ids:
                            active_response_ids.remove(node_id)
                            logger.info(f" {self.name} node '{node_id}' done, {len(active_response_ids)} left")
                        continue
                    
                    # Yield events
                    if isinstance(event, ExecutionEvent):
                        yield event
                
            except Exception as e:
                logger.error(f" {self.name} error: {e}")
                yield ExecutionEvent(
                    type="error",
                    content=f"Parallel flow error: {e}",
                    flow_id=self.flow_id,
                )
        
        # Emit final event
        yield ExecutionEvent(
            type="final",
            flow_id=self.flow_id,
            metadata={
                "background_tasks": len(self._background_tasks),
                "running": sum(1 for t in self._background_tasks if not t.done()),
            }
        )
        
        logger.info(
            f" {self.name} response ended, "
            f"{sum(1 for t in self._background_tasks if not t.done())} background tasks continue"
        )
    
    async def _run_node_to_queue(self, node: FlowNode, is_response: bool) -> None:
        """Run a node and put events into the queue."""
        try:
            logger.info(f" {self.name} starting {'response' if is_response else 'background'} node: {node.id}")
            
            async for event in self.execute_node(node, self._context):
                await self._event_queue.put(event)
            
            await self._event_queue.put({
                "_marker": "node_complete",
                "node_id": node.id,
                "is_response": is_response,
            })
            
            logger.info(f" {self.name} node '{node.id}' completed")
            
        except asyncio.CancelledError:
            logger.info(f" {self.name} node '{node.id}' cancelled")
            await self._event_queue.put({
                "_marker": "node_complete",
                "node_id": node.id,
                "is_response": is_response,
            })
        except Exception as e:
            logger.error(f" {self.name} node '{node.id}' error: {e}")
            await self._event_queue.put(ExecutionEvent(
                type="error",
                content=f"Node {node.name} failed: {e}",
                flow_id=self.flow_id,
                node_id=node.id,
            ))
            await self._event_queue.put({
                "_marker": "node_complete",
                "node_id": node.id,
                "is_response": is_response,
            })
    
    async def wait_background_tasks(self, timeout: Optional[float] = None) -> Dict[str, bool]:
        """Wait for all background tasks to complete."""
        if not self._background_tasks:
            return {}
        
        timeout = timeout or self.background_timeout
        results = {}
        
        try:
            if timeout:
                done, pending = await asyncio.wait(
                    self._background_tasks,
                    timeout=timeout
                )
                for task in done:
                    results[task.get_name()] = True
                for task in pending:
                    results[task.get_name()] = False
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            else:
                await asyncio.gather(*self._background_tasks, return_exceptions=True)
                for task in self._background_tasks:
                    results[task.get_name()] = True
        except Exception as e:
            logger.error(f" {self.name} error waiting for background: {e}")
        
        return results
    
    def cancel_background_tasks(self) -> int:
        """Cancel all running background tasks."""
        cancelled = 0
        for task in self._background_tasks:
            if not task.done():
                task.cancel()
                cancelled += 1
        logger.info(f" {self.name} cancelled {cancelled} background tasks")
        return cancelled
    
    def get_background_task_status(self) -> Dict[str, str]:
        """Get status of all background tasks."""
        status = {}
        for task in self._background_tasks:
            name = task.get_name()
            if task.done():
                if task.cancelled():
                    status[name] = "cancelled"
                elif task.exception():
                    status[name] = f"error: {task.exception()}"
                else:
                    status[name] = "completed"
            else:
                status[name] = "running"
        return status
