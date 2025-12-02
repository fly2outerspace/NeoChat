from datetime import datetime
from enum import Enum
from typing import Any, List, Literal, Optional, Union

from pydantic import BaseModel, Field

from app.utils.enums import MessageCategory


class AgentState(str, Enum):
    """Agent execution states"""

    IDLE = "IDLE"
    RUNNING = "RUNNING"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class Function(BaseModel):
    name: str
    arguments: str


class ToolCall(BaseModel):
    """Represents a tool/function call in a message"""

    id: str
    type: str = "function"
    function: Function


class QueryMetadata(BaseModel):
    """Metadata for query results indicating if there are more messages available"""
    
    has_more_before: bool = Field(
        default=False,
        description="Whether there are more messages before the query range (for around_time queries)"
    )
    has_more_after: bool = Field(
        default=False,
        description="Whether there are more messages after the query range"
    )
    time_point: Optional[str] = Field(
        default=None,
        description="Time point used for around_time queries (for reference)"
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
            # Handle both dict format (from Message.from_tool_calls) and ToolCall objects
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
            message["name"] = self.tool_name  # Keep "name" for OpenAI API compatibility
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
        """Create ToolCallsMessage from raw tool calls.

        Args:
            tool_calls: Raw tool calls from LLM
            content: Optional message content
            speaker: Optional speaker/agent name (default: "assistant")
            created_at: Optional timestamp. If None, uses current time.
            category: Message category identifier (default: 0)
            visible_for_characters: Optional list of character IDs that this message is visible to
        """
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


class Scenario(BaseModel):
    """Represents a scenario window bound to a session"""

    session_id: str = Field(..., description="Owning session identifier")
    scenario_id: Optional[str] = Field(
        default=None,
        description="Business identifier for scenario",
    )
    start_at: str = Field(..., description="Scenario start timestamp")
    end_at: str = Field(..., description="Scenario end timestamp")
    content: str = Field(default="", description="Scenario content")
    title: str = Field(default="", description="Scenario title")
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the scenario record was created",
    )


class ScheduleEntry(BaseModel):
    """Represents a schedule entry"""

    entry_id: str = Field(..., description="Unique business identifier for the schedule entry")
    session_id: str = Field(..., description="Owning session identifier")
    start_at: str = Field(..., description="Schedule start timestamp")
    end_at: str = Field(..., description="Schedule end timestamp")
    content: str = Field(default="", description="Schedule content")
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the schedule record was created",
    )


class Relation(BaseModel):
    """Represents a relationship entry"""

    relation_id: str = Field(..., description="Unique business identifier for the relation")
    session_id: str = Field(..., description="Owning session identifier")
    name: str = Field(..., description="Name of the person/entity in the relationship")
    knowledge: str = Field(default="", description="Knowledge about this relationship")
    progress: str = Field(default="", description="Progress/status of the relationship")
    created_at: Optional[str] = Field(
        default=None,
        description="Timestamp when the relation record was created",
    )


class AgentStreamEvent(BaseModel):
    """Streaming event emitted during agent execution"""
    
    type: Literal["token", "tool_status", "tool_output", "step", "final", "error"] = Field(
        ..., description="Event type"
    )
    content: Optional[str] = Field(
        default=None, description="Event content (token text, status message, etc.)"
    )
    step: Optional[int] = Field(
        default=None, description="Current step number (for step events)"
    )
    total_steps: Optional[int] = Field(
        default=None, description="Total steps (for step events)"
    )
    message_type: Optional[str] = Field(
        default=None, description="Message type (e.g., tool name, message type)"
    )
    message_id: Optional[str] = Field(
        default=None, description="Message ID (e.g., tool call ID, message ID)"
    )
    metadata: Optional[dict] = Field(
        default=None, description="Additional metadata"
    )


class FlowState(str, Enum):
    """Flow execution states"""
    
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FINISHED = "FINISHED"
    ERROR = "ERROR"


class FlowEvent(BaseModel):
    """Streaming event emitted during flow execution
    
    Extends AgentStreamEvent with flow-specific metadata.
    Compatible with AgentStreamEvent for seamless integration.
    """
    
    type: Literal["token", "tool_status", "tool_output", "step", "final", "error", "flow_step"] = Field(
        ..., description="Event type"
    )
    content: Optional[str] = Field(
        default=None, description="Event content (token text, status message, etc.)"
    )
    step: Optional[int] = Field(
        default=None, description="Current step number (for step events)"
    )
    total_steps: Optional[int] = Field(
        default=None, description="Total steps (for step events)"
    )
    message_type: Optional[str] = Field(
        default=None, description="Message type (e.g., tool name, message type)"
    )
    message_id: Optional[str] = Field(
        default=None, description="Message ID (e.g., tool call ID, message ID)"
    )
    metadata: Optional[dict] = Field(
        default=None, description="Additional metadata"
    )
    # Flow-specific fields
    flow_id: Optional[str] = Field(
        default=None, description="Flow instance ID"
    )
    node_id: Optional[str] = Field(
        default=None, description="Node ID that generated this event"
    )
    stage: Optional[str] = Field(
        default=None, description="Flow stage name (e.g., 'planner', 'executor')"
    )
    
    def to_agent_event(self) -> AgentStreamEvent:
        """Convert FlowEvent to AgentStreamEvent for compatibility"""
        return AgentStreamEvent(
            type=self.type,
            content=self.content,
            step=self.step,
            total_steps=self.total_steps,
            message_type=self.message_type,
            message_id=self.message_id,
            metadata=self.metadata,
        )