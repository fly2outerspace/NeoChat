"""Tool for structured self-reflection each reasoning step."""
from app.tool import BaseTool
from app.utils.enums import ToolName


class Reflection(BaseTool):
    """
    A tool that lets the agent explicitly write down its private reflection
    and concrete next-step plan for this turn.

    The output of this tool is **not** meant to be sent directly to the user;
    it is stored as an internal tool message to help the agent think more clearly.
    """

    name: str = ToolName.REFLECTION
    description: str = (
        "Use this tool at each reasoning step to explicitly reflect on what you should do next. "
        "Summarize the current situation, check consistency with your schedule and plans, and then "
        "formulate a concrete next-step plan (which tools to call, what to say, or what to update). "
        "This reflection is internal thinking and should NOT be sent directly to the user."
    )

    parameters: dict = {
        "type": "object",
        "properties": {
            "reflection": {
                "type": "string",
                "description": (
                    "Your private reflection about the current situation: what the user wants, "
                    "what your goals are, how your schedule and scenarios are involved, and any "
                    "uncertainties you need to resolve."
                ),
            },
            "next_plan": {
                "type": "string",
                "description": (
                    "A concrete, concise plan for your next one or two actions: "
                    "for example, which tools to call (such as schedule_reader / schedule_writer / "
                    "scenario_reader / scenario_writer / send_telegram_message) and in what order, "
                    "or what kind of reply you intend to send."
                ),
            },
        },
        "required": ["reflection"],
        "additionalProperties": False,
    }

    async def execute(self, **kwargs) -> str:
        """Format and return the reflection content for logging into memory."""
        reflection = (kwargs.get("reflection") or "").strip()
        next_plan = (kwargs.get("next_plan") or "").strip()

        parts = []
        if reflection:
            parts.append(self._format_reflection(reflection))
        if next_plan:
            parts.append("下一步计划：" + next_plan)

        # Ensure we always return something non-empty to be stored.
        if not parts:
            parts.append("反思：(空)")

        return "\n".join(parts)


    def _format_reflection(self, reflection: str) -> str:
        """Format the reflection content for logging into memory."""
        return reflection.replace("\n", "")