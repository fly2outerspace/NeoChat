"""Tool for reading scenario entries (search by keyword, time point, or time range)"""
from typing import List, Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import Scenario
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_SCENARIO_READER_DESCRIPTION = """
A tool to read and search the detailed scenarios of your memory.

Use this tool to:
1) search scenarios by a keyword that appears in the scenario content (both Chinese and English keywords are supported),
2) find scenarios covering a specific time point,
3) or find scenarios that overlap with a given time range.
"""


class ScenarioReader(BaseTool):
    """Tool for reading scenario entries (search by keyword, time point, or time range)"""

    name: str = ToolName.SCENARIO_READER
    description: str = _SCENARIO_READER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for querying scenarios")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_by_keyword", "search_by_timepoint", "search_by_time_range"],
                "description": "Action to perform: 'search_by_keyword' to search scenarios by keyword, 'search_by_timepoint' to find scenarios covering a specific time point, 'search_by_time_range' to find scenarios that overlap with a time range.",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in scenario content. Required when action is 'search_by_keyword'. Supports both Chinese and English keywords.",
            },
            "time_point": {
                "type": "string",
                "description": "Time point in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:30:00'). Required when action is 'search_by_timepoint'. Returns scenarios that cover this time point (where start_at <= time_point <= end_at).",
            },
            "start_at": {
                "type": "string",
                "description": "Start time of the query range in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 10:00:00'). Required when action is 'search_by_time_range'.",
            },
            "end_at": {
                "type": "string",
                "description": "End time of the query range in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 15:00:00'). Required when action is 'search_by_time_range'.",
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

    def _format_scenario_list(self, entries: List[Scenario]) -> str:
        """Format a list of scenario entries for readable output"""
        if not entries:
            return "No scenario entries found."
        
        output = ""
        for i, entry in enumerate(entries, 1):
            output += f"------\n"
            output += self._format_scenario_entry(entry)
            output += "\n"
        
        return output

    async def execute(
        self,
        *,
        action: Literal["search_by_keyword", "search_by_timepoint", "search_by_time_range"],
        keyword: Optional[str] = None,
        time_point: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute scenario reading action.

        Args:
            action: Action to perform
            keyword: Search keyword (required for search_by_keyword)
            time_point: Time point (required for search_by_timepoint)
            start_at: Start time of range (required for search_by_time_range)
            end_at: End time of range (required for search_by_time_range)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "search_by_keyword":
                # Search scenario entries by keyword
                if not keyword:
                    raise ToolError(
                        "Parameter 'keyword' is required when action is 'search_by_keyword'"
                    )
                
                # Use Memory to search scenarios by keyword
                entries = Memory.search_scenarios_by_keyword(
                    self.session_id,
                    keyword,
                    limit=50,  # Reasonable limit for scenario entries
                    offset=0,
                    sort=["start_at:asc"],  # Sort by start time ascending
                    character_id=self.character_id,
                )
                
                # Format results
                formatted_output = f"Found {len(entries)} scenario entry/entries matching '{keyword}':\n\n"
                if entries:
                    formatted_output += self._format_scenario_list(entries)
                else:
                    formatted_output += "No scenario entries found matching the search keyword."
                
                return ToolResult(content=formatted_output)

            elif action == "search_by_timepoint":
                # Find scenario entries covering a specific time point
                if not time_point:
                    raise ToolError(
                        "Parameter 'time_point' is required when action is 'search_by_timepoint'"
                    )
                
                # Use Memory.get_scenarios_at to find scenarios covering the time point
                entries = Memory.get_scenarios_at(self.session_id, time_point, character_id=self.character_id)
                
                # Format results
                formatted_output = f"Found {len(entries)} scenario entry/entries covering time point '{time_point}':\n\n"
                if entries:
                    formatted_output += self._format_scenario_list(entries)
                else:
                    formatted_output += f"No scenario entries found covering the time point '{time_point}'."
                
                return ToolResult(content=formatted_output)

            elif action == "search_by_time_range":
                # Find scenario entries that overlap with the given time range
                if not start_at or not end_at:
                    raise ToolError(
                        "Parameters 'start_at' and 'end_at' are required when action is 'search_by_time_range'"
                    )
                
                # Use Memory.get_scenarios_in_range to find scenarios overlapping with the range
                entries = Memory.get_scenarios_in_range(self.session_id, start_at, end_at, character_id=self.character_id)
                
                # Format results
                formatted_output = f"Found {len(entries)} scenario entry/entries overlapping with time range '{start_at}' to '{end_at}':\n\n"
                if entries:
                    formatted_output += self._format_scenario_list(entries)
                else:
                    formatted_output += f"No scenario entries found overlapping with the time range '{start_at}' to '{end_at}'."
                
                return ToolResult(content=formatted_output)

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: search_by_keyword, search_by_timepoint, search_by_time_range"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute scenario reader action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


