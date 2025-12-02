"""Request and response schemas for API"""
from typing import List, Optional, Literal, Dict, Any

from pydantic import BaseModel, Field

from app.utils.enums import InputMode


class ToolOutputMessage(BaseModel):
    tool_name: str = Field(..., description="Tool name that produced this output")
    content: str = Field(default="", description="Text content of the tool output")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID associated with the output")


class ChatMessage(BaseModel):
    """Chat message model compatible with OpenAI format"""
    role: str = Field(..., description="Message role: system, user, assistant, tool")
    content: Optional[str] = Field(None, description="Message content")
    name: Optional[str] = Field(None, description="Tool name for tool messages")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID for tool messages")
    tool_outputs: Optional[List[ToolOutputMessage]] = Field(
        default=None, description="Additional tool outputs associated with this message"
    )


class CharacterInfo(BaseModel):
    """Character information for chat request"""
    character_id: str = Field(..., description="Character ID")
    name: str = Field(..., description="Character name")
    roleplay_prompt: Optional[str] = Field(None, description="Roleplay prompt")


class ModelInfo(BaseModel):
    """Model configuration information for chat request"""
    model_id: str = Field(..., description="Model ID")
    name: str = Field(..., description="Model configuration name")
    provider: str = Field(..., description="Provider name")
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: Optional[str] = Field(None, description="API key")
    max_tokens: int = Field(4096, description="Maximum tokens")
    temperature: float = Field(1.0, description="Sampling temperature")
    api_type: str = Field("openai", description="API type")


