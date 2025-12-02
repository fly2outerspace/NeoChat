"""Tool for writing schedule entries (create, update, delete)"""
import uuid
from typing import Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import ScheduleEntry
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_SCHEDULE_WRITER_DESCRIPTION = """A tool to write and manage the detailed schedules of your memory.

Use this tool to:
- 'create' a new schedule entry for an important past event or future plan,
- 'update' an existing schedule entry to adjust its time window, content, or linked scenario,
- 'delete' a schedule entry that is no longer relevant.

Guidelines:
- Each schedule entry should cover a relatively **narrow time window** that corresponds to a single concrete activity.
- When multiple noteworthy sub-events happen within a broader period, you SHOULD create **multiple separate schedule entries** instead of stuffing many events into one long entry.
- Prefer splitting a long time range into several shorter entries (e.g. “14:00–14:30 meeting”, “14:30–15:00 coffee chat”) so that later retrieval and reasoning stay precise.
"""


class ScheduleWriter(BaseTool):
    """Tool for writing schedule entries (create, update, delete)"""

    name: str = ToolName.SCHEDULE_WRITER
    description: str = _SCHEDULE_WRITER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for managing schedules")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "delete"],
                "description": "Action to perform: 'create' to add a new schedule, 'update' to modify schedule content, 'delete' to remove a schedule.",
            },
            "entry_id": {
                "type": "string",
                "description": "Business entry_id of the schedule entry. Required for 'update' and 'delete' actions. (will be auto-generated for 'create').",
            },
            "start_at": {
                "type": "string",
                "description": "Start time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:00:00'). Required for 'create' action. Optional for 'update' action. The time window for a single entry SHOULD be as narrow as reasonably possible and correspond to one concrete activity.",
            },
            "end_at": {
                "type": "string",
                "description": "End time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 15:00:00'). Required for 'create' action. Optional for 'update' action. Avoid using overly long ranges that pack many different events into a single entry.",
            },
            "content": {
                "type": "string",
                "description": "Schedule content/description. Describe ONE main activity for this time window. Required for 'create' action. Optional for 'update' action (at least one of content, start_at, or end_at must be provided).",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def _format_schedule_entry(self, entry: ScheduleEntry) -> str:
        """Format a single schedule entry for readable output"""
        output = f"schedule entry(ID:{entry.entry_id}):\n"
        output += f"content: {entry.content}\n"
        output += f"start_at: {entry.start_at}\n"
        output += f"end_at: {entry.end_at}\n"
        return output

    async def execute(
        self,
        *,
        action: Literal["create", "update", "delete"],
        entry_id: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        content: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute schedule writing action.

        Args:
            action: Action to perform
            entry_id: Business entry_id (required for update/delete)
            start_at: Start time (required for create)
            end_at: End time (required for create)
            content: Schedule content (required for create/update)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "create":
                # Create a new schedule entry (with overwrite support)
                if not start_at or not end_at:
                    raise ToolError(
                        "Parameters 'start_at' and 'end_at' are required when action is 'create'"
                    )
                if not content:
                    raise ToolError(
                        "Parameter 'content' is required when action is 'create'"
                    )
                
                entry_id = f"schedule-{uuid.uuid4().hex[:8]}"
                
                # Create Memory instance to use add_schedule_entry
                memory = Memory(session_id=self.session_id, character_id=self.character_id)
                new_entry = ScheduleEntry(
                    session_id=self.session_id,
                    entry_id=entry_id,
                    start_at=start_at,
                    end_at=end_at,
                    content=content,
                )
                created_entry = memory.add_schedule_entry(new_entry)
                
                formatted_output = f"Successfully created schedule entry:\n\n{self._format_schedule_entry(created_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "update":
                # Update schedule entry (content, start_at, end_at)
                if not entry_id:
                    raise ToolError(
                        "Parameter 'entry_id' is required when action is 'update'"
                    )
                if not content and not start_at and not end_at:
                    raise ToolError(
                        "At least one of 'content', 'start_at', or 'end_at' must be provided when action is 'update'"
                    )
                
                updated_entry = Memory.update_schedule_entry_by_entry_id(
                    entry_id,
                    content=content,
                    start_at=start_at,
                    end_at=end_at,
                    session_id=self.session_id,
                )
                
                if not updated_entry:
                    return ToolResult(error=f"Schedule entry with entry_id '{entry_id}' not found or update failed.")
                
                formatted_output = f"Successfully updated schedule entry:\n\n{self._format_schedule_entry(updated_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "delete":
                # Delete a schedule entry
                if not entry_id:
                    raise ToolError(
                        "Parameter 'entry_id' is required when action is 'delete'"
                    )
                
                success = Memory.delete_schedule_entry_by_entry_id(
                    entry_id, self.session_id
                )
                
                if not success:
                    return ToolResult(error=f"Schedule entry with entry_id '{entry_id}' not found or deletion failed.")
                
                return ToolResult(content=f"Successfully deleted schedule entry with entry_id: {entry_id}")

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: create, update, delete"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute schedule writer action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


