"""Database manager for archive management"""
import shutil
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any

from app.logger import logger
from app.storage.meilisearch_service import MeilisearchService


class DatabaseManager:
    """Singleton manager for database file and archive operations"""
    
    _instance: Optional["DatabaseManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation"""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize database manager"""
        if self._initialized:
            return
        
        # Project root directory
        self._project_root = Path(__file__).parent.parent.parent
        
        # Directory paths
        self._data_dir = self._project_root / "data"
        self._archives_dir = self._data_dir / "archives"
        
        # Create directories if they don't exist
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._archives_dir.mkdir(parents=True, exist_ok=True)
        
        # Working database path (temporary database for current operations)
        # All operations use this database, frontend doesn't need to know about it
        self._working_db_path = self._data_dir / "working.db"
        
        # Lock for thread-safe operations
        self._operation_lock = threading.Lock()
        
        self._initialized = True
    
    def initialize_working_database(self):
        """Initialize working database on startup
        
        If working database doesn't exist, create an empty one.
        """
        try:
            # Ensure working database exists and is initialized
            if not self._working_db_path.exists():
                logger.info("Working database does not exist, initializing...")
                # Use init_database_for_path to avoid recursion
                from app.storage.database import init_database_for_path
                init_database_for_path(self._working_db_path)
                logger.info(f"Initialized working database at {self._working_db_path}")
        except Exception as e:
            logger.error(f"Failed to initialize working database: {e}", exc_info=True)
    
    def get_current_db_path(self) -> Path:
        """Get current working database file path
        
        Always returns the working database path.
        All operations use this temporary database.
        """
        # Ensure working database exists
        if not self._working_db_path.exists():
            from app.storage.database import init_database_for_path
            init_database_for_path(self._working_db_path)
        
        return self._working_db_path
    
    def get_connection(self, timeout: float = 5.0) -> sqlite3.Connection:
        """Get database connection to current database
        
        Args:
            timeout: Timeout in seconds for database operations
            
        Returns:
            SQLite connection object
        """
        db_path = self.get_current_db_path()
        
        # Ensure database is initialized
        if not db_path.exists():
            logger.info(f"Database file does not exist, initializing: {db_path}")
            # Use init_database_for_path to avoid recursion
            from app.storage.database import init_database_for_path
            init_database_for_path(db_path)
        
        conn = sqlite3.connect(str(db_path), check_same_thread=False, timeout=timeout)
        conn.row_factory = sqlite3.Row
        return conn
    
    def create_archive(self, archive_name: str) -> str:
        """Create a new archive as a copy of working database
        
        This copies the current working database to the archive directory.
        
        Args:
            archive_name: Name of the archive (will be sanitized for filename)
            
        Returns:
            Archive name (sanitized)
            
        Raises:
            ValueError: If archive name is invalid or already exists
        """
        with self._operation_lock:
            # Sanitize archive name for filename
            sanitized_name = self._sanitize_filename(archive_name)
            
            if not sanitized_name:
                raise ValueError("Archive name cannot be empty")
            
            archive_path = self._archives_dir / f"{sanitized_name}.db"
            
            # Check if archive already exists
            if archive_path.exists():
                raise ValueError(f"Archive '{archive_name}' already exists")
            
            try:
                # Get working database path
                working_db_path = self.get_current_db_path()
                
                # Check if working database exists
                if not working_db_path.exists():
                    raise ValueError(f"Working database does not exist: {working_db_path}")
                
                # Copy working database to archive location
                shutil.copy2(working_db_path, archive_path)
                logger.info(f"Created new archive '{archive_name}' as copy of working database at {archive_path}")
                
                return sanitized_name
                
            except Exception as e:
                logger.error(f"Failed to create archive '{archive_name}': {e}", exc_info=True)
                # Clean up if copy failed
                if archive_path.exists():
                    archive_path.unlink()
                raise
    
    def create_empty_archive(self, archive_name: str) -> str:
        """Create a new empty archive database
        
        Args:
            archive_name: Name of the archive (will be sanitized for filename)
            
        Returns:
            Archive name (sanitized)
            
        Raises:
            ValueError: If archive name is invalid or already exists
        """
        with self._operation_lock:
            # Sanitize archive name for filename
            sanitized_name = self._sanitize_filename(archive_name)
            
            if not sanitized_name:
                raise ValueError("Archive name cannot be empty")
            
            archive_path = self._archives_dir / f"{sanitized_name}.db"
            
            # Check if archive already exists
            if archive_path.exists():
                raise ValueError(f"Archive '{archive_name}' already exists")
            
            try:
                # Create new empty database with initialized tables
                from app.storage.database import init_database_for_path
                init_database_for_path(archive_path)
                logger.info(f"Created new empty archive '{archive_name}' at {archive_path}")
                
                return sanitized_name
                
            except Exception as e:
                logger.error(f"Failed to create empty archive '{archive_name}': {e}", exc_info=True)
                # Clean up if initialization failed
                if archive_path.exists():
                    archive_path.unlink()
                raise
    
    def generate_default_archive_name(self) -> str:
        """Generate a default archive name with incremental number
        
        Returns:
            Archive name in format 'default_1', 'default_2', etc.
        """
        archives = self.list_archives()
        existing_names = {a["name"] for a in archives}
        
        counter = 1
        while True:
            candidate = f"default_{counter}"
            if candidate not in existing_names:
                return candidate
            counter += 1
    
    def overwrite_archive(self, archive_name: str) -> str:
        """Overwrite an archive with working database content
        
        This method copies the current working database to the target archive location.
        If the archive exists, it will be replaced. If it doesn't exist, it will be created.
        
        Args:
            archive_name: Name of the archive to overwrite/create
            
        Returns:
            Archive name (sanitized)
            
        Raises:
            ValueError: If archive name is invalid
        """
        with self._operation_lock:
            # Sanitize archive name for filename
            sanitized_name = self._sanitize_filename(archive_name)
            
            if not sanitized_name:
                raise ValueError("Archive name cannot be empty")
            
            archive_path = self._archives_dir / f"{sanitized_name}.db"
            
            # Get working database path
            working_db_path = self.get_current_db_path()
            
            # Check if working database exists
            if not working_db_path.exists():
                raise ValueError(f"Working database does not exist: {working_db_path}")
            
            try:
                # Delete existing archive if it exists
                if archive_path.exists():
                    archive_path.unlink()
                    logger.info(f"Deleted existing archive '{archive_name}' before overwrite")
                
                # Copy working database to archive location
                shutil.copy2(working_db_path, archive_path)
                logger.info(f"Overwritten archive '{archive_name}' with working database content at {archive_path}")
                
            except Exception as e:
                logger.error(f"Failed to overwrite archive '{archive_name}': {e}", exc_info=True)
                raise
            
            return sanitized_name
    
    def delete_archive(self, archive_name: str) -> bool:
        """Delete an archive
        
        Args:
            archive_name: Name of the archive to delete
            
        Returns:
            True if deleted successfully, False otherwise
            
        Raises:
            ValueError: If archive does not exist
        """
        with self._operation_lock:
            # Sanitize archive name
            sanitized_name = self._sanitize_filename(archive_name)
            
            archive_path = self._archives_dir / f"{sanitized_name}.db"
            
            if not archive_path.exists():
                raise ValueError(f"Archive '{archive_name}' does not exist")
            
            try:
                archive_path.unlink()
                logger.info(f"Deleted archive '{archive_name}' at {archive_path}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to delete archive '{archive_name}': {e}", exc_info=True)
                raise
    
    def load_archive(self, archive_name: str) -> bool:
        """Load an archive into working database
        
        This copies the specified archive to the working database, overwriting it.
        All subsequent operations will use the working database.
        
        Args:
            archive_name: Name of archive to load
            
        Returns:
            True if loaded successfully
            
        Raises:
            ValueError: If archive does not exist
        """
        with self._operation_lock:
            try:
                # Sanitize archive name
                sanitized_name = self._sanitize_filename(archive_name)
                archive_path = self._archives_dir / f"{sanitized_name}.db"
                
                if not archive_path.exists():
                    raise ValueError(f"Archive '{archive_name}' does not exist")
                
                # Copy archive to working database (overwrite)
                shutil.copy2(archive_path, self._working_db_path)
                logger.info(f"Loaded archive '{archive_name}' into working database at {self._working_db_path}")
                
                # Ensure database schema is up-to-date (handles old archives without character table)
                from app.storage.database import init_database_for_path
                init_database_for_path(self._working_db_path)
                logger.debug(f"Ensured database schema is initialized for {self._working_db_path}")
                
                # Refresh Meilisearch
                self._refresh_meilisearch()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to load archive '{archive_name}': {e}", exc_info=True)
                raise
    
    def list_archives(self) -> List[Dict[str, Any]]:
        """List all available archives
        
        Returns:
            List of archive information dictionaries (without is_active field, as frontend doesn't need to know)
        """
        archives = []
        
        for archive_file in self._archives_dir.glob("*.db"):
            archive_name = archive_file.stem
            stat = archive_file.stat()
            
            archives.append({
                "name": archive_name,
                "path": str(archive_file),
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })
        
        # Sort by creation time (newest first)
        archives.sort(key=lambda x: x["created_at"], reverse=True)
        
        return archives
    
    def get_current_archive_info(self) -> Optional[Dict[str, Any]]:
        """Get information about currently active archive
        
        Always returns None since frontend doesn't need to know about the working database.
        
        Returns:
            None (frontend doesn't need to know which archive is loaded)
        """
        return None
    
    def reset_working_database(self) -> bool:
        """Reset working database to empty state
        
        This deletes the working database and creates a new empty one.
        This is used when creating a new archive without saving the current state.
        
        Returns:
            True if reset successfully
            
        Raises:
            Exception: If reset fails
        """
        with self._operation_lock:
            try:
                # Delete existing working database if it exists
                if self._working_db_path.exists():
                    # Close any existing connections first
                    # Note: SQLite will handle file locks, but we should be careful
                    self._working_db_path.unlink()
                    logger.info(f"Deleted existing working database at {self._working_db_path}")
                
                # Create new empty database with initialized tables
                from app.storage.database import init_database_for_path
                init_database_for_path(self._working_db_path)
                logger.info(f"Reset working database to empty state at {self._working_db_path}")
                
                # Refresh Meilisearch
                self._refresh_meilisearch()
                
                return True
                
            except Exception as e:
                logger.error(f"Failed to reset working database: {e}", exc_info=True)
                raise
    
    def _refresh_meilisearch(self):
        """Refresh Meilisearch index from current database"""
        try:
            meilisearch = MeilisearchService()
            
            if not meilisearch.is_available:
                logger.warning("Meilisearch is not available, skipping refresh")
                return
            
            db_path = self.get_current_db_path()
            logger.info(f"Refreshing Meilisearch index from database: {db_path}")
            
            # Clear all documents from all indexes
            meilisearch.clear_all_documents()
            
            # Refresh from current database
            meilisearch.refresh_from_database(db_path)
            
            logger.info("Meilisearch index refreshed successfully")
            
        except Exception as e:
            logger.error(f"Failed to refresh Meilisearch: {e}", exc_info=True)
            # Don't raise - allow database switch to succeed even if Meilisearch fails
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename to remove invalid characters
        
        Args:
            name: Original name
            
        Returns:
            Sanitized name safe for use as filename
        """
        # Remove invalid characters for Windows/Linux filenames
        invalid_chars = '<>:"/\\|?*'
        sanitized = ''.join(c if c not in invalid_chars else '_' for c in name)
        
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip(' .')
        
        return sanitized