class ChatCompletionRequest(BaseModel):
    """Chat completion request model"""
    user_input: str = Field(..., description="User input text (single string instead of messages list)")
    input_mode: Optional[InputMode] = Field(
        default=InputMode.PHONE, 
        description="Input mode: phone (手机通信), in_person (面对面说话), inner_voice (角色内心活动), command (系统指令)"
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: str = Field(..., description="Session ID for conversation history (required)")
    character: Optional[CharacterInfo] = Field(None, description="Character information (optional)")
    model_info: Optional[ModelInfo] = Field(None, description="Model configuration (optional, if not provided, uses default config from config.toml)")
    participants: Optional[List[str]] = Field(None, description="List of character IDs that messages from this request should be visible to (None means visible to all)")


class ChatCompletionChoice(BaseModel):
    """Chat completion choice"""
    index: int = 0
    message: ChatMessage
    finish_reason: Optional[str] = None


class ChatCompletionResponse(BaseModel):
    """Chat completion response model"""
    id: str = Field(default="chatcmpl-default", description="Response ID")
    object: str = Field(default="chat.completion", description="Object type")
    created: int = Field(default=0, description="Creation timestamp")
    model: str = Field(default="gpt-4o", description="Model name")
    choices: List[ChatCompletionChoice] = Field(..., description="Completion choices")
    usage: Optional[dict] = Field(default=None, description="Token usage")


class SearchRequest(BaseModel):
    """Search request model"""
    query: str = Field(..., description="Search query (supports Chinese and English)")
    session_id: Optional[str] = Field(None, description="Filter by session ID")
    role: Optional[str] = Field(None, description="Filter by message role")
    category: Optional[int] = Field(None, description="Filter by message category")
    limit: int = Field(default=20, ge=1, le=100, description="Maximum number of results")
    offset: int = Field(default=0, ge=0, description="Offset for pagination")
    sort: Optional[List[str]] = Field(None, description="Sort order (e.g., ['created_at:desc'])")


class SearchResult(BaseModel):
    """Search result item"""
    id: int = Field(..., description="Message ID")
    session_id: str = Field(..., description="Session ID")
    role: str = Field(..., description="Message role")
    content: Optional[str] = Field(None, description="Message content")
    tool_name: Optional[str] = Field(None, description="Tool/function name")
    speaker: Optional[str] = Field(None, description="Speaker/agent name")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID")
    created_at: str = Field(..., description="Creation timestamp")
    category: int = Field(default=0, description="Message category")


class SearchResponse(BaseModel):
    """Search response model"""
    query: str = Field(..., description="Search query")
    hits: List[SearchResult] = Field(..., description="Search results")
    estimated_total_hits: int = Field(..., description="Estimated total number of results")
    limit: int = Field(..., description="Maximum number of results")
    offset: int = Field(..., description="Offset for pagination")
    processing_time_ms: Optional[float] = Field(None, description="Processing time in milliseconds")


class ScenarioSearchRequest(BaseModel):
    """Search scenarios"""
    query: str = Field(..., description="Full-text query against scenario content")
    session_id: Optional[str] = Field(None, description="Filter by session id")
    scenario_id: Optional[str] = Field(None, description="Filter by scenario id")
    start_from: Optional[str] = Field(None, description="Filter by start_at >= value")
    start_to: Optional[str] = Field(None, description="Filter by start_at <= value")
    end_from: Optional[str] = Field(None, description="Filter by end_at >= value")
    end_to: Optional[str] = Field(None, description="Filter by end_at <= value")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: Optional[List[str]] = Field(None, description="Sort order, e.g., ['start_at:asc']")


class ScenarioSearchResult(BaseModel):
    scenario_id: str
    session_id: str
    content: Optional[str] = None
    start_at: str
    end_at: str
    created_at: Optional[str] = None


class ScenarioSearchResponse(BaseModel):
    query: str
    hits: List[ScenarioSearchResult]
    estimated_total_hits: int
    limit: int
    offset: int
    processing_time_ms: Optional[float] = None


class ScheduleSearchRequest(BaseModel):
    """Search schedule entries"""
    query: str = Field(..., description="Full-text query against schedule content")
    session_id: Optional[str] = Field(None, description="Filter by session id")
    entry_id: Optional[str] = Field(None, description="Filter by entry id")
    start_from: Optional[str] = Field(None, description="Filter by start_at >= value")
    start_to: Optional[str] = Field(None, description="Filter by start_at <= value")
    end_from: Optional[str] = Field(None, description="Filter by end_at >= value")
    end_to: Optional[str] = Field(None, description="Filter by end_at <= value")
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    sort: Optional[List[str]] = Field(None, description="Sort order, e.g., ['start_at:asc']")


class ScheduleSearchResult(BaseModel):
    entry_id: str
    session_id: str
    content: Optional[str] = None
    start_at: str
    end_at: str
    created_at: Optional[str] = None


class ScheduleSearchResponse(BaseModel):
    query: str
    hits: List[ScheduleSearchResult]
    estimated_total_hits: int
    limit: int
    offset: int
    processing_time_ms: Optional[float] = None


class ScenarioCreateRequest(BaseModel):
    """Create or upsert a scenario"""
    session_id: str = Field(..., description="Owning session identifier")
    scenario_id: Optional[str] = Field(
        default=None, description="Business identifier for scenario; auto-generated if omitted"
    )
    start_at: str = Field(..., description="Scenario start timestamp")
    end_at: str = Field(..., description="Scenario end timestamp")
    content: Optional[str] = Field(default="", description="Scenario content")


class ScheduleEntryCreateRequest(BaseModel):
    """Create or upsert a schedule entry"""
    session_id: str = Field(..., description="Owning session identifier")
    entry_id: str = Field(..., description="Business identifier for schedule entry")
    start_at: str = Field(..., description="Schedule entry start timestamp")
    end_at: str = Field(..., description="Schedule entry end timestamp")
    content: Optional[str] = Field(default="", description="Schedule entry content")


class CharacterCreateRequest(BaseModel):
    """Create a character card"""
    name: str = Field(..., description="Character name")
    roleplay_prompt: Optional[str] = Field(None, description="Roleplay prompt text")
    avatar: Optional[str] = Field(None, description="Base64 encoded image string")
    character_id: Optional[str] = Field(None, description="Optional character_id (auto-generated if omitted)")


class CharacterUpdateRequest(BaseModel):
    """Update a character card"""
    name: Optional[str] = Field(None, description="Character name")
    roleplay_prompt: Optional[str] = Field(None, description="Roleplay prompt text")
    avatar: Optional[str] = Field(None, description="Base64 encoded image string")


class CharacterResponse(BaseModel):
    """Character card response model"""
    id: int = Field(..., description="Database ID")
    character_id: str = Field(..., description="Character ID (business identifier)")
    name: str = Field(..., description="Character name")
    roleplay_prompt: Optional[str] = Field(None, description="Roleplay prompt text")
    avatar: Optional[str] = Field(None, description="Base64 encoded image string")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class CharacterListResponse(BaseModel):
    """Character list response model"""
    characters: List[CharacterResponse] = Field(..., description="List of characters")


class ModelCreateRequest(BaseModel):
    """Create a model configuration"""
    name: str = Field(..., description="Model configuration name")
    provider: str = Field(..., description="Provider name (e.g., OpenAI, DeepSeek, xAI)")
    model: str = Field(..., description="Model name (e.g., gpt-4o, deepseek-chat)")
    base_url: str = Field(..., description="API base URL")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted)")
    max_tokens: int = Field(default=4096, description="Maximum tokens")
    temperature: float = Field(default=1.0, description="Temperature parameter")
    api_type: str = Field(default="openai", description="API type")
    model_id: Optional[str] = Field(None, description="Optional model_id (auto-generated if omitted)")


