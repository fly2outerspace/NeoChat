"""High-level store for kv records"""
from typing import Dict, List, Optional, Any

from app.logger import logger
from app.storage.kv_repository import KVRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.storage.meilisearch_service import MeilisearchService


class KVStore:
    """Singleton store managing kv records"""

    _instance: Optional["KVStore"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._repository = KVRepository()
            cls._instance._session_repository = SQLiteSessionRepository()
            cls._instance._meilisearch = MeilisearchService()
            cls._instance._current_session_id = "default"
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._ensure_session_exists()
        self._initialized = True

    @property
    def session_id(self) -> str:
        """Return current session id"""
        return self._current_session_id

    def set_session(self, session_id: str):
        """Switch context to another session"""
        self._current_session_id = session_id
        self._ensure_session_exists()
        logger.debug(f"KVStore switched to session: {session_id}")

    def get(self, key: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> Optional[str]:
        """Get metadata value by key"""
        target_session = session_id or self._current_session_id
        row = self._repository.get_by_key(target_session, key, character_id)
        if row:
            return row.get("metadata")
        return None

    def set(self, key: str, metadata: str, session_id: Optional[str] = None, key_type: str = "", character_id: Optional[str] = None) -> bool:
        """Set metadata value by key (create or update)"""
        target_session = session_id or self._current_session_id
        self._ensure_session_exists()
        
        # Auto-detect key_type from key prefix if not provided
        if not key_type and key.startswith("relation:"):
            key_type = "relation"
        
        # Check if key exists
        existing = self._repository.get_by_key(target_session, key, character_id)
        if existing:
            # Update existing
            success = self._repository.update_metadata(target_session, key, metadata, key_type if key_type else None, character_id)
            if success:
                # Sync to Meilisearch
                self._sync_kv_to_meilisearch(target_session, key, metadata, existing.get("id"), key_type or existing.get("key_type", ""), character_id)
        else:
            # Create new
            try:
                kv_id = self._repository.insert_kv(target_session, key, metadata, key_type, character_id)
                success = True
                # Sync to Meilisearch
                if success:
                    self._sync_kv_to_meilisearch(target_session, key, metadata, kv_id, key_type, character_id)
            except Exception as e:
                logger.error(f"Failed to insert kv: {e}")
                success = False
        
        if success:
            self._session_repository.update_session_timestamp(target_session)
        return success

    def delete(self, key: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> bool:
        """Delete a kv entry by key"""
        target_session = session_id or self._current_session_id
        try:
            # Get kv entry before deletion for Meilisearch cleanup
            row = self._repository.get_by_key(target_session, key, character_id)
            kv_id = row.get("id") if row else None
            
            success = self._repository.delete_by_key(target_session, key, character_id)
            if success:
                self._session_repository.update_session_timestamp(target_session)
                # Delete from Meilisearch
                if kv_id and self._meilisearch and self._meilisearch.is_available:
                    # Meilisearch document ID format: replace colons with double underscores
                    doc_id = f"{target_session}__{key}".replace(":", "_")
                    self._meilisearch.delete_document(
                        doc_id,
                        index_name=MeilisearchService.KV_INDEX
                    )
            return success
        except Exception as e:
            logger.error(f"Failed to delete kv: {e}")
            return False

    def list_keys(self, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[str]:
        """List all keys for a session"""
        target_session = session_id or self._current_session_id
        rows = self._repository.list_by_session(target_session, character_id=character_id)
        return [row["key"] for row in rows]

    def list_all(self, session_id: Optional[str] = None, key_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, str]]:
        """List all kv entries for a session, optionally filtered by key_type and character_id"""
        target_session = session_id or self._current_session_id
        rows = self._repository.list_by_session(target_session, key_type, character_id)
        return [{"key": row["key"], "metadata": row["metadata"], "key_type": row.get("key_type", "")} for row in rows]

    def search(self, keyword: str, session_id: Optional[str] = None, key_type: Optional[str] = None, character_id: Optional[str] = None) -> List[Dict[str, str]]:
        """Search kv entries by keyword, optionally filtered by key_type and character_id"""
        target_session = session_id or self._current_session_id
        rows = self._repository.search_by_keyword(target_session, keyword, key_type, character_id)
        return [{"key": row["key"], "metadata": row["metadata"], "key_type": row.get("key_type", "")} for row in rows]

    def _prepare_meilisearch_document(self, session_id: str, key: str, metadata: str, kv_id: int, key_type: str = "", character_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert kv entry to Meilisearch document"""
        row = self._repository.get_by_key(session_id, key, character_id)
        # Meilisearch document ID can only contain alphanumeric, hyphens, and underscores
        # Replace colons with double underscores to maintain uniqueness
        doc_id = f"{session_id}__{key}".replace(":", "_")
        return {
            "id": doc_id,
            "session_id": session_id,
            "key": key,
            "key_type": key_type or (row.get("key_type") if row else ""),
            "metadata": metadata,
            "character_id": character_id or (row.get("character_id") if row else None),
            "created_at": row.get("created_at") if row else "",
            "updated_at": row.get("updated_at") if row else "",
        }

    def _sync_kv_to_meilisearch(self, session_id: str, key: str, metadata: str, kv_id: int, key_type: str = "", character_id: Optional[str] = None):
        """Sync single kv entry to Meilisearch"""
        if not getattr(self, "_meilisearch", None):
            return
        if not self._meilisearch.is_available:
            return
        document = self._prepare_meilisearch_document(session_id, key, metadata, kv_id, key_type, character_id)
        ok = self._meilisearch.add_document(
            document,
            index_name=MeilisearchService.KV_INDEX,
        )
        if not ok:
            logger.warning(f"Failed to index kv to Meilisearch: {document}")
        else:
            logger.debug(f"Successfully indexed kv to Meilisearch: key={key}, key_type={key_type}, character_id={character_id}")

    def _ensure_session_exists(self):
        """Ensure session metadata exists"""
        try:
            self._session_repository.create_session(
                self._current_session_id,
                f"Session {self._current_session_id}",
            )
            self._session_repository.update_session_timestamp(self._current_session_id)
        except Exception as exc:
            logger.error(f"KVStore failed to ensure session: {exc}")

