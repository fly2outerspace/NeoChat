"""SQLite repository for character records in archive/working databases"""
from typing import Any, Dict, List, Optional
import uuid

from app.storage.sqlite_base import SQLiteBase
from app.utils import get_current_time, get_real_time
from app.logger import logger


class ArchiveCharacterRepository(SQLiteBase):
    """Data access layer for character table in archive/working databases
    
    This repository operates on the working database (working.db) or archive databases,
    NOT on the settings database. Use CharacterRepository for settings.db operations.
    """

    def get_by_character_id(self, character_id: str) -> Optional[Dict[str, Any]]:
        """Get a character by character_id from archive/working database
        
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

    def insert_character(
        self,
        name: str,
        roleplay_prompt: Optional[str] = None,
        avatar: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> str:
        """Insert a character entry into archive/working database
        
        Args:
            name: Character name
            roleplay_prompt: Roleplay prompt text
            avatar: Base64 encoded image string (optional, usually None for archive characters)
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

    def upsert_character(
        self,
        character_id: str,
        name: str,
        roleplay_prompt: Optional[str] = None,
        avatar: Optional[str] = None,
    ) -> str:
        """Upsert a character (insert if not exists, update only empty fields if exists)
        
        Strategy:
        - If character doesn't exist: insert with all provided fields
        - If character exists:
          - Keep existing non-empty fields (don't overwrite)
          - Only update fields that are empty in database but provided in request
        
        Args:
            character_id: Character ID (required)
            name: Character name
            roleplay_prompt: Optional roleplay prompt text
            avatar: Optional avatar (base64 string)
        
        Returns:
            The character_id
        """
        existing = self.get_by_character_id(character_id)
        
        if not existing:
            # Character doesn't exist, insert new
            return self.insert_character(
                name=name,
                roleplay_prompt=roleplay_prompt,
                avatar=avatar,
                character_id=character_id,
            )
        else:
            # Character exists, update only empty fields
            updates = []
            params = []
            
            # Only update name if current name is empty or None
            if not existing.get("name") and name:
                updates.append("name = ?")
                params.append(name)
            
            # Only update roleplay_prompt if current is empty or None
            if not existing.get("roleplay_prompt") and roleplay_prompt:
                updates.append("roleplay_prompt = ?")
                params.append(roleplay_prompt)
            
            # Only update avatar if current is empty or None
            if not existing.get("avatar") and avatar:
                updates.append("avatar = ?")
                params.append(avatar)
            
            # If we have updates, apply them
            if updates:
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
                logger.debug(f"Updated character {character_id} in archive database (filled empty fields)")
            
            return character_id

    def list_characters(self) -> List[Dict[str, Any]]:
        """List all characters in archive/working database
        
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

