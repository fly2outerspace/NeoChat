"""Message storage service using Repository pattern"""
import json
from typing import Any, Dict, List, Optional

from app.schema import Message, ToolCall, Function, QueryMetadata
from app.storage.message_repository import MessageRepository
from app.storage.sqlite_repository import SQLiteMessageRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.storage.meilisearch_service import MeilisearchService
from app.logger import logger


class MessageStore:
    """Message storage service using Repository pattern (Singleton)"""
    
    _instance: Optional["MessageStore"] = None
    _current_session_id: str = "default"
    _repository: MessageRepository = None
    _session_repository: SQLiteSessionRepository = None
    
    def __new__(cls):
        """Singleton pattern - only one instance exists"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Use SQLite repository by default
            cls._instance._repository = SQLiteMessageRepository()
            cls._instance._session_repository = SQLiteSessionRepository()
            cls._instance._current_session_id = "default"
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        """Initialize message store (only called once due to singleton)"""
        if self._initialized:
            return
        
        self._meilisearch = MeilisearchService()  # Get singleton instance
        self._ensure_session_exists()
        self._initialized = True
    
    @property
    def session_id(self) -> str:
        """Get current session ID"""
        return self._current_session_id
    
    def set_session(self, session_id: str):
        """Switch to a different session
        
        Args:
            session_id: Unique session identifier
        """
        self._current_session_id = session_id
        self._ensure_session_exists()
        logger.debug(f"Switched to session: {session_id}")
    
    def _ensure_session_exists(self):
        """Create session if it doesn't exist"""
        try:
            self._session_repository.create_session(
                self._current_session_id,
                f"Session {self._current_session_id}"
            )
            self._session_repository.update_session_timestamp(self._current_session_id)
        except Exception as e:
            logger.error(f"Failed to ensure session exists: {e}")
    
    def save_message(self, message: Message):
        """Save a single message to database and sync to Meilisearch"""
        try:
            tool_calls_json = self._serialize_tool_calls(message.tool_calls)
            
            # created_at should be set by Message constructor, but fallback to current time if not set
            message_id = self._repository.insert_message(
                session_id=self._current_session_id,
                role=message.role,
                content=message.content,
                tool_calls=tool_calls_json,
                tool_name=message.tool_name,
                speaker=message.speaker,
                tool_call_id=message.tool_call_id,
                created_at=message.created_at,  # Should be set by Message constructor
                category=message.category,  # Include category
                character_id_list=message.visible_for_characters,  # Include character associations
            )
            
            self._session_repository.update_session_timestamp(self._current_session_id)
            
            # Sync to Meilisearch
            self._sync_message_to_meilisearch(message_id, message)
        except Exception as e:
            logger.error(f"Failed to save message: {e}")
            raise
    
    def save_messages(self, messages: List[Message]):
        """Save multiple messages to database (overwrite mode)
        
        This method will replace all existing messages for the current session
        with the provided messages. It first deletes all existing messages,
        then inserts the new ones. Original timestamps are preserved if available.
        """
        try:
            # First, delete all existing messages for this session (overwrite mode)
            self._repository.delete_messages_by_session(self._current_session_id)
            
            # Also delete from Meilisearch
            if self._meilisearch.is_available:
                self._meilisearch.delete_by_session(self._current_session_id)
            
            # Then insert all new messages, preserving original timestamps
            meilisearch_docs = []
            for message in messages:
                tool_calls_json = self._serialize_tool_calls(message.tool_calls)
                message_id = self._repository.insert_message(
                    session_id=self._current_session_id,
                    role=message.role,
                    content=message.content,
                    tool_calls=tool_calls_json,
                    tool_name=message.tool_name,
                    speaker=message.speaker,
                    tool_call_id=message.tool_call_id,
                    created_at=message.created_at,  # Should be set by Message constructor
                    category=message.category,  # Include category
                    character_id_list=message.visible_for_characters,  # Include character associations
                )
                
                # Prepare Meilisearch document
                if self._meilisearch.is_available:
                    doc = self._prepare_meilisearch_document(message_id, message)
                    meilisearch_docs.append(doc)
            
            # Batch sync to Meilisearch
            if meilisearch_docs and self._meilisearch.is_available:
                self._meilisearch.add_documents(meilisearch_docs)
            
            self._session_repository.update_session_timestamp(self._current_session_id)
        except Exception as e:
            logger.error(f"Failed to save messages: {e}")
            raise
    
    def load_messages(self) -> List[Message]:
        """Load all messages for this session"""
        try:
            rows = self._repository.get_messages_by_session(self._current_session_id)
            messages = []
            
            for row in rows:
                tool_calls = self._deserialize_tool_calls(row.get("tool_calls"))
                msg = Message(
                    role=row["role"],
                    content=row["content"],
                    tool_calls=tool_calls,
                    tool_name=row.get("tool_name"),
                    speaker=row.get("speaker"),
                    tool_call_id=row.get("tool_call_id"),
                    created_at=row.get("created_at"),  # Preserve timestamp from database
                    category=row.get("category", 0),  # Load category, default to 0 if missing
                    visible_for_characters=row.get("character_ids"),  # Load character associations
                )
                messages.append(msg)
            
            return messages
        except Exception as e:
            logger.error(f"Failed to load messages: {e}")
            return []
    
    def clear_messages(self, session_id: Optional[str] = None):
        """Delete all messages for a session
        
        Args:
            session_id: Session ID to clear. If None, clears current session.
        """
        target_session = session_id or self._current_session_id
        try:
            self._repository.delete_messages_by_session(target_session)
            
            # Also delete from Meilisearch
            if self._meilisearch.is_available:
                self._meilisearch.delete_by_session(target_session)
            
            logger.info(f"Cleared messages for session {target_session}")
        except Exception as e:
            logger.error(f"Failed to clear messages: {e}")
            raise
    
    @staticmethod
    def list_sessions() -> List[dict]:
        """List all sessions"""
        from app.storage.session_repository import SQLiteSessionRepository
        repository = SQLiteSessionRepository()
        return repository.list_sessions()
    
    @staticmethod
    def _serialize_tool_calls(tool_calls: Optional[List]) -> Optional[str]:
        """Convert tool_calls to JSON string
        
        Supports both ToolCall objects and dict format (from Message.from_tool_calls)
        """
        if not tool_calls:
            return None
        
        tool_calls_data = []
        for tc in tool_calls:
            # Handle dict format (from Message.from_tool_calls)
            if isinstance(tc, dict):
                tool_calls_data.append(tc)
            # Handle ToolCall objects (Pydantic models)
            elif hasattr(tc, 'model_dump'):
                tool_calls_data.append(tc.model_dump())
            elif hasattr(tc, 'dict'):
                tool_calls_data.append(tc.dict())
            else:
                # Fallback: try to convert to dict
                logger.warning(f"Unexpected tool_call type: {type(tc)}, value: {tc}")
                tool_calls_data.append(tc if isinstance(tc, dict) else str(tc))
        
        return json.dumps(tool_calls_data)
    
    @staticmethod
    def _deserialize_tool_calls(tool_calls_json: Optional[str]) -> Optional[List[ToolCall]]:
        """Convert JSON string back to ToolCall objects"""
        if not tool_calls_json:
            return None
        
        try:
            tool_calls_data = json.loads(tool_calls_json)
            return [
                ToolCall(
                    id=tc["id"],
                    type=tc.get("type", "function"),
                    function=Function(**tc["function"])
                )
                for tc in tool_calls_data
            ]
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to parse tool_calls: {e}")
            return None
    
    def _rows_to_messages(self, rows: List[Dict[str, Any]]) -> List[Message]:
        """Convert database rows to Message objects"""
        messages = []
        for row in rows:
            tool_calls = self._deserialize_tool_calls(row.get("tool_calls"))
            msg = Message(
                role=row["role"],
                content=row["content"],
                tool_calls=tool_calls,
                tool_name=row.get("tool_name"),
                speaker=row.get("speaker"),
                tool_call_id=row.get("tool_call_id"),
                created_at=row.get("created_at"),
                category=row.get("category", 0),  # Load category, default to 0 if missing
                visible_for_characters=row.get("character_ids"),  # Load character associations
            )
            messages.append(msg)
        return messages
    
    def get_messages_around_time(
        self,
        time_point: str,
        hours: float = 1.0,
        max_messages: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get messages around a specific time point
        
        Algorithm: Scan forward and backward from time_point within the time range,
        then merge and sort by time distance, return the closest messages.
        
        Args:
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            hours: Time range in hours before and after time_point (default: 1.0)
            max_messages_per_direction: Max messages to scan in each direction (default: 100)
            category: Optional category filter. If None, returns all categories.
            
        Returns:
            Tuple of (List of messages sorted by created_at, QueryMetadata)
        """
        try:
            rows = self._repository.get_messages_around_time(
                self._current_session_id,
                time_point,
                hours,
                max_messages,
                categories,
                character_id
            )
            
            # Extract metadata if present
            metadata_dict = {}
            if rows and '_metadata' in rows[0]:
                metadata_dict = rows[0].pop('_metadata')
            
            metadata = QueryMetadata(**metadata_dict) if metadata_dict else QueryMetadata()
            messages = self._rows_to_messages(rows)
            return messages, metadata
        except Exception as e:
            logger.error(f"Failed to get messages around time: {e}")
            return [], QueryMetadata()
    
    def get_messages_in_range(
        self,
        start_time: str,
        end_time: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get messages within a specific time range
        
        Args:
            start_time: Start time string in format 'YYYY-MM-DD HH:MM:SS'
            end_time: End time string in format 'YYYY-MM-DD HH:MM:SS'
            max_results: Maximum number of messages to return (default: 100)
            category: Optional category filter. If None, returns all categories.
            character_id: Optional character ID for filtering. If None, returns messages visible to all characters.
            
        Returns:
            Tuple of (List of messages within the time range, QueryMetadata)
        """
        try:
            rows = self._repository.get_messages_in_range(
                self._current_session_id,
                start_time,
                end_time,
                max_results,
                categories,
                character_id
            )
            
            # Extract metadata if present
            metadata_dict = {}
            if rows and '_metadata' in rows[0]:
                metadata_dict = rows[0].pop('_metadata')
            
            metadata = QueryMetadata(**metadata_dict) if metadata_dict else QueryMetadata()
            messages = self._rows_to_messages(rows)
            return messages, metadata
        except Exception as e:
            logger.error(f"Failed to get messages in range: {e}")
            return [], QueryMetadata()
    
    def get_messages_by_date(
        self, 
        date: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get all messages on a specific date
        
        Args:
            date: Date string in format 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
                  If time is included, only date part is used
            max_results: Maximum number of messages to return (default: 100)
            category: Optional category filter. If None, returns all categories.
            character_id: Optional character ID for filtering. If None, returns messages visible to all characters.
            
        Returns:
            Tuple of (List of messages on the specified date, QueryMetadata)
        """
        try:
            # Extract date part if full timestamp is provided
            date_only = date[:10] if len(date) > 10 else date
            rows = self._repository.get_messages_by_date(
                self._current_session_id,
                date_only,
                max_results,
                categories,
                character_id
            )
            
            # Extract metadata if present
            metadata_dict = {}
            if rows and '_metadata' in rows[0]:
                metadata_dict = rows[0].pop('_metadata')
            
            metadata = QueryMetadata(**metadata_dict) if metadata_dict else QueryMetadata()
            messages = self._rows_to_messages(rows)
            return messages, metadata
        except Exception as e:
            logger.error(f"Failed to get messages by date: {e}")
            return [], QueryMetadata()
    
    def _prepare_meilisearch_document(self, message_id: int, message: Message) -> Dict[str, Any]:
        """Prepare a message document for Meilisearch indexing"""
        return {
            "id": message_id,
            "session_id": self._current_session_id,
            "role": message.role,
            "content": message.content or "",
            "tool_name": message.tool_name or "",
            "speaker": message.speaker or "",
            "tool_call_id": message.tool_call_id or "",
            "created_at": message.created_at or "",
            "category": message.category,
            "character_ids": message.visible_for_characters or []  # Include character associations
        }
    
    def _sync_message_to_meilisearch(self, message_id: int, message: Message):
        """Sync a single message to Meilisearch"""
        if not self._meilisearch.is_available:
            return
        
        try:
            doc = self._prepare_meilisearch_document(message_id, message)
            self._meilisearch.add_document(doc)
        except Exception as e:
            logger.warning(f"Failed to sync message to Meilisearch: {e}")

