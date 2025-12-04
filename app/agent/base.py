"""Base Agent - Leaf Runnable implementation

BaseAgent is the abstract base class for all agents. It extends Runnable
to be compatible with the unified execution framework while maintaining
backward compatibility with the existing agent interface.

An Agent is a leaf Runnable - it cannot contain child Runnables.
It executes using an LLM and optional tools.
"""

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, List, Optional, Union

from pydantic import Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.memory import Memory
from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.schema import (
    ExecutionEvent,
    ExecutionState,
    Message,
)
from app.utils import get_current_time


class BaseAgent(Runnable, ABC):
    """Abstract base class for managing agent state and execution.

    BaseAgent extends Runnable to be part of the unified execution framework.
    It provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    
    As a Runnable, BaseAgent can:
    1. Execute independently
    2. Be composed with other Runnables using | and & operators
    3. Be used as a node in a Flow
    
    Attributes:
        session_id: Session identifier for this agent
        name: Human-readable agent name (inherited from Runnable)
        description: Optional agent description
        llm: Language model instance
        memory: Agent's memory store
        state: Current execution state (uses ExecutionState)
        max_steps: Maximum steps before termination
        current_step: Current step in execution
    """

    # Core attributes
    session_id: str = Field(..., description="Session ID for this agent instance")
    description: Optional[str] = Field(None, description="Optional agent description")

    # Prompts
    system_prompt: Optional[str] = Field(
        None, description="System-level instruction prompt"
    )
    next_step_prompt: Optional[str] = Field(
        None, description="Prompt for determining next action"
    )

    # Dependencies
    llm: LLM = Field(default_factory=LLM, description="Language model instance")
    memory: Memory = Field(default_factory=Memory, description="Agent's memory store")

    # Execution control
    max_steps: int = Field(default=10, description="Maximum steps before termination")
    current_step: int = Field(default=0, description="Current step in execution")

    duplicate_threshold: int = 2

    result: str = ""
    
    character_id: Optional[str] = Field(
        default=None,
        description="Character ID for this agent (used for filtering messages when querying)"
    )
    
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that messages from this agent should be visible to (None means visible to all)"
    )

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"  # Allow extra fields for flexibility in subclasses

    @model_validator(mode="after")
    def initialize_agent(self) -> "BaseAgent":
        """Initialize agent with default settings if not provided."""
        if self.llm is None or not isinstance(self.llm, LLM):
            self.llm = LLM(config_name=self.name.lower())
        if not isinstance(self.memory, Memory):
            self.memory = Memory(session_id=self.session_id)
        elif self.memory.session_id != self.session_id:
            self.memory = Memory(session_id=self.session_id)
        
        config_name = getattr(self.llm, 'config_name', 'custom')
        model_name = getattr(self.llm, 'model', 'unknown')

        logger.info(f"initialize agent: {self.id} with session_id: {self.session_id}, LLM config: {config_name}, model: {model_name}")
        return self

    @asynccontextmanager
    async def state_context(self, new_state: ExecutionState):
        """Context manager for safe agent state transitions.

        Args:
            new_state: The ExecutionState to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, ExecutionState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = ExecutionState.ERROR
            raise e
        finally:
            self.state = previous_state

    def handle_user_input(self, context: ExecutionContext):
        """Handle user input from ExecutionContext
        
        Args:
            context: ExecutionContext containing user_input and additional data
        
        Subclasses can override to extract additional parameters from context.data
        """
        request = context.user_input
        if request:
            created_at = get_current_time()
            user_msg = Message.user_message(request, speaker="user", created_at=created_at, visible_for_characters=self.visible_for_characters)
            self.memory.add_message(user_msg)

    async def run_stream(
        self,
        context: Union[ExecutionContext, str, None] = None,
        **kwargs
    ) -> AsyncIterator[ExecutionEvent]:
        """Execute the agent's main loop with streaming events.
        
        This method implements the Runnable interface using ExecutionContext,
        while also supporting the legacy string-based interface for backward
        compatibility.

        Args:
            context: ExecutionContext, or string (legacy), or None
            **kwargs: Additional parameters (for legacy compatibility)

        Yields:
            ExecutionEvent: Streaming events during execution.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        # Normalize input to ExecutionContext
        if isinstance(context, ExecutionContext):
            exec_context = context
        elif isinstance(context, str):
            exec_context = ExecutionContext(
                session_id=self.session_id,
                user_input=context,
                data=kwargs
            )
        else:
            exec_context = ExecutionContext(
                session_id=self.session_id,
                data=kwargs
            )
        
        if self.state != ExecutionState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if exec_context.user_input:
            self.handle_user_input(exec_context)

        async with self.state_context(ExecutionState.RUNNING):
            while (
                self.current_step < self.max_steps and self.state != ExecutionState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                
                # Emit step start event
                yield ExecutionEvent(
                        type="step",
                        content=f"步骤 {self.current_step}/{self.max_steps}",
                        step=self.current_step,
                        total_steps=self.max_steps,
                    )

                # Execute step with streaming support
                async for event in self.step_stream():
                    yield event

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

            if self.current_step >= self.max_steps:
                logger.warning(f"Terminated: Reached max steps ({self.max_steps})")

        # Emit final event
        yield ExecutionEvent(type="final")

    async def run(self, request: Optional[str] = None, **kwargs) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.
            **kwargs: Additional parameters

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        buffer = []
        async for event in self.run_stream(request, **kwargs):
            if event.type == "token" and event.content:
                buffer.append(event.content)
        return "".join(buffer) if buffer else self.result

    async def step_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Execute a single step with streaming events.
        
        Default implementation yields no events.
        Subclasses should override this to emit streaming events.
        
        Yields:
            ExecutionEvent: Events from this step
        """
        return
        yield  # Make this an async generator

    def handle_stuck_state(self):
        """Handle stuck state by adding a prompt to change strategy"""
        stuck_prompt = "\
        Observed duplicate responses. Consider new strategies and avoid repeating ineffective paths already attempted."
        self.next_step_prompt = f"{stuck_prompt}\n{self.next_step_prompt}"
        logger.warning(f"Agent detected stuck state. Added prompt: {stuck_prompt}")

    def is_stuck(self) -> bool:
        """Check if the agent is stuck in a loop by detecting duplicate content"""
        messages = self.messages
        if len(messages) < 2:
            return False

        last_message = messages[-1]
        if not last_message.content:
            return False

        duplicate_count = sum(
            1
            for msg in reversed(messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """Retrieve all messages acquired during this agent's lifecycle."""
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory."""
        self.memory.messages = value