class ModelUpdateRequest(BaseModel):
    """Update a model configuration"""
    name: Optional[str] = Field(None, description="Model configuration name")
    provider: Optional[str] = Field(None, description="Provider name")
    model: Optional[str] = Field(None, description="Model name")
    base_url: Optional[str] = Field(None, description="API base URL")
    api_key: Optional[str] = Field(None, description="API key (will be encrypted if provided)")
    max_tokens: Optional[int] = Field(None, description="Maximum tokens")
    temperature: Optional[float] = Field(None, description="Temperature parameter")
    api_type: Optional[str] = Field(None, description="API type")


class ModelResponse(BaseModel):
    """Model configuration response model"""
    id: int = Field(..., description="Database ID")
    model_id: str = Field(..., description="Model ID (business identifier)")
    name: str = Field(..., description="Model configuration name")
    provider: str = Field(..., description="Provider name")
    model: str = Field(..., description="Model name")
    base_url: str = Field(..., description="API base URL")
    api_key: Optional[str] = Field(None, description="API key (only returned when explicitly requested)")
    has_api_key: Optional[bool] = Field(None, description="Whether API key exists (for list responses)")
    max_tokens: int = Field(..., description="Maximum tokens")
    temperature: float = Field(..., description="Temperature parameter")
    api_type: str = Field(..., description="API type")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")


class ModelListResponse(BaseModel):
    """Model list response model"""
    models: List[ModelResponse] = Field(..., description="List of models")


class TimeActionModel(BaseModel):
    """Single time transformation action"""
    type: Literal["scale", "offset", "freeze"] = Field(..., description="Action type")
    value: float = Field(..., description="Primary value (seconds for offset, multiplier for scale)")
    note: Optional[str] = Field(None, description="Optional description")


class TimeClockRequest(BaseModel):
    """Update session clock configuration"""
    base_virtual: Optional[str] = Field(None, description="Explicit virtual base time (YYYY-MM-DD HH:MM:SS)")
    actions: Optional[List[TimeActionModel]] = Field(None, description="Full action chain to apply")
    reset_actions: bool = Field(False, description="Whether to clear existing actions before applying new ones")
    rebase: bool = Field(True, description="Re-anchor base time at current virtual time before applying actions")
    # Legacy fields for backward compatibility
    mode: Optional[str] = Field(None, description="[LEGACY] Time mode: 'real', 'offset', 'fixed', or 'scaled'")
    offset_seconds: Optional[float] = Field(None, description="[LEGACY] Time offset in seconds (for offset mode)")
    fixed_time: Optional[str] = Field(None, description="[LEGACY] Fixed time point (format: 'YYYY-MM-DD HH:MM:SS')")
    speed: Optional[float] = Field(None, description="[LEGACY] Time speed multiplier (for scaled mode, 1.0 = normal)")
    virtual_start: Optional[str] = Field(None, description="[LEGACY] Virtual start time for scaled mode")


class TimeSeekRequest(BaseModel):
    """Seek to a specific virtual time point"""
    virtual_time: str = Field(..., description="Target virtual time (format: 'YYYY-MM-DD HH:MM:SS')")


class TimeNudgeRequest(BaseModel):
    """Nudge time forward or backward"""
    delta_seconds: float = Field(..., description="Time delta in seconds (positive = forward, negative = backward)")


class TimeSpeedRequest(BaseModel):
    """Set time speed multiplier"""
    speed: float = Field(..., description="Speed multiplier (1.0 = normal, 2.0 = 2x, 0.0 = paused)")


class TimeClockResponse(BaseModel):
    """Session clock configuration response"""
    session_id: str = Field(..., description="Session ID")
    base_virtual: str = Field(..., description="Current virtual base time")
    base_real: str = Field(..., description="Real timestamp corresponding to base_virtual")
    actions: List[TimeActionModel] = Field(default_factory=list, description="Transformation chain in order")
    current_virtual_time: str = Field(..., description="Calculated virtual time now")
    current_real_time: str = Field(..., description="Real time now")
    updated_at: Optional[str] = Field(None, description="Last update timestamp (virtual)")
    real_updated_at: Optional[str] = Field(None, description="Last update timestamp (real)")


