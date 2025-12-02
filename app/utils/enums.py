"""Common enumerations used across the application"""
from enum import Enum, IntEnum


class InputMode(str, Enum):
    """Input mode for user messages
    
    Defines the different conversation modes available to users:
    - PHONE: 手机通信 - Phone communication mode
    - IN_PERSON: 面对面说话 - In-person conversation mode
    - INNER_VOICE: 角色内心活动 - Inner voice/thought mode
    - COMMAND: 系统指令 - System command/instruction mode
    """
    
    PHONE = "phone"
    IN_PERSON = "in_person"
    INNER_VOICE = "inner_voice"
    COMMAND = "command"
    SKIP = "skip"
    
    @classmethod
    def default(cls) -> "InputMode":
        """Get default input mode"""
        return cls.PHONE


class MessageCategory(IntEnum):
    """Message category identifiers
    
    Categories are used to classify messages for different purposes:
    - NORMAL: Regular messages (default)
    - TELEGRAM: Messages sent via telegram
    - SPEAK_IN_PERSON: Messages sent via speak_in_person
    - THOUGHT: Internal thought/processing messages
    - TOOL: General tool output messages (for character layer)
    - SYSTEM_INSTRUCTION: System instruction messages
    """
    
    NORMAL = 0
    TELEGRAM = 1
    SPEAK_IN_PERSON = 2
    THOUGHT = 3
    TOOL = 4
    SYSTEM_INSTRUCTION = 5


class ToolName(str, Enum):
    """Enumeration of all tool/function names used in the application.
    
    This enum collects all the tool names (function names) that are used
    throughout the application for consistency and type safety.
    """
    
    # Communication tools
    CREATE_CHAT_COMPLETION = "create_chat_completion"
    SEND_TELEGRAM_MESSAGE = "send_telegram_message"
    SPEAK_IN_PERSON = "speak_in_person"
    
    # Memory and history tools
    DIALOGUE_HISTORY = "dialogue_history"
    
    # Time tools
    GET_CURRENT_TIME = "get_current_time"
    
    # Planning and reflection tools
    PLANNING = "planning"
    REFLECTION = "reflection"
    
    # Scenario tools
    SCENARIO_READER = "scenario_reader"
    SCENARIO_WRITER = "scenario_writer"
    
    # Schedule tools
    SCHEDULE_READER = "schedule_reader"
    SCHEDULE_WRITER = "schedule_writer"
    
    # Relation tools
    RELATION = "relation"
    
    # Strategy tools
    STRATEGY = "strategy"
    
    # Utility tools
    TERMINATE = "terminate"
    WEB_SEARCH = "web_search"
    
    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value


class MessageType(str, Enum):
    """Enumeration of message types used for frontend display differentiation.
    
    This enum defines the different types of messages that are displayed
    in the frontend. It serves as a display flag to distinguish between
    different message types for UI rendering purposes.
    
    Note: Currently matches ToolName for consistency, but this is temporary.
    In the future, different ToolName values may map to different MessageType
    values to provide more granular frontend display control.
    """
    
    # Communication tools
    CREATE_CHAT_COMPLETION = "create_chat_completion"
    SEND_TELEGRAM_MESSAGE = "send_telegram_message"
    SPEAK_IN_PERSON = "speak_in_person"
    
    # Memory and history tools
    DIALOGUE_HISTORY = "dialogue_history"
    
    # Time tools
    GET_CURRENT_TIME = "get_current_time"
    
    # Planning and reflection tools
    PLANNING = "planning"
    
    # Scenario tools
    SCENARIO_READER = "scenario_reader"
    SCENARIO_WRITER = "scenario_writer"
    
    # Schedule tools
    SCHEDULE_READER = "schedule_reader"
    SCHEDULE_WRITER = "schedule_writer"
    
    # Relation tools
    RELATION = "relation"
    
    # Strategy tools
    # Reflection
    INNER_THOUGHT = "inner_thought"
    
    # System instruction
    SYSTEM_INSTRUCTION = "system_instruction"
    
    # Utility tools
    TERMINATE = "terminate"
    WEB_SEARCH = "web_search"
    
    def __str__(self) -> str:
        """Return the string value of the enum."""
        return self.value