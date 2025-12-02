"""High-level store for relation records"""
from typing import List, Optional

from app.logger import logger
from app.schema import Relation
from app.storage.relation_repository import RelationRepository
from app.storage.session_repository import SQLiteSessionRepository


class RelationStore:
    """Singleton store managing relation records"""

    _instance: Optional["RelationStore"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._repository = RelationRepository()
            cls._instance._session_repository = SQLiteSessionRepository()
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
        logger.debug(f"RelationStore switched to session: {session_id}")

    def add_relation(self, relation: Relation, character_id: Optional[str] = None) -> Relation:
        """Add a relation entry"""
        if not relation.session_id:
            relation.session_id = self._current_session_id
        
        try:
            success = self._repository.insert_relation(relation, character_id=character_id)
            if success:
                self._session_repository.update_session_timestamp(relation.session_id)
                return relation
            else:
                raise Exception("Failed to insert relation")
        except Exception as e:
            logger.error(f"Failed to add relation: {e}")
            raise

    def get_by_relation_id(self, relation_id: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> Optional[Relation]:
        """Get a relation by relation_id, optionally filtered by character_id"""
        target_session = session_id or self._current_session_id
        try:
            return self._repository.get_by_relation_id(relation_id, target_session, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get relation: {e}")
            return None

    def list_relations(self, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Relation]:
        """List all relations for a session, optionally filtered by character_id"""
        target_session = session_id or self._current_session_id
        try:
            return self._repository.list_by_session(target_session, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to list relations: {e}")
            return []

    def update_relation(
        self,
        relation_id: str,
        name: Optional[str] = None,
        knowledge: Optional[str] = None,
        progress: Optional[str] = None,
        session_id: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> Optional[Relation]:
        """Update relation fields, optionally filtered by character_id"""
        target_session = session_id or self._current_session_id
        try:
            updated = self._repository.update_relation(
                relation_id, target_session, name, knowledge, progress, character_id=character_id
            )
            if updated:
                self._session_repository.update_session_timestamp(target_session)
            return updated
        except Exception as e:
            logger.error(f"Failed to update relation: {e}")
            return None

    def delete_relation(self, relation_id: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> bool:
        """Delete a relation by relation_id, optionally filtered by character_id"""
        target_session = session_id or self._current_session_id
        try:
            success = self._repository.delete_by_relation_id(relation_id, target_session, character_id=character_id)
            if success:
                self._session_repository.update_session_timestamp(target_session)
            return success
        except Exception as e:
            logger.error(f"Failed to delete relation: {e}")
            return False

    def search_relations(self, keyword: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Relation]:
        """Search relations by keyword, optionally filtered by character_id"""
        target_session = session_id or self._current_session_id
        try:
            return self._repository.search_by_keyword(target_session, keyword, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to search relations: {e}")
            return []

    def _ensure_session_exists(self):
        """Ensure session metadata exists"""
        try:
            self._session_repository.create_session(
                self._current_session_id,
                f"Session {self._current_session_id}",
            )
            self._session_repository.update_session_timestamp(self._current_session_id)
        except Exception as exc:
            logger.error(f"RelationStore failed to ensure session: {exc}")

