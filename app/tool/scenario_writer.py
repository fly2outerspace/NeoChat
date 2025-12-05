"""Tool for writing scenario entries (create, update, delete)"""
import uuid
from typing import Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import Scenario
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_SCENARIO_WRITER_DESCRIPTION = """A tool to write and manage the detailed scenarios of your memory.

Use this tool to:
- 'create' a new scenario entry for an important past episode or memorable event,
- 'update' an existing scenario entry to adjust its time window, content, or title,
- 'delete' a scenario entry that is no longer relevant.

Guidelines:
- Each scenario should be a vivid, subjective story tied to a specific time range.
- Write scenarios from your own perspective with personal meaning.
"""


class ScenarioWriter(BaseTool):
    """Tool for writing scenario entries (create, update, delete)"""

    name: str = ToolName.SCENARIO_WRITER
    description: str = _SCENARIO_WRITER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for managing scenarios")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "delete"],
                "description": "Action to perform: 'create' to add a new scenario, 'update' to modify scenario content, 'delete' to remove a scenario.",
            },
            "scenario_id": {
                "type": "string",
                "description": "Business scenario_id of the scenario. Required for 'update' and 'delete' actions.",
            },
            "title": {
                "type": "string",
                "description": "Scenario title (key event + important people/place). Required for 'create' action.",
            },
            "start_at": {
                "type": "string",
                "description": "Start time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:00:00'). Required for 'create' action.",
            },
            "end_at": {
                "type": "string",
                "description": "End time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 15:00:00'). Required for 'create' action.",
            },
            "content": {
                "type": "string",
                "description": "Full narrative details of the scenario. Required for 'create' action. Optional for 'update' action.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def _format_scenario_entry(self, entry: Scenario) -> str:
        """Format a single scenario entry for readable output"""
        output = f"scenario_id:{entry.scenario_id}:\n"
        if entry.title:
            output += f"title: {entry.title}\n"
        output += f"content: {entry.content}\n"
        output += f"start_at: {entry.start_at}\n"
        output += f"end_at: {entry.end_at}\n"
        return output

    async def execute(
        self,
        *,
        action: Literal["create", "update", "delete"],
        scenario_id: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        content: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute scenario writing action.

        Args:
            action: Action to perform
            scenario_id: Business scenario_id (required for update/delete)
            start_at: Start time (required for create)
            end_at: End time (required for create)
            content: Scenario content (required for create/update)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "create":
                # Create a new scenario entry (with overwrite support)
                if not start_at or not end_at:
                    raise ToolError(
                        "Parameters 'start_at' and 'end_at' are required when action is 'create'. "
                        "Example: {\"action\": \"create\", \"title\": \"Meeting with John\", "
                        "\"start_at\": \"2024-01-15 14:00:00\", \"end_at\": \"2024-01-15 15:00:00\", "
                        "\"content\": \"Had a productive discussion...\"}"
                    )
                if not content:
                    raise ToolError(
                        "Parameter 'content' is required when action is 'create'. "
                        "Example: {\"action\": \"create\", \"title\": \"Meeting with John\", "
                        "\"start_at\": \"2024-01-15 14:00:00\", \"end_at\": \"2024-01-15 15:00:00\", "
                        "\"content\": \"Had a productive discussion...\"}"
                    )
                if not title:
                    raise ToolError(
                        "Parameter 'title' is required when action is 'create'. "
                        "Example: {\"action\": \"create\", \"title\": \"Meeting with John\", "
                        "\"start_at\": \"2024-01-15 14:00:00\", \"end_at\": \"2024-01-15 15:00:00\", "
                        "\"content\": \"Had a productive discussion...\"}"
                    )
                
                # Check if user provided scenario_id (for overwrite support)
                user_provided_scenario_id = scenario_id is not None
                
                # Generate scenario_id automatically if not provided
                if not scenario_id:
                    scenario_id = f"scenario-{uuid.uuid4().hex[:8]}"
                
                # If scenario_id was provided by user, check if it exists and delete it first (overwrite support)
                was_overwritten = False
                if user_provided_scenario_id:
                    # Try to delete existing scenario (returns True if deleted, False if not found)
                    was_overwritten = Memory.delete_scenario_by_scenario_id(scenario_id, self.session_id)
                
                # Create Memory instance to use add_scenario
                memory = Memory(session_id=self.session_id, character_id=self.character_id)
                new_entry = Scenario(
                    session_id=self.session_id,
                    scenario_id=scenario_id,
                    start_at=start_at,
                    end_at=end_at,
                    content=content,
                    title=title,
                )
                created_entry = memory.add_scenario(new_entry)
                
                action_text = "overwritten" if was_overwritten else "created"
                formatted_output = f"Successfully {action_text} scenario entry:\n\n{self._format_scenario_entry(created_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "update":
                # Update scenario entry (content, start_at, end_at, title)
                if not scenario_id:
                    raise ToolError(
                        "Parameter 'scenario_id' is required when action is 'update'"
                    )
                if not content and not start_at and not end_at and not title:
                    raise ToolError(
                        "At least one of 'content', 'start_at', 'end_at', or 'title' must be provided when action is 'update'"
                    )
                
                updated_entry = Memory.update_scenario_by_scenario_id(
                    scenario_id,
                    content=content,
                    start_at=start_at,
                    end_at=end_at,
                    title=title,
                    session_id=self.session_id,
                )
                
                if not updated_entry:
                    return ToolResult(error=f"Scenario entry with scenario_id '{scenario_id}' not found or update failed.")
                
                formatted_output = f"Successfully updated scenario entry:\n\n{self._format_scenario_entry(updated_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "delete":
                # Delete a scenario entry
                if not scenario_id:
                    raise ToolError(
                        "Parameter 'scenario_id' is required when action is 'delete'"
                    )
                
                success = Memory.delete_scenario_by_scenario_id(
                    scenario_id, self.session_id
                )
                
                if not success:
                    return ToolResult(error=f"Scenario entry with scenario_id '{scenario_id}' not found or deletion failed.")
                
                return ToolResult(content=f"Successfully deleted scenario entry with scenario_id: {scenario_id}")

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: create, update, delete"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute scenario writer action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


