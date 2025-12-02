"""Sequential flow implementation for executing nodes one by one"""
from typing import AsyncIterator, Dict, Optional

from app.flow.base import BaseFlow, FlowNode
from app.logger import logger
from app.schema import FlowEvent, FlowState


class SequentialFlow(BaseFlow):
    """Sequential flow implementation
    
    Executes nodes one by one in sequence, supporting conditional routing.
    This is the default flow type for most use cases.
    """
    
    async def run_stream(
        self,
        user_input: Optional[str] = None,
        **kwargs
    ) -> AsyncIterator[FlowEvent]:
        """Execute the flow's main loop with streaming events (sequential execution).
        
        Args:
            user_input: Optional initial user input to process.
            **kwargs: Additional context variables to add to flow context
            
        Yields:
            FlowEvent: Streaming events during execution.
            
        Raises:
            RuntimeError: If the flow is not in IDLE state at start.
        """
        if self.state != FlowState.IDLE:
            raise RuntimeError(f"Cannot run flow from state: {self.state}")
        
        # Initialize flow context
        self.context = {
            "user_input": user_input or "",
            "session_id": self.session_id,
            **kwargs
        }
        logger.info(f" {self.name} flow running with initial context: {self.context}")
        async with self.state_context(FlowState.RUNNING):
            # Create node map for quick lookup
            node_map = {node.id: node for node in self.nodes}
            executed_nodes = set()  # Track executed nodes to avoid infinite loops
            
            # Start with first node or use a starting node selector
            current_node_id = self._get_starting_node_id()
            step_count = 0
            
            logger.info(f" {self.name} starting execution with {len(self.nodes)} nodes")
            
            while current_node_id and current_node_id in node_map:
                # Avoid infinite loops
                if current_node_id in executed_nodes:
                    logger.warning(f"{self.name} detected node {current_node_id} already executed, stopping to avoid loop")
                    break
                
                node = node_map[current_node_id]
                executed_nodes.add(current_node_id)
                step_count += 1
                
                logger.info(f"Executing node {step_count}: {node.id} ({node.name})")
                
                # Emit flow step event
                flow_step_event = FlowEvent(
                    type="flow_step",
                    content=f"执行节点 {step_count}: {node.name}",
                    step=step_count,
                    total_steps=None,  # Dynamic routing means we don't know total steps
                    flow_id=self.flow_id,
                    node_id=node.id,
                    stage=node.name,
                )
                self.on_event(flow_step_event)
                yield flow_step_event
                
                # Execute node
                async for event in self.execute_node(node, self.context):
                    yield event
                
                # Determine next node
                # IMPORTANT: next_node_selector should return None if required context data is not found or invalid
                # This will end the flow gracefully instead of proceeding with missing data
                if node.next_node_selector:
                    next_node_id = node.next_node_selector(self.context)
                    if next_node_id:
                        logger.info(f" {self.name} routing to next node: {next_node_id} (selected by {node.id})")
                        current_node_id = next_node_id
                    else:
                        # Selector returned None (required data not found or invalid), end flow
                        logger.info(f" {self.name} node selector returned None (required context data missing/invalid), ending flow")
                        current_node_id = None  # End the flow
                else:
                    # No selector means this is a terminal node, end the flow
                    logger.info(f" {self.name} node '{node.id}' has no next_node_selector, ending flow")
                    current_node_id = None  # End the flow
            
            logger.info(f" {self.name} execution completed: executed {step_count} nodes")
            
            # Emit final event
            final_event = FlowEvent(
                type="final",
                content=None,
                flow_id=self.flow_id,
            )
            self.on_event(final_event)
            yield final_event
    
    def _get_starting_node_id(self) -> Optional[str]:
        """Get the starting node ID. Override in subclasses for custom starting logic."""
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

