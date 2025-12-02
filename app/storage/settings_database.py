"""Settings database initialization and connection management"""
import sqlite3
from pathlib import Path
from app.logger import logger


# Settings database file path (in project root)
SETTINGS_DB_PATH = Path(__file__).parent.parent.parent / "data" / "settings.db"


def get_settings_connection(timeout: float = 5.0):
    """Get a connection to the settings database
    
    Args:
        timeout: Timeout in seconds for database operations (default: 5.0)
                 SQLite will wait up to this time for locks to be released
    """
    # Create data directory if it doesn't exist
    SETTINGS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(SETTINGS_DB_PATH), check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row  # Return rows as dict-like objects
    return conn


def init_settings_database():
    """Initialize settings database tables (character and model)"""
    conn = get_settings_connection()
    cursor = conn.cursor()
    
    try:
        # Create character table
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

        # Create model table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS model (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                model_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                base_url TEXT NOT NULL,
                api_key TEXT,
                max_tokens INTEGER DEFAULT 4096,
                temperature REAL DEFAULT 1.0,
                api_type TEXT DEFAULT 'openai',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                real_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Create index for model table
        cursor.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_model_model_id
            ON model(model_id)
        """)
        
        conn.commit()
        logger.info(f"Settings database initialized at {SETTINGS_DB_PATH}")
    except Exception as e:
        logger.error(f"Failed to initialize settings database: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

