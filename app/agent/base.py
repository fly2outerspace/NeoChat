from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from typing import AsyncIterator, Callable, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator

from app.llm import LLM
from app.logger import logger
from app.memory import Memory
from app.schema import AgentState, AgentStreamEvent, Message
from app.utils import get_current_time

class BaseAgent(BaseModel, ABC):
    """Abstract base class for managing agent state and execution.

    Provides foundational functionality for state transitions, memory management,
    and a step-based execution loop. Subclasses must implement the `step` method.
    """

    # Core attributes
    session_id: str = Field(..., description="Session ID for this agent instance")
    name: str = Field(..., description="Unique name of the agent")
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
    state: AgentState = Field(
        default=AgentState.IDLE, description="Current agent state"
    )

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
            # If memory exists but session_id doesn't match, create new memory with correct session_id
            self.memory = Memory(session_id=self.session_id)
        logger.info(f"initialize agent: {self.name} with session_id: {self.session_id}")
        return self


    @asynccontextmanager
    async def state_context(self, new_state: AgentState):
        """Context manager for safe agent state transitions.

        Args:
            new_state: The state to transition to during the context.

        Yields:
            None: Allows execution within the new state.

        Raises:
            ValueError: If the new_state is invalid.
        """
        if not isinstance(new_state, AgentState):
            raise ValueError(f"Invalid state: {new_state}")

        previous_state = self.state
        self.state = new_state
        try:
            yield
        except Exception as e:
            self.state = AgentState.ERROR  # Transition to ERROR on failure
            raise e
        finally:
            self.state = previous_state  # Revert to previous state

    def handle_user_input(self, request: str, **kwargs):
        """Handle user input with optional parameters
        
        Args:
            request: User input text
            **kwargs: Optional parameters (e.g., input_mode for Character agent)
        
        Returns:
            Message: Created user message
        """
        created_at = get_current_time()
        user_msg = Message.user_message(request, speaker="user", created_at=created_at, visible_for_characters=self.visible_for_characters)
        self.memory.add_message(user_msg)

    async def run(self, request: Optional[str] = None) -> str:
        """Execute the agent's main loop asynchronously.

        Args:
            request: Optional initial user request to process.

        Returns:
            A string summarizing the execution results.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        # For backward compatibility, collect events and return final result
        buffer = []
        async for event in self.run_stream(request):
            if event.type == "token" and event.content:
                buffer.append(event.content)
        return "".join(buffer) if buffer else self.result

    async def run_stream(
        self, request: Optional[str] = None, **kwargs
    ) -> AsyncIterator[AgentStreamEvent]:
        """Execute the agent's main loop with streaming events.

        Args:
            request: Optional initial user request to process.
            **kwargs: Optional parameters to pass to handle_user_input (e.g., input_mode for Character agent)

        Yields:
            AgentStreamEvent: Streaming events during execution.

        Raises:
            RuntimeError: If the agent is not in IDLE state at start.
        """
        if self.state != AgentState.IDLE:
            raise RuntimeError(f"Cannot run agent from state: {self.state}")

        if request:
            self.handle_user_input(request, **kwargs)

        async def emit(event: AgentStreamEvent):
            """Helper to emit events"""
            yield event

        async with self.state_context(AgentState.RUNNING):
            while (
                self.current_step < self.max_steps and self.state != AgentState.FINISHED
            ):
                self.current_step += 1
                logger.info(f"Executing step {self.current_step}/{self.max_steps}")
                
                # Emit step start event
                async for event in emit(
                    AgentStreamEvent(
                        type="step",
                        content=f"步骤 {self.current_step}/{self.max_steps}",
                        step=self.current_step,
                        total_steps=self.max_steps,
                    )
                ):
                    yield event

                # Execute step with streaming support
                async for event in self.step_stream():
                    yield event

                # Check for stuck state
                if self.is_stuck():
                    self.handle_stuck_state()

            if self.current_step >= self.max_steps:
                logger.warning(f"Terminated: Reached max steps ({self.max_steps})")

        # Emit final event (no additional content to avoid duplicate output)
        yield AgentStreamEvent(
            type="final",
            content=None,
        )

    async def step_stream(self) -> AsyncIterator[AgentStreamEvent]:
        """Execute a single step with streaming events.
        
        Default implementation yields no events.
        Subclasses should override this to emit streaming events.
        """
        # Empty generator - subclasses should override
        return
        yield  # Make this an async generator (unreachable but needed for type)

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

        # Count identical content occurrences
        duplicate_count = sum(
            1
            for msg in reversed(messages[:-1])
            if msg.role == "assistant" and msg.content == last_message.content
        )

        return duplicate_count >= self.duplicate_threshold

    @property
    def messages(self) -> List[Message]:
        """Retrieve all messages acquired during this agent's lifecycle.
        
        This property returns all messages that have been collected since the agent
        was initialized. It does not include messages that existed before the agent
        was created.
        """
        return self.memory.messages

    @messages.setter
    def messages(self, value: List[Message]):
        """Set the list of messages in the agent's memory.
        
        Note: Setting messages directly updates the memory instance's messages list.
        For persistence, use memory.add_message() or memory.set_messages() instead.
        """
        self.memory.messages = value