from typing import Any, Optional

from app.tool import BaseTool
from app.utils.enums import ToolName

class SendTelegramMessage(BaseTool):
    name: str = ToolName.SEND_TELEGRAM_MESSAGE
    session_id: Optional[str] = None
    description: str = (
        "Use this tool to send a message to the user on Telegram. "
        "This is the primary way to communicate with the user on Telegram. "
        "call this tool with the 'response' parameter containing your message. "
        "When using this tool, you should simulate real social app chat style by using "
        "short sentences with line breaks to express your message. "
        "Reply with one to two lines for normal communication, can use multiple lines when you have a lot to say."
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "response": {
                "type": "string",
                "description": "The message text that should be sent to the user on Telegram.",    
            },
        },
        "required": ["response"],
    }

    async def execute(self, **kwargs) -> str:
        """Execute the Telegram message sending.

        Args:
            **kwargs: Response data containing 'response' field

        Returns:
            The message text to be sent on Telegram
        """
        response = kwargs.get("response", "")
        return response
