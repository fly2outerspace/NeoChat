"""Base class for SQLite database operations"""
import time
from contextlib import contextmanager
from typing import Iterator, List, Dict, Any, Optional, Tuple

import sqlite3

from app.storage.database import get_connection
from app.logger import logger


class SQLiteBase:
    """Base class for SQLite database operations
    
    Provides common database operations and connection management.
    Subclasses can inherit this to avoid repetitive connection handling.
    """
    
    @contextmanager
    def _get_cursor(self, timeout: float = 5.0, max_retries: int = 3, retry_delay: float = 0.1) -> Iterator[sqlite3.Cursor]:
        """Context manager for database cursor with retry mechanism
        
        Usage:
            with self._get_cursor() as cursor:
                cursor.execute("SELECT * FROM table")
                rows = cursor.fetchall()
        
        Args:
            timeout: Timeout in seconds for database operations (default: 5.0)
            max_retries: Maximum number of retry attempts for locked database (default: 3)
            retry_delay: Delay in seconds between retries (default: 0.1)
        """
        conn = None
        last_exception = None
        
        for attempt in range(1, max_retries + 1):
            try:
                conn = get_connection(timeout=timeout)
                cursor = conn.cursor()
                try:
                    yield cursor
                    conn.commit()
                    return
                except sqlite3.OperationalError as e:
                    conn.rollback()
                    if "database is locked" in str(e).lower() and attempt < max_retries:
                        logger.warning(f"Database locked, retrying ({attempt}/{max_retries})...")
                        if conn:
                            conn.close()
                        time.sleep(retry_delay * attempt)  # Exponential backoff
                        last_exception = e
                        continue
                    else:
                        logger.error(f"Database operation failed: {e}")
                        raise
                except Exception as e:
                    conn.rollback()
                    logger.error(f"Database operation failed: {e}")
                    raise
                finally:
                    if conn:
                        conn.close()
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e).lower() and attempt < max_retries:
                    logger.warning(f"Database connection failed, retrying ({attempt}/{max_retries})...")
                    time.sleep(retry_delay * attempt)  # Exponential backoff
                    last_exception = e
                    continue
                else:
                    raise
        
        # If we exhausted all retries, raise the last exception
        if last_exception:
            raise last_exception
    
    def execute(
        self,
        sql: str,
        params: Optional[Tuple] = None,
        fetch: bool = False
    ) -> Optional[List[Dict[str, Any]]]:
        """Execute a SQL statement
        
        Args:
            sql: SQL statement
            params: Parameters for the SQL statement
            fetch: If True, fetch and return results as list of dicts
        
        Returns:
            List of dicts if fetch=True, None otherwise
        """
        with self._get_cursor() as cursor:
            cursor.execute(sql, params or ())
            if fetch:
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
            return None
    
    def execute_many(self, sql: str, params_list: List[Tuple]) -> None:
        """Execute a SQL statement multiple times with different parameters
        
        Args:
            sql: SQL statement
            params_list: List of parameter tuples
        """
        with self._get_cursor() as cursor:
            cursor.executemany(sql, params_list)
    
    def fetch_one(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> Optional[Dict[str, Any]]:
        """Fetch a single row
        
        Args:
            sql: SQL statement
            params: Parameters for the SQL statement
        
        Returns:
            Dict if found, None otherwise
        """
        with self._get_cursor() as cursor:
            cursor.execute(sql, params or ())
            row = cursor.fetchone()
            return dict(row) if row else None
    
    def fetch_all(
        self,
        sql: str,
        params: Optional[Tuple] = None
    ) -> List[Dict[str, Any]]:
        """Fetch all rows
        
        Args:
            sql: SQL statement
            params: Parameters for the SQL statement
        
        Returns:
            List of dicts
        """
        with self._get_cursor() as cursor:
            cursor.execute(sql, params or ())
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

