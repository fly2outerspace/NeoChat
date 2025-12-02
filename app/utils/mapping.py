"""Mapping utilities for converting between different message types and categories"""
from typing import Optional, Union

from app.utils.enums import ToolName
from app.utils.enums import InputMode, MessageCategory
from app.logger import logger

# Mapping from tool name to message category
# Use .value to ensure string keys work correctly with string lookups
TOOL_CATEGORY_MAP = {
    ToolName.SEND_TELEGRAM_MESSAGE.value: MessageCategory.TELEGRAM,
    ToolName.SPEAK_IN_PERSON.value: MessageCategory.SPEAK_IN_PERSON,
    # Add more tool-to-category mappings here as needed
}

# Mapping from InputMode to MessageCategory
INPUT_MODE_TO_CATEGORY_MAP = {
    InputMode.PHONE: MessageCategory.TELEGRAM,
    InputMode.IN_PERSON: MessageCategory.SPEAK_IN_PERSON,
    InputMode.INNER_VOICE: MessageCategory.THOUGHT,
    InputMode.COMMAND: MessageCategory.SYSTEM_INSTRUCTION,
}

# Mapping from MessageCategory to indicator string
CATEGORY_TO_INDICATOR_MAP = {
    MessageCategory.TELEGRAM: "telegram",
    MessageCategory.SPEAK_IN_PERSON: "speakinperson",
    MessageCategory.THOUGHT: "thought",
    MessageCategory.NORMAL: "normal",
    MessageCategory.TOOL: "tool",
    MessageCategory.SYSTEM_INSTRUCTION: "system_instruction",
}


def get_category_from_input_mode(input_mode: Optional[Union[InputMode, str]]) -> MessageCategory:
    """Convert input_mode to MessageCategory
    
    Args:
        input_mode: Input mode enum or string ("phone", "in_person", "inner_voice", "command")
    
    Returns:
        MessageCategory: Corresponding message category
    """
    # Handle string input for backward compatibility
    if isinstance(input_mode, str):
        try:
            input_mode = InputMode(input_mode)
        except ValueError:
            # Invalid input_mode, default to PHONE
            logger.warning(f"Invalid input_mode: {input_mode}, defaulting to PHONE")
            input_mode = InputMode.PHONE
    
    # Handle None or use default
    if input_mode is None:
        input_mode = InputMode.PHONE
    
    # Map InputMode to MessageCategory using mapping
    return INPUT_MODE_TO_CATEGORY_MAP.get(input_mode, MessageCategory.TELEGRAM)

