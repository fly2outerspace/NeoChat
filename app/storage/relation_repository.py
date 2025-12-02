"""Repository for relation records using kv store"""
import json
from typing import List, Optional

from app.logger import logger
from app.schema import Relation
from app.storage.kv_store import KVStore


class RelationRepository:
    """Data access layer for relation records using kv store"""

    def __init__(self):
        self._kv_store = KVStore()
        self._key_prefix = "relation:"

    def _make_key(self, relation_id: str) -> str:
        """Create kv key from relation_id"""
        return f"{self._key_prefix}{relation_id}"

    def _serialize_relation(self, relation: Relation) -> str:
        """Serialize relation to JSON string"""
        data = {
            "relation_id": relation.relation_id,
            "session_id": relation.session_id,
            "name": relation.name,
            "knowledge": relation.knowledge,
            "progress": relation.progress,
            "created_at": relation.created_at,
        }
        return json.dumps(data, ensure_ascii=False)

    def _deserialize_relation(self, key: str, metadata: str, session_id: str) -> Optional[Relation]:
        """Deserialize JSON string to Relation object"""
        try:
            data = json.loads(metadata)
            # Extract relation_id from key (remove prefix)
            relation_id = key.replace(self._key_prefix, "")
            return Relation(
                relation_id=relation_id,
                session_id=data.get("session_id", session_id),
                name=data.get("name", ""),
                knowledge=data.get("knowledge", ""),
                progress=data.get("progress", ""),
                created_at=data.get("created_at"),
            )
        except (json.JSONDecodeError, KeyError) as e:
            logger.error(f"Failed to deserialize relation: {e}")
            return None

    def insert_relation(self, relation: Relation, character_id: Optional[str] = None) -> bool:
        """Insert a relation entry"""
        try:
            self._kv_store.set_session(relation.session_id)
            key = self._make_key(relation.relation_id)
            metadata = self._serialize_relation(relation)
            return self._kv_store.set(key, metadata, relation.session_id, key_type="relation", character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to insert relation: {e}")
            return False

    def get_by_relation_id(self, relation_id: str, session_id: str, character_id: Optional[str] = None) -> Optional[Relation]:
        """Get a relation by relation_id, optionally filtered by character_id"""
        try:
            self._kv_store.set_session(session_id)
            key = self._make_key(relation_id)
            metadata = self._kv_store.get(key, session_id, character_id=character_id)
            if metadata:
                return self._deserialize_relation(key, metadata, session_id)
            return None
        except Exception as e:
            logger.error(f"Failed to get relation: {e}")
            return None

    def list_by_session(self, session_id: str, character_id: Optional[str] = None) -> List[Relation]:
        """List all relations under a session, optionally filtered by character_id"""
        try:
            self._kv_store.set_session(session_id)
            # Use key_type filter for better performance
            all_entries = self._kv_store.list_all(session_id, key_type="relation", character_id=character_id)
            relations = []
            for entry in all_entries:
                if entry["key"].startswith(self._key_prefix):
                    relation = self._deserialize_relation(entry["key"], entry["metadata"], session_id)
                    if relation:
                        relations.append(relation)
            return relations
        except Exception as e:
            logger.error(f"Failed to list relations: {e}")
            return []

    def update_relation(
        self,
        relation_id: str,
        session_id: str,
        name: Optional[str] = None,
        knowledge: Optional[str] = None,
        progress: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> Optional[Relation]:
        """Update relation fields, optionally filtered by character_id"""
        try:
            # Get existing relation (with character_id filter to ensure we're updating the right one)
            existing = self.get_by_relation_id(relation_id, session_id, character_id=character_id)
            if not existing:
                return None

            # Update fields
            if name is not None:
                existing.name = name
            if knowledge is not None:
                existing.knowledge = knowledge
            if progress is not None:
                existing.progress = progress

            # Save updated relation (preserve the original character_id)
            if self.insert_relation(existing, character_id=character_id):
                return existing
            return None
        except Exception as e:
            logger.error(f"Failed to update relation: {e}")
            return None

    def delete_by_relation_id(self, relation_id: str, session_id: str, character_id: Optional[str] = None) -> bool:
        """Delete a relation by relation_id, optionally filtered by character_id"""
        try:
            self._kv_store.set_session(session_id)
            key = self._make_key(relation_id)
            return self._kv_store.delete(key, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to delete relation: {e}")
            return False

    def search_by_keyword(self, session_id: str, keyword: str, character_id: Optional[str] = None) -> List[Relation]:
        """Search relations by keyword in name, knowledge, or progress using Meilisearch"""
        try:
            from app.storage.meilisearch_service import MeilisearchService
            
            self._kv_store.set_session(session_id)
            meilisearch = MeilisearchService()
            
            if not meilisearch.is_available:
                # Fallback to SQLite search if Meilisearch is not available
                logger.warning("Meilisearch not available, falling back to SQLite search")
                results = self._kv_store.search(keyword, session_id, key_type="relation", character_id=character_id)
                relations = []
                for entry in results:
                    if entry["key"].startswith(self._key_prefix):
                        relation = self._deserialize_relation(entry["key"], entry["metadata"], session_id)
                        if relation:
                            relations.append(relation)
                return relations
            
            # Build filters
            filters = ['key_type = "relation"']
            if character_id is not None:
                filters.append(f'character_id = "{character_id}"')
            else:
                filters.append('character_id = null')
            
            # Use Meilisearch to search in metadata
            search_results = meilisearch.search(
                query=keyword,
                session_id=session_id,
                limit=100,
                offset=0,
                index_name=MeilisearchService.KV_INDEX,
                filters=filters,
            )
            
            logger.debug(f"Meilisearch search for '{keyword}' returned {search_results.get('estimatedTotalHits', 0)} hits")
            
            relations = []
            for hit in search_results.get("hits", []):
                key = hit.get("key", "")
                metadata = hit.get("metadata", "")
                if key.startswith(self._key_prefix):
                    relation = self._deserialize_relation(key, metadata, session_id)
                    if relation:
                        relations.append(relation)
            
            logger.debug(f"Found {len(relations)} relations matching keyword '{keyword}'")
            return relations
        except Exception as e:
            logger.error(f"Failed to search relations: {e}")
            return []

