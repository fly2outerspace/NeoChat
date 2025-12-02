from typing import Any, Optional

from app.tool import BaseTool
from app.utils.enums import ToolName


class SpeakInPerson(BaseTool):
    name: str = ToolName.SPEAK_IN_PERSON
    session_id: Optional[str] = None
    description: str = (
        "Use this tool to express speech in person (face-to-face conversation). "
        "You can use parentheses to include actions, expressions, and other objective elements."
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The in-person speech content.",
            },
        },
        "required": ["content"],
    }

    async def execute(self, **kwargs) -> str:
        """Execute the in-person speech action.

        Args:
            **kwargs: Speech data containing 'content' field

        Returns:
            The content string with timestamp
        """
        content = kwargs.get("content", "")
        return content

