from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.llm import LLM
from app.memory import Memory
from app.schema import AgentState, AgentStreamEvent


class ReActAgent(BaseAgent, ABC):
    name: str
    description: Optional[str] = None

    system_prompt: Optional[str] = None
    next_step_prompt: Optional[str] = None

    llm: Optional[LLM] = Field(default_factory=LLM)
    memory: Memory = Field(default_factory=Memory)
    state: AgentState = AgentState.IDLE

    max_steps: int = 10
    current_step: int = 0

    @abstractmethod
    async def think(self) -> bool:
        """Process current state and decide next action"""

    @abstractmethod
    async def act(self) -> str:
        """Execute decided actions"""
    
    async def step_stream(self) -> AsyncIterator[AgentStreamEvent]:
        """Execute a single step with streaming events."""
        # Emit thinking status
        yield AgentStreamEvent(
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
            # Emit completion event if we had to fall back
            yield AgentStreamEvent(
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
    
    async def think_stream(self) -> AsyncIterator[AgentStreamEvent]:
        """Think with streaming events. Should yield events.
        
        Subclasses should override this to emit streaming events during thinking.
        Default implementation just calls think() and yields nothing.
        """
        await self.think()
        return
        yield
    
    async def act_stream(self) -> AsyncIterator[AgentStreamEvent]:
        """Act with streaming events.
        
        Subclasses should override this to emit streaming events during action execution.
        Default implementation just calls act() and yields nothing.
        """
        await self.act()
        return
        yield
