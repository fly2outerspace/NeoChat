"""SQLite repository for session clock records"""
import json
from typing import Any, Dict, Optional

from app.storage.sqlite_base import SQLiteBase
from app.utils import get_real_time


class SessionClockRepository(SQLiteBase):
    """Data access layer for session_clock table"""

    def get_by_session_id(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session clock by session_id
        
        Args:
            session_id: Session ID
        
        Returns:
            Session clock dict if found, None otherwise
        """
        return self.fetch_one(
            """
            SELECT session_id, mode, offset_seconds, fixed_time, speed,
                   virtual_base, real_base, actions, updated_at, real_updated_at
            FROM session_clock
            WHERE session_id = ?
            """,
            (session_id,),
        )

    def insert_or_update_clock(
        self,
        session_id: str,
        base_virtual: str,
        base_real: str,
        actions: Optional[list[dict]] = None,
    ) -> bool:
        """Insert or update session clock timeline"""
        real_now = get_real_time()
        actions_json = json.dumps(actions or [])
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO session_clock
                (session_id, mode, offset_seconds, fixed_time, speed,
                 virtual_base, real_base, actions, updated_at, real_updated_at)
                VALUES (?, 'actions', 0.0, NULL, 1.0, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    base_virtual,
                    base_real,
                    actions_json,
                    real_now,
                    real_now,
                ),
            )
            return cursor.rowcount > 0

    def delete_by_session_id(self, session_id: str) -> bool:
        """Delete session clock by session_id
        
        Args:
            session_id: Session ID
        
        Returns:
            True if deleted, False if not found
        """
        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM session_clock WHERE session_id = ?",
                (session_id,)
            )
            return cursor.rowcount > 0

    def list_all_clocks(self) -> list[Dict[str, Any]]:
        """List all session clocks
        
        Returns:
            List of session clock dicts
        """
        return self.fetch_all("""
            SELECT session_id, mode, offset_seconds, fixed_time, speed,
                   virtual_base, real_base, actions, updated_at, real_updated_at
            FROM session_clock
            ORDER BY session_id
        """)

