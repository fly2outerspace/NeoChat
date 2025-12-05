"""Tool for writing event entries (create, update, delete)"""
import uuid
from typing import Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import Event
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_EVENT_WRITER_DESCRIPTION = """A tool to write and manage the life events of your memory.

Use this tool to:
- 'create' a new event entry for an important past episode, future plan, or memorable experience,
- 'update' an existing event entry to adjust its time window, title, or scene,
- 'delete' an event entry that is no longer relevant.

Guidelines:
- Each event has two parts:
  * Title: Factual information (what happened, when, where, who)
  * Scene: Subjective detailed content (feelings, dialogue, story)
- Write events from your own perspective with personal meaning.
"""


class EventWriter(BaseTool):
    """Tool for writing event entries (create, update, delete)"""

    name: str = ToolName.EVENT_WRITER
    description: str = _EVENT_WRITER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for managing events")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "delete"],
                "description": "Action to perform: 'create' to add a new event, 'update' to modify event content, 'delete' to remove an event.",
            },
            "event_id": {
                "type": "string",
                "description": "Business event_id of the event. Required for 'update' and 'delete' actions.",
            },
            "title": {
                "type": "string",
                "description": "Event title (factual information: what, when, where, who). Required for 'create' action.",
            },
            "scene": {
                "type": "string",
                "description": "Event scene (subjective detailed content: feelings, dialogue, story). Optional for 'create' and 'update' actions.",
            },
            "start_at": {
                "type": "string",
                "description": "Start time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:00:00'). Required for 'create' action.",
            },
            "end_at": {
                "type": "string",
                "description": "End time in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 15:00:00'). Required for 'create' action.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def _format_event_entry(self, entry: Event) -> str:
        """Format a single event entry for readable output"""
        output = f"event_id:{entry.event_id}:\n"
        if entry.title:
            output += f"title: {entry.title}\n"
        if entry.scene:
            output += f"scene: {entry.scene}\n"
        output += f"start_at: {entry.start_at}\n"
        output += f"end_at: {entry.end_at}\n"
        return output

    async def execute(
        self,
        *,
        action: Literal["create", "update", "delete"],
        event_id: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        scene: Optional[str] = None,
        title: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute event writing action.

        Args:
            action: Action to perform
            event_id: Business event_id (required for update/delete)
            start_at: Start time (required for create)
            end_at: End time (required for create)
            scene: Event scene (optional for create/update)
            title: Event title (required for create, optional for update)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "create":
                # Create a new event entry (with overwrite support)
                if not start_at or not end_at:
                    raise ToolError(
                        "Parameters 'start_at' and 'end_at' are required when action is 'create'. "
                        "Example: {\"action\": \"create\", \"title\": \"Meeting with John\", "
                        "\"start_at\": \"2024-01-15 14:00:00\", \"end_at\": \"2024-01-15 15:00:00\", "
                        "\"scene\": \"Had a productive discussion...\"}"
                    )
                if not title:
                    raise ToolError(
                        "Parameter 'title' is required when action is 'create'. "
                        "Example: {\"action\": \"create\", \"title\": \"Meeting with John\", "
                        "\"start_at\": \"2024-01-15 14:00:00\", \"end_at\": \"2024-01-15 15:00:00\", "
                        "\"scene\": \"Had a productive discussion...\"}"
                    )
                
                # Check if user provided event_id (for overwrite support)
                user_provided_event_id = event_id is not None
                
                # Generate event_id automatically if not provided
                if not event_id:
                    event_id = f"event-{uuid.uuid4().hex[:8]}"
                
                # If event_id was provided by user, check if it exists and delete it first (overwrite support)
                was_overwritten = False
                if user_provided_event_id:
                    # Try to delete existing event (returns True if deleted, False if not found)
                    was_overwritten = Memory.delete_event_by_event_id(event_id, self.session_id)
                
                # Create Memory instance to use add_event
                memory = Memory(session_id=self.session_id, character_id=self.character_id)
                new_entry = Event(
                    session_id=self.session_id,
                    event_id=event_id,
                    start_at=start_at,
                    end_at=end_at,
                    scene=scene or "",
                    title=title,
                )
                created_entry = memory.add_event(new_entry)
                
                action_text = "overwritten" if was_overwritten else "created"
                formatted_output = f"Successfully {action_text} event entry:\n\n{self._format_event_entry(created_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "update":
                # Update event entry (scene, start_at, end_at, title)
                if not event_id:
                    raise ToolError(
                        "Parameter 'event_id' is required when action is 'update'"
                    )
                if not scene and not start_at and not end_at and not title:
                    raise ToolError(
                        "At least one of 'scene', 'start_at', 'end_at', or 'title' must be provided when action is 'update'"
                    )
                
                updated_entry = Memory.update_event_by_event_id(
                    event_id,
                    scene=scene,
                    start_at=start_at,
                    end_at=end_at,
                    title=title,
                    session_id=self.session_id,
                )
                
                if not updated_entry:
                    return ToolResult(error=f"Event entry with event_id '{event_id}' not found or update failed.")
                
                formatted_output = f"Successfully updated event entry:\n\n{self._format_event_entry(updated_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "delete":
                # Delete an event entry
                if not event_id:
                    raise ToolError(
                        "Parameter 'event_id' is required when action is 'delete'"
                    )
                
                success = Memory.delete_event_by_event_id(
                    event_id, self.session_id
                )
                
                if not success:
                    return ToolResult(error=f"Event entry with event_id '{event_id}' not found or deletion failed.")
                
                return ToolResult(content=f"Successfully deleted event entry with event_id: {event_id}")

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: create, update, delete"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute event writer action '{action}': {str(e)}"
            return ToolResult(error=error_msg)

