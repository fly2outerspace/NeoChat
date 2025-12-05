"""Tool for reading scenario entries (search by keyword or scenario_id)"""
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
2) or get a specific scenario by its scenario_id.
"""


class ScenarioReader(BaseTool):
    """Tool for reading scenario entries (search by keyword or scenario_id)"""

    name: str = ToolName.SCENARIO_READER
    description: str = _SCENARIO_READER_DESCRIPTION
    session_id: str = Field(..., description="Session ID for querying scenarios")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["search_by_keyword", "search_by_id"],
                "description": "Action to perform: 'search_by_keyword' to search scenarios by keyword, 'search_by_id' to get a specific scenario by its scenario_id.",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in scenario content. Required when action is 'search_by_keyword'. Supports both Chinese and English keywords.",
            },
            "scenario_id": {
                "type": "string",
                "description": "Scenario ID to search for. Required when action is 'search_by_id'. Returns the scenario with the specified scenario_id if it exists.",
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
        action: Literal["search_by_keyword", "search_by_id"],
        keyword: Optional[str] = None,
        scenario_id: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute scenario reading action.

        Args:
            action: Action to perform
            keyword: Search keyword (required for search_by_keyword)
            scenario_id: Scenario ID (required for search_by_id)

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

            elif action == "search_by_id":
                # Get a specific scenario by scenario_id
                if not scenario_id:
                    raise ToolError(
                        "Parameter 'scenario_id' is required when action is 'search_by_id'"
                    )
                
                # Use Memory.get_scenario_by_scenario_id to get the scenario
                scenario = Memory.get_scenario_by_scenario_id(scenario_id, self.session_id)
                
                # Format result
                if scenario:
                    formatted_output = f"Found scenario with scenario_id '{scenario_id}':\n\n"
                    formatted_output += self._format_scenario_entry(scenario)
                else:
                    formatted_output = f"No scenario found with scenario_id '{scenario_id}'."
                
                return ToolResult(content=formatted_output)

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: search_by_keyword, search_by_id"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute scenario reader action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


