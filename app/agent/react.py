"""ReAct Agent - Think-Act pattern implementation

ReActAgent implements the ReAct (Reasoning and Acting) pattern,
where the agent alternates between thinking and acting phases.
"""

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.llm import LLM
from app.memory import Memory
from app.schema import ExecutionEvent, ExecutionState


class ReActAgent(BaseAgent, ABC):
    """Base class for ReAct pattern agents
    
    ReAct agents follow a think-act loop:
    1. Think: Analyze current state and decide next action
    2. Act: Execute the decided action
    
    This class extends BaseAgent and thus inherits from Runnable,
    making it composable with other Runnables.
    
    Attributes:
        name: Agent name
        description: Optional agent description
        system_prompt: System-level instruction prompt
        next_step_prompt: Prompt for determining next action
        llm: Language model instance
        memory: Agent's memory store
        max_steps: Maximum steps before termination
    """
    
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action
        
        Returns:
            True if action should be taken, False otherwise
        """
        pass

    @abstractmethod
    async def act(self) -> str:
        """Execute decided actions
        
        Returns:
            Result of the action
        """
        pass
    
    async def step_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Execute a single step with streaming events.
        
        Implements the think-act cycle with streaming support.
        
        Yields:
            ExecutionEvent: Events during step execution
        """
        # Emit thinking status
        yield ExecutionEvent(
            type="tool_status",
            content="🧠 正在思考...",
            step=self.current_step,
            total_steps=self.max_steps,
        )
        
        # Call think_stream which yields events
        should_act = None
        async for event in self.think_stream():
            yield event
            # Check if event contains result in metadata
            if event.metadata and 'should_act' in event.metadata:
                should_act = event.metadata['should_act']
        
        # If we didn't get result from events, call think() directly
        if should_act is None:
            should_act = await self.think()
            yield ExecutionEvent(
                type="tool_status",
                content="✅ 思考完成",
                step=self.current_step,
                total_steps=self.max_steps,
            )
        
        if not should_act:
            return
        
        # Execute actions with streaming
        async for event in self.act_stream():
            yield event
    
    async def think_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Think with streaming events.
        
        Subclasses should override this to emit streaming events during thinking.
        Default implementation just calls think() and yields nothing.
        
        Yields:
            ExecutionEvent: Events during thinking
        """
        await self.think()
        return
        yield  # Make this an async generator
    
    async def act_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Act with streaming events.
        
        Subclasses should override this to emit streaming events during action execution.
        Default implementation just calls act() and yields nothing.
        
        Yields:
            ExecutionEvent: Events during action
        """
        await self.act()
        return
        yield  # Make this an async generator
