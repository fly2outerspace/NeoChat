"""User Agent - Handles user input processing

UserAgent is a specialized agent that focuses on processing and formatting user input.
It extends BaseAgent to handle user messages with proper categorization and formatting.
"""

from typing import AsyncIterator, List, Optional

from pydantic import Field

from app.agent.base import BaseAgent
from app.logger import logger
from app.memory import Memory
from app.runnable.context import ExecutionContext
from app.schema import ExecutionEvent, ExecutionEventType, ExecutionState, Message
from app.utils import get_current_time
from app.utils.enums import InputMode
from app.utils.mapping import get_category_from_input_mode


class UserAgent(BaseAgent):
    """User agent class that handles user input processing and formatting
    
    This agent specializes in:
    1. Processing user input from ExecutionContext
    2. Formatting user messages based on input mode
    3. Adding properly categorized user messages to memory
    """

    name: str = "user"
    description: str = "an agent that processes and formats user input."
    
    # Set max_steps to 1 since we only process input
    max_steps: int = 1
    
    # History messages for formatting context
    history_messages: List[Message] = Field(default_factory=list)

    # Flag to indicate if next node should be skipped (set after processing COMMAND input)
    skip_next_node: bool = False

    def handle_user_input(self, context: ExecutionContext):
        """Handle user input from ExecutionContext
        
        This method processes user input similar to StrategyAgent:
        1. Gets input_mode from context.data
        2. Determines message category based on input_mode
        3. Creates and adds user message to memory
        4. Sets skip_next_node flag if input_mode is COMMAND
        
        Args:
            context: ExecutionContext containing user_input and input_mode
        """
        request = context.user_input
        
        current_time = get_current_time(session_id=self.session_id) if self.session_id else get_current_time()
        
        # Load history messages for formatting context
        self.history_messages, _ = Memory.get_messages_around_time(
            self.session_id, 
            time_point=current_time, 
            hours=24.0, 
            max_messages=150, 
            character_id=self.character_id
        )

        # Get input_mode from context.data (default to PHONE if not found)
        if "input_mode" not in context.data:
            logger.warning(
                f" {self.name} input_mode not found in context.data, using default input_mode: {InputMode.PHONE}"
            )
            input_mode = InputMode.PHONE
        else:
            input_mode = context.data.get("input_mode")
        
        # Check if this is a COMMAND mode - skip next node if so
        if input_mode == InputMode.COMMAND:
            self.skip_next_node = True
            logger.info(f" {self.name} detected COMMAND mode, will skip character agent")
        
        # Only add message if not SKIP mode and request exists
        if input_mode != InputMode.SKIP and request:
            category = get_category_from_input_mode(input_mode)
            user_msg = Message.user_message(
                request,
                speaker="user",
                created_at=current_time,
                category=category,
                visible_for_characters=self.visible_for_characters
            )
            self.memory.add_message(user_msg)
            logger.info(f" {self.name} processed user input: {request[:50]}... (category: {category})")

    async def step_stream(self) -> AsyncIterator[ExecutionEvent]:
        """Execute a single step - processes user input
        
        Since UserAgent only processes input and doesn't generate output,
        this method simply confirms that input processing is complete.
        
        Yields:
            ExecutionEvent: Status event indicating completion
        """
        # User input has already been processed in handle_user_input()
        # Just emit a status event to indicate processing is complete
        yield ExecutionEvent(
            type=ExecutionEventType.STATUS,
            content="✅ 用户输入已处理",
            step=self.current_step,
            total_steps=self.max_steps,
        )
        
        # Mark as finished since we only process input
        self.state = ExecutionState.FINISHED
        logger.info(f" {self.name} completed processing user input")

