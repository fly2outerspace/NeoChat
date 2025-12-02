"""Database initialization and connection management"""
import sqlite3
import os
from pathlib import Path
from app.logger import logger


# Database file path (in project root) - kept for backward compatibility
DB_PATH = Path(__file__).parent.parent.parent / "data" / "chat.db"


def get_connection(timeout: float = 5.0):
    """Get a database connection with timeout
    
    Gets connection from DatabaseManager singleton, which manages
    current database file (active database or archive).
    
    Args:
        timeout: Timeout in seconds for database operations (default: 5.0)
                 SQLite will wait up to this time for locks to be released
    """
    from app.storage.database_manager import DatabaseManager
    
    # Get connection from DatabaseManager singleton
    manager = DatabaseManager()
    return manager.get_connection(timeout=timeout)


def init_database():
    """Initialize database tables"""
    conn = get_connection()
    try:
        init_database_for_connection(conn)
    finally:
        conn.close()


def init_database_for_path(db_path: Path):
    """Initialize database tables for a specific database file path
    
    Args:
        db_path: Path to the database file
    """
    # Create parent directory if it doesn't exist
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        init_database_for_connection(conn)
    finally:
        conn.close()
    logger.info(f"Database initialized at {db_path}")


def init_database_for_connection(conn: sqlite3.Connection):
    """Initialize database tables for an existing connection
    
    Args:
        conn: SQLite connection object
    """
    cursor = conn.cursor()
    
    try:
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT,
                tool_calls TEXT,
                tool_name TEXT,
                speaker TEXT,
                tool_call_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                category INTEGER DEFAULT 0,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Add category column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE messages ADD COLUMN category INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            # Column already exists, ignore
            pass
        
        # Create index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session_id 
            ON messages(session_id, created_at)
        """)

        # Create period table (merged scenario and schedule)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS period (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                period_id TEXT NOT NULL,
                period_type TEXT NOT NULL,
                start_at TIMESTAMP NOT NULL,
                end_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                content TEXT DEFAULT '',
                title TEXT DEFAULT '',
                character_id TEXT,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                UNIQUE(period_id)
            )
        """)
        
        # Add title column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE period ADD COLUMN title TEXT DEFAULT ''")
        except Exception:
            # Column already exists, ignore
            pass

        # Create indexes for period queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_period_session_time
            ON period(session_id, start_at, end_at)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_period_period_id
            ON period(period_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_period_type
            ON period(period_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_period_session_type
            ON period(session_id, period_type)
        """)

        # Create character table (reserved for future use, not currently accessed)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS character (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                character_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                roleplay_prompt TEXT,
                avatar TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for character table
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_character_character_id
            ON character(character_id)
        """)

        # Note: model table has been moved to settings.db
        # It is no longer created in archive databases
        
        # Create session_clock table for virtual time management
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_clock (
                session_id TEXT PRIMARY KEY,
                mode TEXT NOT NULL DEFAULT 'real',
                offset_seconds REAL DEFAULT 0.0,
                fixed_time TEXT,
                speed REAL DEFAULT 1.0,
                virtual_base TEXT,
                real_base TEXT,
                actions TEXT DEFAULT '[]',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
        """)
        
        # Create kv table for key-value storage
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS kv (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                key TEXT NOT NULL,
                key_type TEXT DEFAULT '',
                metadata TEXT NOT NULL,
                character_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                UNIQUE(session_id, key)
            )
        """)
        
        # Add key_type column if it doesn't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE kv ADD COLUMN key_type TEXT DEFAULT ''")
        except sqlite3.OperationalError:
            # Column already exists, ignore
            pass
        
        # Update existing relation keys to have key_type = 'relation'
        cursor.execute("""
            UPDATE kv
            SET key_type = 'relation'
            WHERE key LIKE 'relation:%' AND (key_type IS NULL OR key_type = '')
        """)
        
        # Create index for kv table
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_kv_session_key
            ON kv(session_id, key)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_session_id
            ON kv(session_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_key_type
            ON kv(key_type)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_kv_session_key_type
            ON kv(session_id, key_type)
        """)
        
        # Create message_characters association table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS message_characters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id INTEGER NOT NULL,
                character_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (message_id) REFERENCES messages(id) ON DELETE CASCADE,
                FOREIGN KEY (character_id) REFERENCES character(character_id) ON DELETE CASCADE,
                UNIQUE(message_id, character_id)
            )
        """)
        
        # Create indexes for message_characters table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_characters_message_id
            ON message_characters(message_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_message_characters_character_id
            ON message_characters(character_id)
        """)
        
        # Create frontend_messages table for frontend display messages
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS frontend_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                client_message_id TEXT NOT NULL,
                role TEXT NOT NULL,
                message_kind TEXT NOT NULL DEFAULT 'text',
                content TEXT NOT NULL DEFAULT '',
                tool_name TEXT,
                tool_call_id TEXT,
                input_mode TEXT,
                character_id TEXT,
                display_order INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE,
                UNIQUE(session_id, client_message_id)
            )
        """)
        
        # Create indexes for frontend_messages table
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_frontend_messages_session_id
            ON frontend_messages(session_id, display_order, created_at)
        """)
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_frontend_messages_client_id
            ON frontend_messages(session_id, client_message_id)
        """)
        
        conn.commit()
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        conn.rollback()
        raise

