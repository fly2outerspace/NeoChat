from typing import Optional
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName
from app.utils import get_current_time


_GET_CURRENT_TIME_DESCRIPTION = """Get the current date and time. Returns the current time in a readable format (YYYY-MM-DD HH:MM:SS). The time returned is session-specific virtual time if available, otherwise real system time."""


class GetCurrentTime(BaseTool):
    name: str = ToolName.GET_CURRENT_TIME
    description: str = _GET_CURRENT_TIME_DESCRIPTION
    session_id: Optional[str] = None
    parameters: dict = {
        "type": "object",
        "properties": {},
        "required": [],
    }

    async def execute(self, **kwargs) -> str:
        """Get the current date and time in readable format.
        
        Returns:
            Current time as a string in format 'YYYY-MM-DD HH:MM:SS'
        """
        try:
            # Try to get session_id from kwargs or context
            return get_current_time(session_id=self.session_id)
        except Exception as e:
            return f"Error getting current time: {e}"

