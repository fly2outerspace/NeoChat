"""Sequential flow implementation for executing nodes one by one

SequentialFlow executes nodes in sequence, supporting conditional routing
based on node selectors.
"""

from typing import AsyncIterator, Dict, List, Optional, Union

from app.flow.base import BaseFlow, FlowNode
from app.logger import logger
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionState


class SequentialFlow(BaseFlow):
    """Sequential flow implementation
    
    Executes nodes one by one in sequence, supporting conditional routing.
    This is the default flow type for most use cases.
    """
    
    async def run_stream(
        self,
        context: Union[ExecutionContext, str, None] = None,
        **kwargs
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute the flow's main loop with streaming events.
        
        Args:
            context: ExecutionContext, user_input string, or None
            **kwargs: Additional context variables
            
        Yields:
            ExecutionEvent: Streaming events during execution.
        """
        if self.state != ExecutionState.IDLE:
            raise RuntimeError(f"Cannot run flow from state: {self.state}")
        
        # Initialize context
        exec_context = self._init_context_from_input(context, **kwargs)
        
        # Update legacy Dict context
        self.context = {
            "user_input": exec_context.user_input or "",
            "session_id": self.session_id,
            **exec_context.data,
        }
        
        logger.info(f" {self.name} flow running with context keys: {list(self.context.keys())}")
        
        async with self.state_context(ExecutionState.RUNNING):
            # Create node map for quick lookup
            node_map = {node.id: node for node in self.nodes}
            executed_nodes = set()
            
            # Start with first node
            current_node_id = self._get_starting_node_id()
            step_count = 0
            
            logger.info(f" {self.name} starting execution with {len(self.nodes)} nodes")
            
            while current_node_id and current_node_id in node_map:
                # Avoid infinite loops
                if current_node_id in executed_nodes:
                    logger.warning(f"{self.name} detected loop at node {current_node_id}")
                    break
                
                node = node_map[current_node_id]
                executed_nodes.add(current_node_id)
                step_count += 1
                
                logger.info(f"Executing node {step_count}: {node.id} ({node.name})")
                
                # Emit flow step event
                yield ExecutionEvent(
                    type="flow_step",
                    content=f"执行节点 {step_count}: {node.name}",
                    step=step_count,
                    flow_id=self.flow_id,
                    node_id=node.id,
                    stage=node.name,
                )
                
                # Execute node
                async for event in self.execute_node(node, self.context):
                    yield event
                
                # Determine next node
                if node.next_node_selector:
                    next_node_id = node.next_node_selector(self.context)
                    if next_node_id:
                        logger.info(f" {self.name} routing to: {next_node_id}")
                        current_node_id = next_node_id
                    else:
                        logger.info(f" {self.name} selector returned None, ending flow")
                        current_node_id = None
                else:
                    logger.info(f" {self.name} node '{node.id}' is terminal")
                    current_node_id = None
            
            logger.info(f" {self.name} completed: {step_count} nodes executed")
        
        # Emit final event
        yield ExecutionEvent(
            type="final",
            flow_id=self.flow_id,
        )
    
    def _get_starting_node_id(self) -> Optional[str]:
        """Get the starting node ID."""
        if self.nodes:
            return self.nodes[0].id
        return None
    
    def _get_next_sequential_node(self, current_node_id: str, node_map: Dict[str, FlowNode]) -> Optional[str]:
        """Get the next node ID in sequential order."""
        node_ids = [node.id for node in self.nodes]
        try:
            current_index = node_ids.index(current_node_id)
            if current_index + 1 < len(node_ids):
                return node_ids[current_index + 1]
        except ValueError:
            pass
        return None
    
    def build_nodes(self) -> List[FlowNode]:
        """Build the flow nodes. Override in subclasses."""
        return []
