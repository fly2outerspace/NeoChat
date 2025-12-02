"""Repository for message-character associations"""
import sqlite3
from typing import List, Optional, Any
from app.storage.sqlite_base import SQLiteBase


class MessageCharacterRepository(SQLiteBase):
    """Repository for managing message-character associations"""
    
    def insert_associations(self, message_id: int, character_ids: List[str], cursor: Optional[Any] = None) -> None:
        """Insert associations between a message and multiple characters
        
        Args:
            message_id: Message ID
            character_ids: List of character IDs to associate
            cursor: Optional existing cursor to use (avoids nested connections).
                   If None, creates a new connection.
        """
        if not character_ids:
            return
        
        if cursor is not None:
            # Use provided cursor (same transaction)
            for character_id in character_ids:
                try:
                    cursor.execute("""
                        INSERT INTO message_characters (message_id, character_id)
                        VALUES (?, ?)
                    """, (message_id, character_id))
                except sqlite3.IntegrityError as e:
                    # Ignore duplicate key errors (UNIQUE constraint)
                    if "UNIQUE constraint" not in str(e):
                        from app.logger import logger
                        logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
                except Exception as e:
                    from app.logger import logger
                    logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
        else:
            # Create new connection (for backward compatibility)
            with self._get_cursor() as new_cursor:
                for character_id in character_ids:
                    try:
                        new_cursor.execute("""
                            INSERT INTO message_characters (message_id, character_id)
                            VALUES (?, ?)
                        """, (message_id, character_id))
                    except sqlite3.IntegrityError as e:
                        # Ignore duplicate key errors (UNIQUE constraint)
                        if "UNIQUE constraint" not in str(e):
                            from app.logger import logger
                            logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
                    except Exception as e:
                        from app.logger import logger
                        logger.warning(f"Failed to insert association {message_id}-{character_id}: {e}")
    
    def get_character_ids_by_message(self, message_id: int) -> List[str]:
        """Get all character IDs associated with a message
        
        Args:
            message_id: Message ID
            
        Returns:
            List of character IDs
        """
        rows = self.fetch_all("""
            SELECT character_id
            FROM message_characters
            WHERE message_id = ?
            ORDER BY created_at ASC
        """, (message_id,))
        return [row["character_id"] for row in rows]
    
    def get_message_ids_by_character(self, character_id: str) -> List[int]:
        """Get all message IDs associated with a character
        
        Args:
            character_id: Character ID
            
        Returns:
            List of message IDs
        """
        rows = self.fetch_all("""
            SELECT message_id
            FROM message_characters
            WHERE character_id = ?
            ORDER BY created_at ASC
        """, (character_id,))
        return [row["message_id"] for row in rows]
    
    def delete_associations_by_message(self, message_id: int) -> None:
        """Delete all associations for a message
        
        Args:
            message_id: Message ID
        """
        self.execute("DELETE FROM message_characters WHERE message_id = ?", (message_id,))
    
    def delete_associations_by_character(self, character_id: str) -> None:
        """Delete all associations for a character
        
        Args:
            character_id: Character ID
        """
        self.execute("DELETE FROM message_characters WHERE character_id = ?", (character_id,))
    
    def get_character_ids_by_messages(self, message_ids: List[int]) -> dict[int, List[str]]:
        """Get character IDs for multiple messages
        
        Args:
            message_ids: List of message IDs
            
        Returns:
            Dictionary mapping message_id to list of character_ids
        """
        if not message_ids:
            return {}
        
        placeholders = ",".join(["?"] * len(message_ids))
        rows = self.fetch_all(f"""
            SELECT message_id, character_id
            FROM message_characters
            WHERE message_id IN ({placeholders})
            ORDER BY message_id, created_at ASC
        """, tuple(message_ids))
        
        result = {}
        for row in rows:
            msg_id = row["message_id"]
            char_id = row["character_id"]
            if msg_id not in result:
                result[msg_id] = []
            result[msg_id].append(char_id)
        
        # Ensure all message_ids are in result (even if empty)
        for msg_id in message_ids:
            if msg_id not in result:
                result[msg_id] = []
        
        return result

