"""SQLite repository for period records (merged scenario and schedule)"""
from typing import Any, Dict, List, Optional

from app.storage.sqlite_base import SQLiteBase
from app.utils import get_current_time, get_real_time


class PeriodRepository(SQLiteBase):
    """Data access layer for period table (unified scenario and schedule)"""

    PERIOD_TYPE_SCENARIO = "scenario"
    PERIOD_TYPE_SCHEDULE = "schedule"

    def insert_period(
        self,
        session_id: str,
        period_id: str,
        period_type: str,
        start_at: str,
        end_at: str,
        content: str = "",
        title: str = "",
        character_id: Optional[str] = None,
        created_at: Optional[str] = None,
    ) -> int:
        """Insert a period entry"""
        content = content or ""
        title = title or ""
        # Use session-specific virtual time if available
        timestamp = created_at or get_current_time(session_id=session_id)
        real_timestamp = get_real_time()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO period (session_id, period_id, period_type, start_at, end_at, content, title, character_id, created_at, real_updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, period_id, period_type, start_at, end_at, content, title, character_id, timestamp, real_timestamp),
            )
            return cursor.lastrowid

    def list_by_session(self, session_id: str, period_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """List all periods under a session, optionally filtered by period_type and character_id
        
        Args:
            session_id: Session ID
            period_type: Optional period type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?"]
        params = [session_id]
        
        if period_type:
            conditions.append("period_type = ?")
            params.append(period_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE {where_clause}
            ORDER BY start_at ASC
            """,
            tuple(params),
        )

    def find_by_time(self, session_id: str, time_point: str, period_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find periods covering a specific time point
        
        Args:
            session_id: Session ID
            time_point: Time point to check
            period_type: Optional period type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?", "start_at <= ?", "end_at >= ?"]
        params = [session_id, time_point, time_point]
        
        if period_type:
            conditions.append("period_type = ?")
            params.append(period_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE {where_clause}
            ORDER BY start_at ASC
            """,
            tuple(params),
        )

    def find_by_time_range(self, session_id: str, start_at: str, end_at: str, period_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find periods that overlap with the given time range
        
        A period overlaps with the query range if:
        - period.start_at <= query.end_at AND period.end_at >= query.start_at
        
        Args:
            session_id: Session ID
            start_at: Start time of the range
            end_at: End time of the range
            period_type: Optional period type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?", "start_at <= ?", "end_at >= ?"]
        params = [session_id, end_at, start_at]
        
        if period_type:
            conditions.append("period_type = ?")
            params.append(period_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE {where_clause}
            ORDER BY start_at ASC
            """,
            tuple(params),
        )

    def find_by_date(self, session_id: str, date: str, period_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Find periods where start_at or end_at matches the date
        
        Args:
            session_id: Session ID
            date: Date to match
            period_type: Optional period type filter
            character_id: If None, only returns entries where character_id IS NULL.
                         If provided, only returns entries with matching character_id.
        """
        conditions = ["session_id = ?", "(date(start_at) = date(?) OR date(end_at) = date(?))"]
        params = [session_id, date, date]
        
        if period_type:
            conditions.append("period_type = ?")
            params.append(period_type)
        
        if character_id is not None:
            conditions.append("character_id = ?")
            params.append(character_id)
        else:
            conditions.append("character_id IS NULL")
        
        where_clause = " AND ".join(conditions)
        return self.fetch_all(
            f"""
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE {where_clause}
            ORDER BY start_at ASC
            """,
            tuple(params),
        )

    def update_content_by_id(self, period_id: int, content: str) -> bool:
        """Update content of a period by database id"""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE period
                SET content = ?
                WHERE id = ?
                """,
                (content, period_id),
            )
            return cursor.rowcount > 0

    def update_content_by_period_id(self, period_id: str, content: str) -> bool:
        """Update content of a period by business period_id"""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE period
                SET content = ?
                WHERE period_id = ?
                """,
                (content, period_id),
            )
            return cursor.rowcount > 0

    def update_by_period_id(
        self,
        period_id: str,
        content: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        title: Optional[str] = None,
    ) -> bool:
        """Update period fields by business period_id"""
        updates = []
        params = []
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        if start_at is not None:
            updates.append("start_at = ?")
            params.append(start_at)
        if end_at is not None:
            updates.append("end_at = ?")
            params.append(end_at)
        if title is not None:
            updates.append("title = ?")
            params.append(title)
        
        if not updates:
            return False
        
        params.append(period_id)
        
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                UPDATE period
                SET {', '.join(updates)}
                WHERE period_id = ?
                """,
                params,
            )
            return cursor.rowcount > 0

    def delete_by_id(self, period_id: int) -> bool:
        """Delete a period by database id"""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM period
                WHERE id = ?
                """,
                (period_id,),
            )
            return cursor.rowcount > 0

    def delete_by_period_id(self, period_id: str) -> bool:
        """Delete a period by business period_id"""
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM period
                WHERE period_id = ?
                """,
                (period_id,),
            )
            return cursor.rowcount > 0

    def get_by_id(self, period_id: int) -> Optional[Dict[str, Any]]:
        """Get a period by database id"""
        rows = self.fetch_all(
            """
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE id = ?
            """,
            (period_id,),
        )
        return rows[0] if rows else None

    def get_by_period_id(self, period_id: str) -> Optional[Dict[str, Any]]:
        """Get a period by business period_id"""
        rows = self.fetch_all(
            """
            SELECT id, session_id, period_id, period_type, start_at, end_at, created_at, content, title, character_id
            FROM period
            WHERE period_id = ?
            """,
            (period_id,),
        )
        return rows[0] if rows else None

