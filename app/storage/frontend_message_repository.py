"""Repository for frontend display messages"""
from typing import Any, Dict, List, Optional

from app.storage.sqlite_base import SQLiteBase
from app.logger import logger


class FrontendMessageRepository(SQLiteBase):
    """Data access layer for frontend_messages table"""
    
    def insert_message(
        self,
        session_id: str,
        client_message_id: str,
        role: str,
        message_kind: str,
        content: str = "",
        tool_name: Optional[str] = None,
        tool_call_id: Optional[str] = None,
        input_mode: Optional[str] = None,
        character_id: Optional[str] = None,
        display_order: Optional[int] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """Insert or update a frontend message (upsert by client_message_id)
        
        Args:
            session_id: Session ID
            client_message_id: Unique client-side message ID (e.g., tool_call_id for tool outputs)
            role: Message role ('user' or 'assistant')
            message_kind: Message kind ('text', 'tool_output', 'user', 'system')
            content: Message content
            tool_name: Optional tool name (for inline tools or tool outputs)
            tool_call_id: Optional tool call ID (for tool output messages)
            input_mode: Optional input mode (for user messages)
            character_id: Optional character ID (for assistant messages)
            display_order: Optional display order (auto-incremented if not provided)
        
        Returns:
            The ID of the inserted/updated message
        """
        with self._get_cursor() as cursor:
            # Get max display_order for this session if not provided
            if display_order is None:
                cursor.execute("""
                    SELECT COALESCE(MAX(display_order), -1) + 1
                    FROM frontend_messages
                    WHERE session_id = ?
                """, (session_id,))
                display_order = cursor.fetchone()[0]
            
            # Use INSERT OR REPLACE to handle upsert
            # If created_at is provided, use it; otherwise let database use DEFAULT CURRENT_TIMESTAMP
            if created_at is not None:
                cursor.execute("""
                    INSERT OR REPLACE INTO frontend_messages 
                    (session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at))
            else:
                cursor.execute("""
                    INSERT OR REPLACE INTO frontend_messages 
                    (session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order))
            
            # Get the ID (either newly inserted or existing)
            cursor.execute("""
                SELECT id FROM frontend_messages
                WHERE session_id = ? AND client_message_id = ?
            """, (session_id, client_message_id))
            result = cursor.fetchone()
            return result[0] if result else cursor.lastrowid
    
    def get_messages_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all frontend messages for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            List of message dicts ordered by display_order ASC, then created_at ASC
        """
        rows = self.fetch_all("""
            SELECT id, session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at
            FROM frontend_messages
            WHERE session_id = ?
            ORDER BY display_order ASC, created_at ASC
        """, (session_id,))
        
        result = []
        for row in rows:
            result.append(dict(row))
        
        return result
    
    def get_message_by_client_id(self, session_id: str, client_message_id: str) -> Optional[Dict[str, Any]]:
        """Get a message by client_message_id
        
        Args:
            session_id: Session ID
            client_message_id: Client message ID
        
        Returns:
            Message dict or None if not found
        """
        rows = self.fetch_all("""
            SELECT id, session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at
            FROM frontend_messages
            WHERE session_id = ? AND client_message_id = ?
        """, (session_id, client_message_id))
        
        if not rows:
            return None
        
        return dict(rows[0])
    
    def delete_messages_by_session(self, session_id: str) -> int:
        """Delete all frontend messages for a session
        
        Args:
            session_id: Session ID
        
        Returns:
            Number of deleted messages
        """
        with self._get_cursor() as cursor:
            cursor.execute("""
                DELETE FROM frontend_messages
                WHERE session_id = ?
            """, (session_id,))
            return cursor.rowcount
    
    def delete_all_messages(self) -> int:
        """Delete all frontend messages (used when loading archives)
        
        Returns:
            Number of deleted messages
        """
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM frontend_messages")
            return cursor.rowcount
    
    def update_message(
        self,
        message_id: int,
        content: Optional[str] = None,
        tool_name: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> bool:
        """Update an existing frontend message
        
        Args:
            message_id: Message ID to update
            content: Optional new content
            tool_name: Optional new tool name
        
        Returns:
            True if message was updated, False if message not found
        """
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if tool_name is not None:
            updates.append("tool_name = ?")
            params.append(tool_name)
        
        if created_at is not None:
            updates.append("created_at = ?")
            params.append(created_at)
        
        if not updates:
            # No fields to update
            return False
        
        params.append(message_id)
        
        with self._get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE frontend_messages
                SET {', '.join(updates)}
                WHERE id = ?
            """, params)
            return cursor.rowcount > 0
    
    def update_message_by_client_id(
        self,
        session_id: str,
        client_message_id: str,
        content: Optional[str] = None,
        tool_name: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> bool:
        """Update an existing frontend message by client_message_id
        
        Args:
            session_id: Session ID
            client_message_id: Client message ID
            content: Optional new content
            tool_name: Optional new tool name
        
        Returns:
            True if message was updated, False if message not found
        """
        # Build update query dynamically based on provided fields
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if tool_name is not None:
            updates.append("tool_name = ?")
            params.append(tool_name)
        
        if created_at is not None:
            updates.append("created_at = ?")
            params.append(created_at)
        
        if not updates:
            # No fields to update
            return False
        
        params.extend([session_id, client_message_id])
        
        with self._get_cursor() as cursor:
            cursor.execute(f"""
                UPDATE frontend_messages
                SET {', '.join(updates)}
                WHERE session_id = ? AND client_message_id = ?
            """, params)
            return cursor.rowcount > 0
    
    def get_last_message_by_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the last message for a session (by display_order)
        
        Args:
            session_id: Session ID
        
        Returns:
            Last message dict or None if no messages found
        """
        rows = self.fetch_all("""
            SELECT id, session_id, client_message_id, role, message_kind, content, tool_name, tool_call_id, input_mode, character_id, display_order, created_at
            FROM frontend_messages
            WHERE session_id = ?
            ORDER BY display_order DESC, created_at DESC
            LIMIT 1
        """, (session_id,))
        
        if not rows:
            return None
        
        return dict(rows[0])

