"""Schema definitions for the application

This module contains all Pydantic models and enums used throughout the application.
"""

from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.utils.enums import MessageCategory


# =============================================================================
# Execution States
# =============================================================================

class AgentState(str, Enum):
    """Agent execution states (legacy, use ExecutionState for new code)"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class FlowState(str, Enum):
    """Flow execution states (legacy, use ExecutionState for new code)"""
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class ExecutionState(str, Enum):
    """Unified execution state for all Runnables
    
    This is the recommended state enum for new code.
    """
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    FINISHED = "finished"
    ERROR = "error"
    
    @classmethod
    def from_agent_state(cls, state: AgentState) -> "ExecutionState":
        """Convert from AgentState for compatibility"""
        mapping = {
            AgentState.IDLE: cls.IDLE,
            AgentState.RUNNING: cls.RUNNING,
            AgentState.FINISHED: cls.FINISHED,
            AgentState.ERROR: cls.ERROR,
        }
        return mapping.get(state, cls.IDLE)
    
    @classmethod
    def from_flow_state(cls, state: FlowState) -> "ExecutionState":
        """Convert from FlowState for compatibility"""
        mapping = {
            FlowState.IDLE: cls.IDLE,
            FlowState.RUNNING: cls.RUNNING,
            FlowState.PAUSED: cls.PAUSED,
            FlowState.FINISHED: cls.FINISHED,
            FlowState.ERROR: cls.ERROR,
        }
        return mapping.get(state, cls.IDLE)


class ControlSignal(str, Enum):
    """Control signals for execution flow"""
    TERMINATE = "terminate"  # Terminate all execution immediately
    PAUSE = "pause"          # Pause execution
    RESUME = "resume"        # Resume execution


# =============================================================================
# Tool and Function Types
# =============================================================================

class Function(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    """Represents a tool/function call in a message"""
    id: str
    type: str = "function"
    function: Function


# =============================================================================
# Message Types
# =============================================================================

class QueryMetadata(BaseModel):
    """Metadata for query results indicating if there are more messages available"""
    has_more_before: bool = Field(
        default=False,
        description="Whether there are more messages before the query range"
    )
    has_more_after: bool = Field(
        default=False,
        description="Whether there are more messages after the query range"
    )
    time_point: Optional[str] = Field(
        default=None,
        description="Time point used for around_time queries"
    )


class Message(BaseModel):
    """Represents a chat message in the conversation"""

    role: Literal["system", "user", "assistant", "tool"] = Field(...)
    content: Optional[str] = Field(default=None)
    tool_calls: Optional[List[ToolCall]] = Field(default=None)
    tool_name: Optional[str] = Field(
        default=None,
        description="Tool/function name (for tool messages)"
    )
    speaker: Optional[str] = Field(
        default=None,
        description="Speaker/agent name who sent this message"
    )
    tool_call_id: Optional[str] = Field(default=None)
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the message was created (ISO format: 'YYYY-MM-DD HH:MM:SS')"
    )
    category: int = Field(
        default=MessageCategory.NORMAL,
        description="Message category identifier (default: NORMAL=0)"
    )
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that this message is visible to (None means visible to all)"
    )

    def __add__(self, other) -> List["Message"]:
        """支持 Message + list 或 Message + Message 的操作"""
        if isinstance(other, list):
            return [self] + other
        elif isinstance(other, Message):
            return [self, other]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(self).__name__}' and '{type(other).__name__}'"
            )

    def __radd__(self, other) -> List["Message"]:
        """支持 list + Message 的操作"""
        if isinstance(other, list):
            return other + [self]
        else:
            raise TypeError(
                f"unsupported operand type(s) for +: '{type(other).__name__}' and '{type(self).__name__}'"
            )

    def to_dict(self) -> dict:
        """Convert message to dictionary format"""
        message = {"role": self.role}
        if self.content is not None:
            message["content"] = self.content
        if self.tool_calls is not None:
            tool_calls_list = []
            for tc in self.tool_calls:
                if isinstance(tc, dict):
                    tool_calls_list.append(tc)
                elif hasattr(tc, 'model_dump'):
                    tool_calls_list.append(tc.model_dump())
                elif hasattr(tc, 'dict'):
                    tool_calls_list.append(tc.dict())
                else:
                    tool_calls_list.append(tc)
            message["tool_calls"] = tool_calls_list
        if self.tool_name is not None:
            message["name"] = self.tool_name
        if self.speaker is not None:
            message["speaker"] = self.speaker
        if self.tool_call_id is not None:
            message["tool_call_id"] = self.tool_call_id
        if self.created_at is not None:
            message["created_at"] = self.created_at
        message["category"] = self.category
        if self.visible_for_characters is not None:
            message["visible_for_characters"] = self.visible_for_characters
        return message

    @classmethod
    def user_message(cls, content: str, speaker: Optional[str] = "user", created_at: Optional[str] = None, category: int = 0, visible_for_characters: Optional[List[str]] = None) -> "Message":
        """Create a user message"""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time()
        return cls(role="user", content=content, speaker=speaker, created_at=created_at, category=category, visible_for_characters=visible_for_characters)

    @classmethod
    def system_message(cls, content: str, speaker: Optional[str] = "system", created_at: Optional[str] = None, category: int = MessageCategory.NORMAL, visible_for_characters: Optional[List[str]] = None) -> "Message":
        """Create a system message"""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time()
        return cls(role="system", content=content, speaker=speaker, created_at=created_at, category=category, visible_for_characters=visible_for_characters)

    @classmethod
    def assistant_message(cls, content: Optional[str] = None, speaker: Optional[str] = "assistant", created_at: Optional[str] = None, category: int = MessageCategory.NORMAL, visible_for_characters: Optional[List[str]] = None) -> "Message":
        """Create an assistant message"""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time()
        return cls(role="assistant", content=content, speaker=speaker, created_at=created_at, category=category, visible_for_characters=visible_for_characters)

    @classmethod
    def tool_message(cls, content: str, tool_name: str, tool_call_id: str, speaker: Optional[str] = None, created_at: Optional[str] = None, category: int = MessageCategory.NORMAL, visible_for_characters: Optional[List[str]] = None) -> "Message":
        """Create a tool message"""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time()
        return cls(role="tool", content=content, tool_name=tool_name, tool_call_id=tool_call_id, speaker=speaker, created_at=created_at, category=category, visible_for_characters=visible_for_characters)

    @classmethod
    def from_tool_calls(
        cls, tool_calls: List[Any], content: Union[str, List[str]] = "", speaker: Optional[str] = "assistant", created_at: Optional[str] = None, category: int = MessageCategory.NORMAL, visible_for_characters: Optional[List[str]] = None, **kwargs
    ):
        """Create ToolCallsMessage from raw tool calls."""
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time()
        formatted_calls = [
            {"id": call.id, "function": call.function.model_dump(), "type": "function"}
            for call in tool_calls
        ]
        return cls(
            role="assistant", content=content, tool_calls=formatted_calls, speaker=speaker, created_at=created_at, category=category, visible_for_characters=visible_for_characters, **kwargs
        )


# =============================================================================
# Domain Models
# =============================================================================

class Scenario(BaseModel):
    """Represents a scenario window bound to a session"""
    session_id: str = Field(..., description="Owning session identifier")
    scenario_id: Optional[str] = Field(default=None, description="Business identifier for scenario")
    start_at: str = Field(..., description="Scenario start timestamp")
    end_at: str = Field(..., description="Scenario end timestamp")
    content: str = Field(default="", description="Scenario content")
    title: str = Field(default="", description="Scenario title")
    created_at: Optional[str] = Field(default=None, description="Timestamp when created")


class ScheduleEntry(BaseModel):
    """Represents a schedule entry"""
    entry_id: str = Field(..., description="Unique business identifier")
    session_id: str = Field(..., description="Owning session identifier")
    start_at: str = Field(..., description="Schedule start timestamp")
    end_at: str = Field(..., description="Schedule end timestamp")
    content: str = Field(default="", description="Schedule content")
    created_at: Optional[str] = Field(default=None, description="Timestamp when created")


class Relation(BaseModel):
    """Represents a relationship entry"""
    relation_id: str = Field(..., description="Unique business identifier")
    session_id: str = Field(..., description="Owning session identifier")
    name: str = Field(..., description="Name of the person/entity")
    knowledge: str = Field(default="", description="Knowledge about this relationship")
    progress: str = Field(default="", description="Progress/status of the relationship")
    created_at: Optional[str] = Field(default=None, description="Timestamp when created")


# =============================================================================
# Unified Execution Event
# =============================================================================

class ExecutionEvent(BaseModel):
    """Unified streaming event for all Runnables (Agents and Flows)
    
    This is the single event type used throughout the system.
    It replaces the previous AgentStreamEvent and FlowEvent.
    
    Event Types:
    - token: Content token (streaming text)
    - tool_status: Tool execution status update
    - tool_output: Tool execution output
    - step: Step marker (agent or flow step)
    - flow_step: Flow-specific step marker
    - final: Execution complete
    - error: Error occurred
    
    Attributes:
        type: Event type
        content: Event content (text, status message, etc.)
        step: Current step number
        total_steps: Total number of steps
        message_type: Source type (tool name, agent name, etc.)
        message_id: Source identifier (tool call ID, etc.)
        flow_id: Flow instance ID (for flow events)
        node_id: Node ID that generated this event
        stage: Flow stage name
        execution_path: Full execution path for nested runnables
        control: Control signal for flow control
        metadata: Additional metadata
    """
    
    # Event type - supports all legacy types
    type: Literal[
        "token",        # Content token (streaming text)
        "tool_status",  # Tool/status update
        "tool_output",  # Tool/output data
        "step",         # Step marker
        "flow_step",    # Flow step marker
        "final",        # Execution complete
        "error",        # Error occurred
    ] = Field(..., description="Event type")
    
    # Content
    content: Optional[str] = Field(
        default=None,
        description="Event content (token text, status message, etc.)"
    )
    
    # Step information
    step: Optional[int] = Field(
        default=None,
        description="Current step number"
    )
    total_steps: Optional[int] = Field(
        default=None,
        description="Total number of steps"
    )
    
    # Source identification (Agent compatibility)
    message_type: Optional[str] = Field(
        default=None,
        description="Source type (tool name, agent name, etc.)"
    )
    message_id: Optional[str] = Field(
        default=None,
        description="Source identifier (tool call ID, message ID, etc.)"
    )
    
    # Flow identification (Flow compatibility)
    flow_id: Optional[str] = Field(
        default=None,
        description="Flow instance ID"
    )
    node_id: Optional[str] = Field(
        default=None,
        description="Node ID that generated this event"
    )
    stage: Optional[str] = Field(
        default=None,
        description="Flow stage name (e.g., 'strategy', 'speak')"
    )
    
    # Execution path for nested Runnables
    execution_path: Optional[List[str]] = Field(
        default=None,
        description="Path of execution (e.g., ['flow_id', 'node_id', 'sub_flow_id'])"
    )
    
    # Control signal
    control: Optional[ControlSignal] = Field(
        default=None,
        description="Control signal for flow control"
    )
    
    # Additional metadata
    metadata: Optional[dict] = Field(
        default=None,
        description="Additional metadata"
    )
    
    def with_path(self, *path_segments: str) -> "ExecutionEvent":
        """Create a copy with path segments prepended
        
        Args:
            *path_segments: Path segments to prepend
            
        Returns:
            New ExecutionEvent with updated execution_path
        """
        current_path = self.execution_path or []
        new_path = list(path_segments) + current_path
        return self.model_copy(update={"execution_path": new_path})
    
    def with_flow_info(self, flow_id: str, node_id: Optional[str] = None, stage: Optional[str] = None) -> "ExecutionEvent":
        """Create a copy with flow information added
        
        Args:
            flow_id: Flow instance ID
            node_id: Optional node ID
            stage: Optional stage name
            
        Returns:
            New ExecutionEvent with flow info
        """
        updates = {"flow_id": flow_id}
        if node_id:
            updates["node_id"] = node_id
        if stage:
            updates["stage"] = stage
        return self.model_copy(update=updates)
    
    # =========================================================================
    # Factory methods
    # =========================================================================
    
    @classmethod
    def token(cls, content: str, **kwargs) -> "ExecutionEvent":
        """Create a token event"""
        return cls(type="token", content=content, **kwargs)
    
    @classmethod
    def status(cls, content: str, **kwargs) -> "ExecutionEvent":
        """Create a tool_status event"""
        return cls(type="tool_status", content=content, **kwargs)
    
    @classmethod
    def output(cls, content: str, **kwargs) -> "ExecutionEvent":
        """Create a tool_output event"""
        return cls(type="tool_output", content=content, **kwargs)
    
    @classmethod
    def error(cls, content: str, **kwargs) -> "ExecutionEvent":
        """Create an error event"""
        return cls(type="error", content=content, **kwargs)
    
    @classmethod
    def final(cls, **kwargs) -> "ExecutionEvent":
        """Create a final event"""
        return cls(type="final", **kwargs)
    
    @classmethod
    def step_event(cls, step: int, total_steps: Optional[int] = None, content: Optional[str] = None, **kwargs) -> "ExecutionEvent":
        """Create a step event"""
        return cls(type="step", step=step, total_steps=total_steps, content=content, **kwargs)
    
    @classmethod
    def flow_step_event(cls, content: str, flow_id: str, node_id: Optional[str] = None, stage: Optional[str] = None, **kwargs) -> "ExecutionEvent":
        """Create a flow_step event"""
        return cls(type="flow_step", content=content, flow_id=flow_id, node_id=node_id, stage=stage, **kwargs)


# =============================================================================
# Type Aliases for Backward Compatibility
# =============================================================================

# These aliases allow existing code to continue working without changes
AgentStreamEvent = ExecutionEvent
FlowEvent = ExecutionEvent
