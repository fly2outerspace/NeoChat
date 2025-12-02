"""Tool for managing relation entries (create, update, delete, search)"""
import uuid
from typing import Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.schema import Relation
from app.tool.base import BaseTool, ToolResult
from app.utils.enums import ToolName


_RELATION_DESCRIPTION = """
A tool to manage relationship information in your memory.

Use this tool to:
- 'create' a new relationship entry when you learn about or establish a relationship with someone,
- 'update' an existing relationship to update name, knowledge, or progress information,
- 'delete' a relationship that is no longer relevant,
- 'search' relationships by keyword to find specific relationship information.
"""


class RelationTool(BaseTool):
    """Tool for managing relation entries (create, update, delete, search)"""

    name: str = ToolName.RELATION
    description: str = _RELATION_DESCRIPTION
    session_id: str = Field(..., description="Session ID for managing relations")
    parameters: dict = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "update", "delete", "search"],
                "description": "Action to perform: 'create' to add a new relation, 'update' to modify relation fields, 'delete' to remove a relation, 'search' to find relations by keyword.",
            },
            "relation_id": {
                "type": "string",
                "description": "Business relation_id of the relation. Required for 'update' and 'delete' actions. Optional for 'create' (will be auto-generated if not provided).",
            },
            "name": {
                "type": "string",
                "description": "Name of the person/entity in the relationship. Required for 'create' action. Optional for 'update' action.",
            },
            "knowledge": {
                "type": "string",
                "description": "Knowledge about this relationship. Optional for 'create' and 'update' actions.",
            },
            "progress": {
                "type": "string",
                "description": "Progress/status of the relationship. Optional for 'create' and 'update' actions.",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in relation name, knowledge, or progress. Required when action is 'search'.",
            },
        },
        "required": ["action"],
        "additionalProperties": False,
    }

    def _format_relation_entry(self, entry: Relation) -> str:
        """Format a single relation entry for readable output"""
        output = f"relation_id: {entry.relation_id}\n"
        output += f"name: {entry.name}\n"
        output += f"knowledge: {entry.knowledge}\n"
        output += f"progress: {entry.progress}\n"
        return output

    def _format_relation_list(self, entries: list[Relation]) -> str:
        """Format a list of relation entries for readable output"""
        if not entries:
            return "No relation entries found."
        
        output = ""
        for i, entry in enumerate(entries, 1):
            output += f"------\n"
            output += self._format_relation_entry(entry)
            output += "\n"
        
        return output

    async def execute(
        self,
        *,
        action: Literal["create", "update", "delete", "search"],
        relation_id: Optional[str] = None,
        name: Optional[str] = None,
        knowledge: Optional[str] = None,
        progress: Optional[str] = None,
        keyword: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute relation management action.

        Args:
            action: Action to perform
            relation_id: Business relation_id (required for update/delete, optional for create)
            name: Name of the person/entity (required for create)
            knowledge: Knowledge about the relationship (optional)
            progress: Progress/status of the relationship (optional)
            keyword: Search keyword (required for search)

        Returns:
            ToolResult containing formatted result
        """
        try:
            if action == "create":
                # Create a new relation entry
                if not name:
                    raise ToolError(
                        "Parameter 'name' is required when action is 'create'"
                    )
                
                # Generate relation_id automatically if not provided
                if not relation_id:
                    relation_id = f"relation-{uuid.uuid4().hex[:8]}"
                
                # Check if relation_id already exists (for overwrite support)
                was_overwritten = False
                existing = Memory.get_relation_by_relation_id(relation_id, self.session_id, character_id=self.character_id)
                if existing:
                    was_overwritten = Memory.delete_relation_by_relation_id(relation_id, self.session_id, character_id=self.character_id)
                
                # Create Memory instance to use add_relation
                memory = Memory(session_id=self.session_id, character_id=self.character_id)
                new_entry = Relation(
                    session_id=self.session_id,
                    relation_id=relation_id,
                    name=name,
                    knowledge=knowledge or "",
                    progress=progress or "",
                )
                created_entry = memory.add_relation(new_entry)
                
                action_text = "overwritten" if was_overwritten else "created"
                formatted_output = f"Successfully {action_text} relation entry:\n\n{self._format_relation_entry(created_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "update":
                # Update relation entry
                if not relation_id:
                    raise ToolError(
                        "Parameter 'relation_id' is required when action is 'update'"
                    )
                if not name and not knowledge and not progress:
                    raise ToolError(
                        "At least one of 'name', 'knowledge', or 'progress' must be provided when action is 'update'"
                    )
                
                updated_entry = Memory.update_relation_by_relation_id(
                    relation_id,
                    name=name,
                    knowledge=knowledge,
                    progress=progress,
                    session_id=self.session_id,
                    character_id=self.character_id,
                )
                
                if not updated_entry:
                    return ToolResult(error=f"Relation entry with relation_id '{relation_id}' not found or update failed.")
                
                formatted_output = f"Successfully updated relation entry:\n\n{self._format_relation_entry(updated_entry)}"
                return ToolResult(content=formatted_output)

            elif action == "delete":
                # Delete a relation entry
                if not relation_id:
                    raise ToolError(
                        "Parameter 'relation_id' is required when action is 'delete'"
                    )
                
                success = Memory.delete_relation_by_relation_id(
                    relation_id, self.session_id, character_id=self.character_id
                )
                
                if not success:
                    return ToolResult(error=f"Relation entry with relation_id '{relation_id}' not found or deletion failed.")
                
                return ToolResult(content=f"Successfully deleted relation entry with relation_id: {relation_id}")

            elif action == "search":
                # Search relation entries by keyword
                if not keyword:
                    raise ToolError(
                        "Parameter 'keyword' is required when action is 'search'"
                    )
                
                # Use Memory to search relations by keyword
                entries = Memory.search_relations_by_keyword(
                    self.session_id,
                    keyword,
                    limit=50,  # Reasonable limit for relation entries
                    character_id=self.character_id,
                )
                
                # Format results
                formatted_output = f"Found {len(entries)} relation entry/entries matching '{keyword}':\n\n"
                if entries:
                    formatted_output += self._format_relation_list(entries)
                else:
                    formatted_output += "No relation entries found matching the search keyword."
                
                return ToolResult(content=formatted_output)

            else:
                raise ToolError(
                    f"Invalid action: {action}. Must be one of: create, update, delete, search"
                )

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to execute relation action '{action}': {str(e)}"
            return ToolResult(error=error_msg)


