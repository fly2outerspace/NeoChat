"""Tool for strategic decision-making and conversation planning."""
from typing import Literal

from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


class Strategy(BaseTool):
    """
    A tool that allows the agent to make strategic decisions about communication channels
    and plan conversation strategies.
    
    The tool helps the agent decide whether to use speak_in_person or telegram for communication,
    and provides a comprehensive strategy for the conversation.
    """

    name: str = ToolName.STRATEGY
    description: str = (
        "Decide whether to use speak_in_person (face-to-face conversation) or telegram (remote messaging), "
        "Use this tool to make inner_monologue about how to communicate with the user. "
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "decision": {
                "type": "string",
                "enum": ["speakinperson", "telegram"],
                "description": (
                    "The communication channel to use: "
                    "'speakinperson' for face-to-face conversation, "
                    "'telegram' for remote messaging via Telegram."
                ),
            },
            "inner_monologue": {
                "type": "string",
                "description": (
                    "A comprehensive inner_monologue covering all personal aspects for the conversation. "
                ),
            },
        },
        "required": ["decision", "inner_monologue"],
        "additionalProperties": False,
    }

    
    async def execute(
        self,
        *,
        decision: Literal["speakinperson", "telegram"],
        inner_monologue: str,
        **kwargs,
    ) -> ToolResult:
        """Format and return the strategy decision and plan."""
        decision_text = decision.strip()
        strategy_text = (inner_monologue or "").strip()

        if not decision_text:
            return ToolResult(content="error: must provide decision parameter")

        if not strategy_text:
            return ToolResult(content="error: must provide strategy parameter")

        # For the display, not for program usage.
        content = strategy_text

        # Return structured result with args
        return ToolResult(
            content=content,
            args={
                "decision": decision_text,
                "strategy": strategy_text,
            }
        )

