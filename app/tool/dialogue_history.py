"""Tool for querying dialogue history from memory"""
from typing import List, Literal, Optional

from pydantic import Field

from app.exceptions import ToolError
from app.memory import Memory
from app.utils.enums import ToolName
from app.utils.enums import MessageCategory
from app.schema import Message, QueryMetadata
from app.tool.base import BaseTool, ToolResult


def _get_category_indicator(category: int) -> str:
    """Get indicator string based on message category"""
    if category == MessageCategory.TELEGRAM:
        return "telegram"
    elif category == MessageCategory.SPEAK_IN_PERSON:
        return "speakinperson"
    elif category == MessageCategory.THOUGHT:
        return "thought"
    elif category == MessageCategory.TOOL:
        return "tool"
    else:
        return ""  # Empty for NORMAL or unknown categories


_DIALOGUE_HISTORY_DESCRIPTION = """
Query dialogue history from the chat history. 
This tool allows you to retrieve past messages by date, time point, time range, or keyword search.
Use this when you need to recall previous conversations or check what was discussed at specific times.

Note: Each query returns a maximum of 100 messages. If you need more information, you can call this tool multiple times with different time ranges, dates, or keywords.
"""


class DialogueHistory(BaseTool):
    """Tool for querying dialogue history from memory storage"""

    name: str = ToolName.DIALOGUE_HISTORY
    description: str = _DIALOGUE_HISTORY_DESCRIPTION
    session_id: str = Field(..., description="Session ID for querying messages")
    character_id: Optional[str] = Field(default=None, description="Character ID for querying messages")
    parameters: dict = {
        "type": "object",
        "properties": {
            "query_type": {
                "type": "string",
                "enum": ["by_date", "around_time", "in_range", "by_keyword"],
                "description": "Type of query: 'by_date' to get all messages on a specific date, 'around_time' to get messages around a time point, 'in_range' to get messages within a time range, 'by_keyword' to search messages by keyword (supports Chinese and English).",
            },
            "keyword": {
                "type": "string",
                "description": "Keyword to search for in message content. Required when query_type is 'by_keyword'. Supports both Chinese and English keywords.",
            },
            "date": {
                "type": "string",
                "description": "Date string in format 'YYYY-MM-DD' (e.g., '2024-01-15'). Required when query_type is 'by_date'. If time is included, only date part is used.",
            },
            "time_point": {
                "type": "string",
                "description": "Time point string in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 14:30:00'). Required when query_type is 'around_time'.",
            },
            "start_time": {
                "type": "string",
                "description": "Start time string in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 09:00:00'). Required when query_type is 'in_range'.",
            },
            "end_time": {
                "type": "string",
                "description": "End time string in format 'YYYY-MM-DD HH:MM:SS' (e.g., '2024-01-15 18:00:00'). Required when query_type is 'in_range'.",
            },
        },
        "required": ["query_type"],
        "additionalProperties": False,
    }

    def _format_messages(
        self, 
        messages: List[Message],
        metadata: QueryMetadata,
        max_results,
    ) -> str:
        """Format messages for readable output
        
        Args:
            messages: List of messages to format
            metadata: QueryMetadata containing information about whether there are more messages
        """
        if not messages:
            return "No messages found matching the query criteria."

        output = f"Found {len(messages)} message(s):\n\n"
        
        def _format_single_message(msg: Message) -> str:
            """Format a single message in the new format: {timestamp} - {indicator} - {name} : {content}"""
            timestamp = msg.created_at if msg.created_at else "N/A"
            indicator = _get_category_indicator(msg.category)
            name = msg.speaker if msg.speaker else ""
            
            if msg.content:
                content = msg.content
                if len(content) > 500:
                    content = content[:500] + "... (truncated)"
            else:
                content = "[No content]"
            
            # Format: {timestamp} - {indicator} - {name} : {content}
            return f"{timestamp} - {indicator} - {name} : {content}"
        
        # For around_time, need to separate messages before and after time_point
        if metadata.time_point:
            time_point = metadata.time_point
            from datetime import datetime
            try:
                time_point_dt = datetime.strptime(time_point, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    time_point_dt = datetime.strptime(time_point, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    time_point_dt = None
            
            if time_point_dt:
                before_messages = []
                after_messages = []
                
                for msg in messages:
                    if msg.created_at:
                        try:
                            msg_dt = datetime.strptime(msg.created_at, '%Y-%m-%d %H:%M:%S')
                        except ValueError:
                            try:
                                msg_dt = datetime.strptime(msg.created_at, '%Y-%m-%d %H:%M:%S.%f')
                            except ValueError:
                                # If parsing fails, treat as after
                                after_messages.append(msg)
                                continue
                        
                        if msg_dt < time_point_dt:
                            before_messages.append(msg)
                        else:
                            after_messages.append(msg)
                    else:
                        after_messages.append(msg)
                
                # Format before messages
                if metadata.has_more_before:
                    output += "[Note: There are more messages before this time point. You may need to query earlier times to see them.]\n\n"
                
                for msg in before_messages:
                    output += _format_single_message(msg) + "\n"
                
                # Add separator if both before and after messages exist
                if before_messages and after_messages:
                    output += f"\n[Time point: {time_point}]\n\n"
                
                # Format after messages
                for msg in after_messages:
                    output += _format_single_message(msg) + "\n"
                
                if metadata.has_more_after:
                    output += f"\n[Note: There are more messages after this time point. You may need to query later times to see them.]\n"
                
                return output
        
        # For by_date and in_range, format normally
        for msg in messages:
            output += _format_single_message(msg) + "\n"
        
        if metadata.has_more_after:
            output += f"\n[Note: There are more messages matching the query criteria. The results are limited to {max_results} messages. You may need to query with a narrower time range or later times to see more messages.]\n"
        
        return output

    async def execute(
        self,
        *,
        query_type: Literal["by_date", "around_time", "in_range", "by_keyword"],
        date: Optional[str] = None,
        time_point: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        keyword: Optional[str] = None,
        **kwargs,
    ) -> ToolResult:
        """
        Execute dialogue history query based on query_type.
        All queries are filtered by category=TELEGRAM by default.

        Args:
            query_type: Type of query to perform
            date: Date string for 'by_date' query (format: 'YYYY-MM-DD')
            time_point: Time point for 'around_time' query (format: 'YYYY-MM-DD HH:MM:SS')
                       Returns messages around this time point (within 1 hour, up to 100 messages per direction)
            start_time: Start time for 'in_range' query (format: 'YYYY-MM-DD HH:MM:SS')
            end_time: End time for 'in_range' query (format: 'YYYY-MM-DD HH:MM:SS')
            keyword: Keyword to search for (required when query_type is 'by_keyword')

        Returns:
            ToolResult containing formatted message list
        """
        try:
            messages: List[Message] = []

            # Internal configuration: max results per query (not exposed to LLM)
            MAX_RESULTS = 100
            target_categories = [MessageCategory.TELEGRAM, MessageCategory.SPEAK_IN_PERSON]
            # Execute query based on type (all queries use category=TELEGRAM by default)
            if query_type == "by_date":
                if not date:
                    raise ToolError(
                        "Parameter 'date' is required when query_type is 'by_date'"
                    )
                messages, metadata = Memory.get_messages_by_date(self.session_id, date, max_results=MAX_RESULTS, categories=target_categories, character_id=self.character_id)
                formatted_output = self._format_messages(messages, metadata, MAX_RESULTS)

            elif query_type == "around_time":
                if not time_point:
                    raise ToolError(
                        "Parameter 'time_point' is required when query_type is 'around_time'"
                    )
                # Use default values: 1 hour range, 100 messages per direction
                # These are internal configuration, not exposed to LLM
                messages, metadata = Memory.get_messages_around_time(
                    self.session_id,
                    time_point, 
                    hours=1.0, 
                    max_messages=MAX_RESULTS,
                    categories=target_categories,
                    character_id=self.character_id
                )
                formatted_output = self._format_messages(messages, metadata, MAX_RESULTS)

            elif query_type == "in_range":
                if not start_time or not end_time:
                    raise ToolError(
                        "Parameters 'start_time' and 'end_time' are required when query_type is 'in_range'"
                    )
                messages, metadata = Memory.get_messages_in_range(self.session_id, start_time, end_time, max_results=MAX_RESULTS, categories=target_categories, character_id=self.character_id)
                formatted_output = self._format_messages(messages, metadata, MAX_RESULTS)

            elif query_type == "by_keyword":
                if not keyword:
                    raise ToolError(
                        "Parameter 'keyword' is required when query_type is 'by_keyword'"
                    )
                # Use Memory to search messages by keyword
                messages, metadata = Memory.search_messages_by_keyword(
                    self.session_id,
                    keyword,
                    category=target_categories,  # Only telegram messages   
                    limit=MAX_RESULTS,
                    offset=0,
                    sort=["created_at:desc"],  # Most recent first
                    character_id=self.character_id
                )
                formatted_output = self._format_messages(messages, metadata, MAX_RESULTS)

            else:
                raise ToolError(
                    f"Invalid query_type: {query_type}. Must be one of: by_date, around_time, in_range, by_keyword"
                )

            # Format and return results
            return ToolResult(content=formatted_output)

        except ToolError:
            raise
        except Exception as e:
            error_msg = f"Failed to query dialogue history: {str(e)}"
            return ToolResult(error=error_msg)