class FlowCompletionRequest(BaseModel):
    """Flow completion request model (similar to ChatCompletionRequest but for flows)"""
    user_input: str = Field(..., description="User input text")
    input_mode: Optional[InputMode] = Field(
        default=InputMode.PHONE,
        description="Input mode: phone (手机通信), in_person (面对面说话), inner_voice (角色内心活动), command (系统指令)"
    )
    stream: bool = Field(default=False, description="Whether to stream the response")
    session_id: str = Field(..., description="Session ID for conversation history (required)")
    flow_type: str = Field(default="chat", description="Type of flow to use (default: 'chat')")
    character: Optional[CharacterInfo] = Field(None, description="Character information (optional)")
    model_info: Optional[ModelInfo] = Field(None, description="Model configuration (optional)")
    participants: Optional[List[str]] = Field(None, description="List of character IDs that messages from this flow should be visible to (None means visible to all)")


class ArchiveCreateRequest(BaseModel):
    """Create archive request"""
    name: str = Field(..., description="Archive name")


class ArchiveSwitchRequest(BaseModel):
    """Load archive request"""
    name: str = Field(..., description="Archive name to load into working database")


class ArchiveInfo(BaseModel):
    """Archive information"""
    name: str = Field(..., description="Archive name")
    path: str = Field(..., description="Archive file path")
    size: int = Field(..., description="Archive file size in bytes")
    created_at: str = Field(..., description="Creation timestamp")
    modified_at: str = Field(..., description="Last modification timestamp")


class ArchiveListResponse(BaseModel):
    """Archive list response"""
    archives: List[ArchiveInfo] = Field(..., description="List of archives")
    current_archive: Optional[ArchiveInfo] = Field(None, description="Always None - frontend doesn't need to know about working database")


class ArchiveResponse(BaseModel):
    """Archive operation response"""
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Response message")
    archive: Optional[ArchiveInfo] = Field(None, description="Archive information if applicable")
    imported_characters: Optional[List[str]] = Field(
        None, 
        description="List of character_id values that were newly imported from archive to settings (only for load_archive operation)"
    )


class FrontendMessageCreateRequest(BaseModel):
    """Request model for creating a frontend message"""
    session_id: str = Field(..., description="Session ID")
    client_message_id: str = Field(..., description="Unique client-side message ID")
    role: Literal["user", "assistant"] = Field(..., description="Message role")
    message_kind: Literal["text", "tool_output", "user", "system"] = Field(..., description="Message kind")
    content: str = Field(default="", description="Message content")
    tool_name: Optional[str] = Field(None, description="Tool name (for tool outputs or inline tools)")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID (for tool output messages)")
    input_mode: Optional[str] = Field(None, description="Input mode for user messages")
    character_id: Optional[str] = Field(None, description="Character ID for assistant messages")
    display_order: Optional[int] = Field(None, description="Display order (auto-incremented if not provided)")
    created_at: Optional[str] = Field(None, description="Virtual time when message was created (format: 'YYYY-MM-DD HH:MM:SS')")


class FrontendMessageUpdateRequest(BaseModel):
    """Request model for updating a frontend message"""
    content: Optional[str] = Field(None, description="Message content")
    tool_name: Optional[str] = Field(None, description="Tool name")
    created_at: Optional[str] = Field(
        None, description="Virtual time when message was created (format: 'YYYY-MM-DD HH:MM:SS')"
    )


class FrontendMessageResponse(BaseModel):
    """Response model for a frontend message"""
    id: int = Field(..., description="Message ID")
    session_id: str = Field(..., description="Session ID")
    client_message_id: str = Field(..., description="Client message ID")
    role: str = Field(..., description="Message role")
    message_kind: str = Field(..., description="Message kind")
    content: str = Field(..., description="Message content")
    tool_name: Optional[str] = Field(None, description="Tool name")
    tool_call_id: Optional[str] = Field(None, description="Tool call ID")
    input_mode: Optional[str] = Field(None, description="Input mode")
    character_id: Optional[str] = Field(None, description="Character ID")
    display_order: int = Field(..., description="Display order")
    created_at: str = Field(..., description="Creation timestamp")


class FrontendMessageListResponse(BaseModel):
    """Response model for a list of frontend messages"""
    messages: List[FrontendMessageResponse] = Field(..., description="List of frontend messages")


class SessionResponse(BaseModel):
    """Response model for a session"""
    id: str = Field(..., description="Session ID")
    name: str = Field(..., description="Session name")
    created_at: str = Field(..., description="Creation timestamp")
    updated_at: str = Field(..., description="Last update timestamp")
    message_count: int = Field(0, description="Number of messages in this session")


class SessionListResponse(BaseModel):
    """Response model for a list of sessions"""
    sessions: List[SessionResponse] = Field(..., description="List of sessions")