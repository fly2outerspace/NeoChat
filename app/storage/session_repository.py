"""Repository for session management"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

from app.storage.sqlite_base import SQLiteBase
from app.utils import get_current_time, get_real_time


class SessionRepository(ABC):
    """Abstract repository for session operations"""
    
    @abstractmethod
    def create_session(self, session_id: str, name: str) -> None:
        """Create a new session if it doesn't exist"""
        pass
    
    @abstractmethod
    def update_session_timestamp(self, session_id: str) -> None:
        """Update session's updated_at timestamp"""
        pass
    
    @abstractmethod
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with message counts"""
        pass


class SQLiteSessionRepository(SQLiteBase, SessionRepository):
    """SQLite implementation of session repository"""
    
    def create_session(self, session_id: str, name: str) -> None:
        """Create a new session if it doesn't exist"""
        now = get_current_time(session_id=session_id)
        real_now = get_real_time()
        self.execute(
            "INSERT OR IGNORE INTO sessions (id, name, created_at, updated_at, real_updated_at) VALUES (?, ?, ?, ?, ?)",
            (session_id, name, now, now, real_now)
        )
    
    def update_session_timestamp(self, session_id: str) -> None:
        """Update session's updated_at timestamp"""
        now = get_current_time(session_id=session_id)
        real_now = get_real_time()
        self.execute(
            "UPDATE sessions SET updated_at = ?, real_updated_at = ? WHERE id = ?",
            (now, real_now, session_id)
        )
    
    def list_sessions(self) -> List[Dict[str, Any]]:
        """List all sessions with message counts"""
        return self.fetch_all("""
            SELECT s.id, s.name, s.created_at, s.updated_at,
                   COUNT(m.id) as message_count
            FROM sessions s
            LEFT JOIN messages m ON s.id = m.session_id
            GROUP BY s.id
            ORDER BY s.updated_at DESC
        """)

