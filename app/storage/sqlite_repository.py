"""SQLite implementation of MessageRepository"""
import sqlite3
from typing import List, Dict, Any, Optional, Tuple

from app.storage.message_repository import MessageRepository
from app.storage.sqlite_base import SQLiteBase
from app.storage.message_character_repository import MessageCharacterRepository
from app.utils import get_current_time, get_real_time
from app.logger import logger


class SQLiteMessageRepository(SQLiteBase, MessageRepository):
    """SQLite implementation of message repository"""
    
    def __init__(self):
        super().__init__()
        self._character_repo = MessageCharacterRepository()
    
    def insert_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str],
        tool_calls: Optional[str],
        tool_name: Optional[str],
        speaker: Optional[str],
        tool_call_id: Optional[str],
        created_at: Optional[str] = None,
        category: int = 0,
        character_id_list: Optional[List[str]] = None,
    ) -> int:
        """Insert a message into database
        
        Args:
            session_id: Session ID
            role: Message role
            content: Message content
            tool_calls: Serialized tool calls JSON string
            tool_name: Optional tool/function name (for tool messages)
            speaker: Optional speaker/agent name
            tool_call_id: Optional tool call ID
            created_at: Optional timestamp (ISO format: 'YYYY-MM-DD HH:MM:SS'). 
                       If None, uses current time.
            category: Message category identifier (default: 0)
            character_id_list: Optional list of character IDs to associate with this message
        
        Returns:
            The ID of the inserted message
        """
        # created_at should be provided by Message object, but fallback to current time if not set
        if created_at is None:
            from app.utils import get_current_time
            created_at = get_current_time(session_id=session_id)
        real_now = get_real_time()
        with self._get_cursor() as cursor:
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category, real_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (session_id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category, real_now))
            message_id = cursor.lastrowid
            
            # Insert character associations if provided - use same cursor to avoid nested connections
            if character_id_list:
                for character_id in character_id_list:
                    try:
                        cursor.execute("""
                            INSERT INTO message_characters (message_id, character_id)
                            VALUES (?, ?)
                        """, (message_id, character_id))
                    except sqlite3.IntegrityError as e:
                        # Ignore duplicate key errors (UNIQUE constraint)
                        if "UNIQUE constraint" not in str(e):
                            logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
                    except Exception as e:
                        logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
            
            return message_id
    
    def get_messages_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session, returns raw dicts with character_ids included"""
        rows = self.fetch_all("""
            SELECT id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, (session_id,))
        
        # Add character_ids to each message
        if rows:
            message_ids = [row["id"] for row in rows]
            character_map = self._character_repo.get_character_ids_by_messages(message_ids)
            for row in rows:
                row["character_ids"] = character_map.get(row["id"], [])
        
        return rows
    
    def delete_messages_by_session(self, session_id: str) -> None:
        """Delete all messages for a session
        
        Note: Associated character relationships will be automatically deleted
        due to ON DELETE CASCADE foreign key constraint
        """
        self.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
    
    def get_messages_around_time(
        self,
        session_id: str,
        time_point: str,
        hours: float = 1.0,
        max_messages: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get messages around a specific time point.
        
        Algorithm: Scan forward and backward from time_point within the time range,
        then merge and sort by time distance, return the closest messages.
        
        Args:
            session_id: Session ID
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            hours: Time range in hours before and after time_point (default: 1.0)
            max_messages: Max messages to scan in each direction (default: 100)
            categories: Optional list of category filters. If None or empty, returns all categories.
            
        Returns:
            List of message dicts sorted by created_at, closest to time_point first
        """
        from datetime import datetime
        
        # Parse time_point for Python datetime calculation
        try:
            time_point_dt = datetime.strptime(time_point, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            # Try alternative format if needed
            time_point_dt = datetime.strptime(time_point, '%Y-%m-%d %H:%M:%S.%f')
        
        hours_str = str(abs(hours))
        
        # Query max_messages + 1 to check if there are more messages in each direction
        limit = max_messages + 1
        
        # Build category filter clause
        category_filter = ""
        category_params = []
        if categories:
            placeholders = ",".join(["?"] * len(categories))
            category_filter = f"AND category IN ({placeholders})"
            category_params = categories
        
        # Build character_id filter clause (database-level filtering)
        character_filter = ""
        character_params = []
        if character_id:
            # Include messages that have no character associations (visible to all)
            # OR messages that have an association with the specified character_id
            character_filter = """AND (
                NOT EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id)
                OR EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id AND character_id = ?)
            )"""
            character_params = [character_id]
        
        # Query 1: Messages before time_point (scan backward, query limit + 1 to check for more)
        before_all = self.fetch_all(f"""
            SELECT id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category
            FROM messages
            WHERE session_id = ?
              AND created_at >= datetime(?, ?)
              AND created_at < ?
              {category_filter}
              {character_filter}
            ORDER BY created_at DESC
            LIMIT ?
        """, (session_id, time_point, f"-{hours_str} hours", time_point) + tuple(category_params) + tuple(character_params) + (limit,))
        
        # Add character_ids to before messages
        if before_all:
            message_ids = [row["id"] for row in before_all]
            character_map = self._character_repo.get_character_ids_by_messages(message_ids)
            for row in before_all:
                row["character_ids"] = character_map.get(row["id"], [])
        
        # Take only max_messages messages for processing
        before_messages = before_all[:max_messages]
        
        # Query 2: Messages after time_point (scan forward, query limit + 1 to check for more)
        after_all = self.fetch_all(f"""
            SELECT id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category
            FROM messages
            WHERE session_id = ?
              AND created_at >= ?
              AND created_at <= datetime(?, ?)
              {category_filter}
              {character_filter}
            ORDER BY created_at ASC
            LIMIT ?
        """, (session_id, time_point, time_point, f"+{hours_str} hours") + tuple(category_params) + tuple(character_params) + (limit,))
        
        # Add character_ids to after messages
        if after_all:
            message_ids = [row["id"] for row in after_all]
            character_map = self._character_repo.get_character_ids_by_messages(message_ids)
            for row in after_all:
                row["character_ids"] = character_map.get(row["id"], [])
        
        # Take only max_messages messages for processing
        after_messages = after_all[:max_messages]
        
        # Merge messages
        all_messages = before_messages + after_messages
        
        # Helper function to parse datetime (reusable)
        def parse_datetime(time_str: str) -> Optional[datetime]:
            """Parse datetime string with multiple format support"""
            try:
                return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                try:
                    return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
                except ValueError:
                    return None
        
        # Calculate time distance and sort by proximity to time_point
        # Also track which messages are before/after for later counting
        def calculate_time_distance_and_direction(msg: Dict[str, Any]) -> Tuple[float, bool]:
            """Calculate time distance and determine if message is before time_point
            
            Returns:
                Tuple of (time_distance, is_before)
            """
            msg_created_at = msg['created_at']
            msg_dt = parse_datetime(msg_created_at)
            if msg_dt is None:
                # If parsing fails, treat as after and return large distance
                return (float('inf'), False)
            
            time_distance = abs((msg_dt - time_point_dt).total_seconds())
            is_before = msg_dt < time_point_dt
            return (time_distance, is_before)
        
        # Sort by time distance from time_point, then by id (primary key) for stable ordering
        # Store direction info in a temporary list for counting
        messages_with_direction = []
        for msg in all_messages:
            time_distance, is_before = calculate_time_distance_and_direction(msg)
            # Use id (primary key) for stable sorting when time distance is the same
            msg_id = msg.get('id', 0)
            messages_with_direction.append((time_distance, msg_id, is_before, msg))
        
        # Sort by time distance, then by id for stable ordering
        messages_with_direction.sort(key=lambda x: (x[0], x[1]))
        
        # Take the closest messages (up to max_messages, not * 2)
        # We scan up to 100 in each direction, but only return the closest 100 overall
        closest_messages_with_direction = messages_with_direction[:max_messages]
        
        # Extract messages and count before/after
        result = []
        before_count_in_result = 0
        after_count_in_result = 0
        
        for _, _, is_before, msg in closest_messages_with_direction:
            result.append(msg)
            if is_before:
                before_count_in_result += 1
            else:
                after_count_in_result += 1
        
        # Note: character_id filtering is now done at database level in SQL queries above
        # We still need to fetch character_ids for the result messages (for Message object construction)
        # but no application-level filtering is needed
        
        # Final sort by created_at for chronological output
        result.sort(key=lambda msg: msg['created_at'])
        
        # Determine if there are more messages based on what's actually in the result
        # If result contains fewer messages from a direction than we queried, there are more
        has_more_before = before_count_in_result < len(before_all)
        has_more_after = after_count_in_result < len(after_all)
        
        # Add metadata to the first message dict to indicate if there are more messages
        # We'll use a special key that won't conflict with actual message data
        if result:
            result[0]['_metadata'] = {
                'has_more_before': has_more_before,
                'has_more_after': has_more_after,
                'time_point': time_point
            }
        
        return result
    
    def get_messages_in_range(
        self,
        session_id: str,
        start_time: str,
        end_time: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get messages within a specific time range"""
        # Query max_results + 1 to check if there are more messages
        limit = max_results + 1
        
        # Build category filter clause
        category_filter = ""
        category_params = []
        if categories:
            placeholders = ",".join(["?"] * len(categories))
            category_filter = f"AND category IN ({placeholders})"
            category_params = categories
        
        # Build character_id filter clause (database-level filtering)
        character_filter = ""
        character_params = []
        if character_id:
            # Include messages that have no character associations (visible to all)
            # OR messages that have an association with the specified character_id
            character_filter = """AND (
                NOT EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id)
                OR EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id AND character_id = ?)
            )"""
            character_params = [character_id]
        
        all_rows = self.fetch_all(f"""
            SELECT id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category
            FROM messages
            WHERE session_id = ?
              AND created_at >= ?
              AND created_at <= ?
              {category_filter}
              {character_filter}
            ORDER BY created_at ASC
            LIMIT ?
        """, (session_id, start_time, end_time) + tuple(category_params) + tuple(character_params) + (limit,))
        
        # Add character_ids to messages
        if all_rows:
            message_ids = [row["id"] for row in all_rows]
            character_map = self._character_repo.get_character_ids_by_messages(message_ids)
            for row in all_rows:
                row["character_ids"] = character_map.get(row["id"], [])
        
        # Check if there are more messages
        has_more_after = len(all_rows) > max_results
        
        # Return only max_results messages
        result = all_rows[:max_results]
        
        # Add metadata to the first message dict if there are more messages
        if result and has_more_after:
            result[0]['_metadata'] = {
                'has_more_before': False,
                'has_more_after': True,
                'time_point': None
            }
        
        return result
    
    def get_messages_by_date(
        self,
        session_id: str,
        date: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all messages on a specific date"""
        # Query max_results + 1 to check if there are more messages
        limit = max_results + 1
        
        # Build category filter clause
        category_filter = ""
        category_params = []
        if categories:
            placeholders = ",".join(["?"] * len(categories))
            category_filter = f"AND category IN ({placeholders})"
            category_params = categories
        
        # Build character_id filter clause (database-level filtering)
        character_filter = ""
        character_params = []
        if character_id:
            # Include messages that have no character associations (visible to all)
            # OR messages that have an association with the specified character_id
            character_filter = """AND (
                NOT EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id)
                OR EXISTS (SELECT 1 FROM message_characters WHERE message_id = messages.id AND character_id = ?)
            )"""
            character_params = [character_id]
        
        # Use date() function to extract date part and compare
        all_rows = self.fetch_all(f"""
            SELECT id, role, content, tool_calls, tool_name, speaker, tool_call_id, created_at, category
            FROM messages
            WHERE session_id = ?
              AND date(created_at) = date(?)
              {category_filter}
              {character_filter}
            ORDER BY created_at ASC
            LIMIT ?
        """, (session_id, date) + tuple(category_params) + tuple(character_params) + (limit,))
        
        # Add character_ids to messages
        if all_rows:
            message_ids = [row["id"] for row in all_rows]
            character_map = self._character_repo.get_character_ids_by_messages(message_ids)
            for row in all_rows:
                row["character_ids"] = character_map.get(row["id"], [])
        
        # Check if there are more messages
        has_more_after = len(all_rows) > max_results
        
        # Return only max_results messages
        result = all_rows[:max_results]
        
        # Add metadata to the first message dict if there are more messages
        if result and has_more_after:
            result[0]['_metadata'] = {
                'has_more_before': False,
                'has_more_after': True,
                'time_point': None
            }
        
        return result
    
    def count_dialogue_messages(
        self,
        session_id: str,
        speaker: str,
        categories: Optional[List[int]] = None
    ) -> int:
        """Count dialogue messages by speaker and categories
        
        This is an efficient COUNT query for calculating dialogue turns.
        
        Args:
            session_id: Session ID
            speaker: Speaker name to filter by
            categories: List of category filters (default: [1, 2] for TELEGRAM and SPEAK_IN_PERSON)
            
        Returns:
            Count of matching messages
        """
        # Default to TELEGRAM(1) and SPEAK_IN_PERSON(2)
        if categories is None:
            categories = [1, 2]
        
        if not categories:
            return 0
        
        # Build category filter
        category_placeholders = ",".join("?" * len(categories))
        
        with self._get_cursor() as cursor:
            cursor.execute(f"""
                SELECT COUNT(*) as count
                FROM messages
                WHERE session_id = ?
                  AND speaker = ?
                  AND category IN ({category_placeholders})
            """, (session_id, speaker) + tuple(categories))
            
            row = cursor.fetchone()
            return row["count"] if row else 0
