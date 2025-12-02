"""SQLite repository for character records"""
from typing import Any, Dict, List, Optional
import uuid

from app.storage.settings_sqlite_base import SettingsSQLiteBase
from app.utils import get_current_time, get_real_time


class CharacterRepository(SettingsSQLiteBase):
    """Data access layer for character table"""

    def insert_character(
        self,
        name: str,
        roleplay_prompt: Optional[str] = None,
        avatar: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> str:
        """Insert a character entry
        
        Args:
            name: Character name
            roleplay_prompt: Roleplay prompt text
            avatar: Base64 encoded image string
            character_id: Optional character_id (if not provided, generates "char-{16位uuid}")
        
        Returns:
            The character_id of the inserted character
        """
        # Generate character_id if not provided: "char-{16位uuid}"
        if not character_id:
            # Generate 16 hex characters (8 bytes)
            hex_uuid = uuid.uuid4().hex[:16]
            character_id = f"char-{hex_uuid}"
        
        timestamp = get_current_time()
        real_timestamp = get_real_time()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO character (character_id, name, roleplay_prompt, avatar, created_at, updated_at, real_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (character_id, name, roleplay_prompt, avatar, timestamp, timestamp, real_timestamp),
            )
            return character_id

    def list_characters(self) -> List[Dict[str, Any]]:
        """List all characters
        
        Returns:
            List of character dicts ordered by created_at DESC
        """
        return self.fetch_all(
            """
            SELECT id, character_id, name, roleplay_prompt, avatar, created_at, updated_at
            FROM character
            ORDER BY created_at DESC
            """
        )

    def get_by_character_id(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get a character by character_id
        
        Args:
            character_id: Character ID
        
        Returns:
            Character dict if found, None otherwise
        """
        return self.fetch_one(
            """
            SELECT id, character_id, name, roleplay_prompt, avatar, created_at, updated_at
            FROM character
            WHERE character_id = ?
            """,
            (character_id,),
        )

    def update_character(
        self,
        character_id: str,
        name: Optional[str] = None,
        roleplay_prompt: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> bool:
        """Update a character by character_id
        
        Args:
            character_id: Character ID
            name: Optional new name
            roleplay_prompt: Optional new roleplay prompt
            avatar: Optional new avatar (base64 string)
        
        Returns:
            True if updated, False if character not found
        """
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if roleplay_prompt is not None:
            updates.append("roleplay_prompt = ?")
            params.append(roleplay_prompt)
        if avatar is not None:
            updates.append("avatar = ?")
            params.append(avatar)
        
        if not updates:
            return False
        
        # Add updated_at timestamp
        updates.append("updated_at = ?")
        params.append(get_current_time())
        updates.append("real_updated_at = ?")
        params.append(get_real_time())
        
        params.append(character_id)
        
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE character
                SET {', '.join(updates)}
                WHERE character_id = ?
                """,
                params,
            )
            return cursor.rowcount > 0

    def delete_character(self, character_id: str) -> bool:
        """Delete a character by character_id
        
        Args:
            character_id: Character ID
        
        Returns:
            True if deleted, False if character not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM character
                WHERE character_id = ?
                """,
                (character_id,),
            )
            return cursor.rowcount > 0

