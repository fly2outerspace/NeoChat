"""Tool for reading schedule entries (list, search)"""
from typing import List, Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import ScheduleEntry
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_SCHEDULE_READER_DESCRIPTION = """
A tool to read and search the detailed schedules of your memory.

Use this tool to:
- list schedule entries by date,
- search schedule entries by keyword,
- or find schedule entries that cover a specific time point.
"""


class ScheduleReader(BaseTool):
    """Tool for reading schedule entries (list, search)"""

    name: str = ToolName.SCHEDULE_READER
    description: str = _SCHEDULE_READER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for querying schedules")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["list_by_date", "search_by_keyword", "search_by_timepoint"],
                "description": "Action to perform: 'list_by_date' to get schedules by date (returns schedules where start_at or end_at matches the date), 'search_by_keyword' to search schedules by keyword, 'search_by_timepoint' to find schedules covering a specific time point.",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in schedule content. Required when action is 'search_by_keyword'. Supports both Chinese and English keywords.",
            },
            "time_point": {
                "type": "string",
                "description": "Time point in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:30:00'). Required when action is 'search_by_timepoint'. Returns schedules that cover this time point (where start_at <= time_point <= end_at).",
            },
            "date": {
                "type": "string",
                "description": "Date in format 'YYYY-MM-DD' (e.g., '2024-01-15'). Required when action is 'list_by_date'. Returns schedules where start_at or end_at matches this date.",
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

    def _format_schedule_list(self, entries: List[ScheduleEntry]) -> str:
        """Format a list of schedule entries for readable output"""
        if not entries:
            return "No schedule entries found."
        
        output = ""
        for i, entry in enumerate(entries, 1):
            output += f"------\n"
            output += self._format_schedule_entry(entry)
            output += "\n"
        
        return output

    async def execute(
        self,
        *,
        action: Literal["list_by_date", "search_by_keyword", "search_by_timepoint"],
        keyword: Optional[str] = None,
        time_point: Optional[str] = None,
        date: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute schedule reading action.

        Args:
            action: Action to perform
            keyword: Search keyword (required for search_by_keyword)
            time_point: Time point (required for search_by_timepoint)
            date: Date in format 'YYYY-MM-DD' (required for list_by_date)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "list_by_date":
                # List schedule entries by date
                if not date:
                    raise ToolError(
                        "Parameter 'date' is required when action is 'list_by_date'"
                    )
                
                # Query from database by date (efficient database-level filtering)
                entries = Memory.get_schedule_entries_by_date(self.session_id, date, character_id=self.character_id)
                
                formatted_output = f"Found {len(entries)} schedule entry/entries for date '{date}':\n\n"
                if entries:
                    formatted_output += self._format_schedule_list(entries)
                else:
                    formatted_output += f"No schedule entries found for date '{date}'."
                
                return ToolResult(content=formatted_output)

            elif action == "search_by_keyword":
                # Search schedule entries by keyword
                if not keyword:
                    raise ToolError(
                        "Parameter 'keyword' is required when action is 'search_by_keyword'"
                    )
                
                # Use Memory to search schedule entries by keyword
                entries = Memory.search_schedule_entries_by_keyword(
                    self.session_id,
                    keyword,
                    limit=50,  # Reasonable limit for schedule entries
                    offset=0,
                    sort=["start_at:asc"],  # Sort by start time ascending
                    character_id=self.character_id,
                )
                
                # Format results
                formatted_output = f"Found {len(entries)} schedule entry/entries matching '{keyword}':\n\n"
                if entries:
                    formatted_output += self._format_schedule_list(entries)
                else:
                    formatted_output += "No schedule entries found matching the search keyword."
                
                return ToolResult(content=formatted_output)

            elif action == "search_by_timepoint":
                # Find schedule entries covering a specific time point
                if not time_point:
                    raise ToolError(
                        "Parameter 'time_point' is required when action is 'search_by_timepoint'"
                    )
                
                # Use Memory.get_schedule_entries_at to find schedules covering the time point
                entries = Memory.get_schedule_entries_at(self.session_id, time_point, character_id=self.character_id)
                
                # Format results
                formatted_output = f"Found {len(entries)} schedule entry/entries covering time point '{time_point}':\n\n"
                if entries:
                    formatted_output += self._format_schedule_list(entries)
                else:
                    formatted_output += f"No schedule entries found covering the time point '{time_point}'."
                
                return ToolResult(content=formatted_output)

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: list_by_date, search_by_keyword, search_by_timepoint"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute schedule reader action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


