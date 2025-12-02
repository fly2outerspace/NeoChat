"""SQLite repository for kv records"""
from typing import Any, Dict, List, Optional

from app.storage.sqlite_base import SQLiteBase
from app.utils import get_current_time, get_real_time


class KVRepository(SQLiteBase):
    """Data access layer for kv table"""

    def insert_kv(
        self,
        session_id: str,
        key: str,
        metadata: str,
        key_type: str = "",
        character_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """Insert a kv entry"""
        # Use session-specific virtual time if available
        timestamp = created_at or get_current_time(session_id=session_id)
        real_timestamp = get_real_time()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO kv (session_id, key, key_type, metadata, character_id, created_at, real_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, key, key_type, metadata, character_id, timestamp, real_timestamp),
            )
            return cursor.lastrowid

    def get_by_key(self, session_id: str, key: str, character_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Get a kv entry by key
        
        Args:
            session_id: Session ID
            key: Key to look up
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        if character_id is not None:
            rows = self.fetch_all(
                """
                SELECT id, session_id, key, key_type, metadata, character_id, created_at, updated_at
                FROM kv
                WHERE session_id = ? AND key = ? AND character_id = ?
                """,
                (session_id, key, character_id),
            )
        else:
            rows = self.fetch_all(
                """
                SELECT id, session_id, key, key_type, metadata, character_id, created_at, updated_at
                FROM kv
                WHERE session_id = ? AND key = ? AND character_id IS NULL
                """,
                (session_id, key),
            )
        return rows[0] if rows else None

    def list_by_session(self, session_id: str, key_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all kv entries under a session, optionally filtered by key_type and character_id
        
        Args:
            session_id: Session ID
            key_type: Optional key type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?"]
        params = [session_id]
        
        if key_type:
            conditions.append("key_type = ?")
            params.append(key_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, key, key_type, metadata, character_id, created_at, updated_at
            FROM kv
            WHERE {where_clause}
            ORDER BY key ASC
            """,
            tuple(params),
        )

    def update_metadata(self, session_id: str, key: str, metadata: str, key_type: Optional[str] = None, character_id: Optional[str] = None) -> bool:
        """Update metadata of a kv entry, optionally update key_type and character_id"""
        conditions = ["session_id = ?", "key = ?"]
        params = []
        
        updates = ["metadata = ?", "updated_at = ?", "real_updated_at = ?"]
        params.extend([metadata, get_current_time(session_id=session_id), get_real_time()])
        
        if key_type is not None:
            updates.append("key_type = ?")
            params.append(key_type)
        
        if character_id is not None:
            updates.append("character_id = ?")
            params.append(character_id)
        
        params.extend([session_id, key])
        
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE kv
                SET {', '.join(updates)}
                WHERE {' AND '.join(conditions)}
                """,
                tuple(params),
            )
            return cursor.rowcount > 0

    def delete_by_key(self, session_id: str, key: str, character_id: Optional[str] = None) -> bool:
        """Delete a kv entry by key
        
        Args:
            session_id: Session ID
            key: Key to delete
            character_id: If None, only deletes entries where character_id IS NULL.
                         If provided, only deletes entries with matching character_id.
        """
        if character_id is not None:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM kv
                    WHERE session_id = ? AND key = ? AND character_id = ?
                    """,
                    (session_id, key, character_id),
                )
                return cursor.rowcount > 0
        else:
            with self._get_cursor() as cursor:
                cursor.execute(
                    """
                    DELETE FROM kv
                    WHERE session_id = ? AND key = ? AND character_id IS NULL
                    """,
                    (session_id, key),
                )
                return cursor.rowcount > 0

    def search_by_keyword(self, session_id: str, keyword: str, key_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Search kv entries by keyword in key or metadata, optionally filtered by key_type and character_id
        
        Args:
            session_id: Session ID
            keyword: Keyword to search for
            key_type: Optional key type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?", "(key LIKE ? OR metadata LIKE ?)"]
        params = [session_id, f"%{keyword}%", f"%{keyword}%"]
        
        if key_type:
            conditions.append("key_type = ?")
            params.append(key_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, key, key_type, metadata, character_id, created_at, updated_at
            FROM kv
            WHERE {where_clause}
            ORDER BY key ASC
            """,
            tuple(params),
        )

