"""High-level store for event records"""
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.logger import logger
from app.schema import Event
from app.storage.period_repository import PeriodRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.storage.meilisearch_service import MeilisearchService


class EventStore:
    """Singleton store managing event records"""

    _instance: Optional["EventStore"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._repository = PeriodRepository()
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
        logger.debug(f"EventStore switched to session: {session_id}")

    def add_event(self, event: Event, character_id: Optional[str] = None) -> Event:
        """Add an event entry using schema"""
        scene = event.scene or ""
        title = event.title or ""
        event_identifier = event.event_id or f"event-{uuid4().hex[:8]}"
        event_db_id = self._repository.insert_period(
            self._current_session_id,
            event_identifier,
            PeriodRepository.PERIOD_TYPE_EVENT,
            event.start_at,
            event.end_at,
            scene,  # scene maps to content in period table
            title,
            character_id,
            event.created_at,
        )
        self._session_repository.update_session_timestamp(self._current_session_id)
        stored = Event(
            session_id=self._current_session_id,
            event_id=event_identifier,
            start_at=event.start_at,
            end_at=event.end_at,
            scene=scene,
            title=title,
            created_at=event.created_at,
        )
        self._sync_event_to_meilisearch(stored, character_id)
        return stored

    def list_events(self, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Event]:
        """List all events for a session"""
        target_session = session_id or self._current_session_id
        rows = self._repository.list_by_session(target_session, PeriodRepository.PERIOD_TYPE_EVENT, character_id)
        return self._rows_to_events(rows)

    def find_events_at(self, time_point: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Event]:
        """Find events covering a specific time point"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_time(target_session, time_point, PeriodRepository.PERIOD_TYPE_EVENT, character_id)
        return self._rows_to_events(rows)

    def find_events_in_range(self, start_at: str, end_at: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Event]:
        """Find events that overlap with the given time range"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_time_range(target_session, start_at, end_at, PeriodRepository.PERIOD_TYPE_EVENT, character_id)
        return self._rows_to_events(rows)

    @staticmethod
    def _rows_to_events(rows: List[dict]) -> List[Event]:
        """Convert database rows to Event objects"""
        events: List[Event] = []
        for row in rows:
            events.append(
                Event(
                    session_id=row["session_id"],
                    event_id=row.get("period_id"),  # period_id maps to event_id
                    start_at=row["start_at"],
                    end_at=row["end_at"],
                    scene=row.get("content") or "",  # content maps to scene
                    title=row.get("title") or "",
                    created_at=row.get("created_at"),
                )
            )
        return events

    def _prepare_meilisearch_document(self, event: Event, character_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert event to Meilisearch document"""
        return {
            "id": event.event_id or "",
            "period_id": event.event_id or "",
            "period_type": PeriodRepository.PERIOD_TYPE_EVENT,
            "session_id": event.session_id,
            "content": event.scene or "",  # scene maps to content
            "title": event.title or "",
            "start_at": event.start_at,
            "end_at": event.end_at,
            "character_id": character_id,
            "created_at": event.created_at or "",
        }

    def _sync_event_to_meilisearch(self, event: Event, character_id: Optional[str] = None):
        """Sync single event to Meilisearch"""
        if not getattr(self, "_meilisearch", None):
            return
        if not self._meilisearch.is_available:
            return
        document = self._prepare_meilisearch_document(event, character_id)
        ok = self._meilisearch.add_document(
            document,
            index_name=MeilisearchService.PERIOD_INDEX,
        )
        if not ok:
            logger.warning(f"Failed to index event to Meilisearch: {document}")

    def update_event_by_event_id(
        self,
        event_id: str,
        scene: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[Event]:
        """Update event fields by business event_id"""
        try:
            # Map scene to content for update
            content = scene
            success = self._repository.update_by_period_id(
                event_id, content, start_at, end_at, title
            )
            if not success:
                return None
            
            # Get updated event
            row = self._repository.get_by_period_id(event_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_EVENT:
                return None
            
            updated_event = self._rows_to_events([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_event.session_id)
            self._sync_event_to_meilisearch(updated_event, character_id)
            return updated_event
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return None

    def delete_event_by_event_id(self, event_id: str) -> bool:
        """Delete an event by business event_id"""
        try:
            # Get event before deletion for Meilisearch cleanup
            row = self._repository.get_by_period_id(event_id)
            if row and row.get("period_type") == PeriodRepository.PERIOD_TYPE_EVENT:
                event = self._rows_to_events([row])[0]
                session_id = event.session_id
            else:
                session_id = None
            
            success = self._repository.delete_by_period_id(event_id)
            if success and session_id:
                self._session_repository.update_session_timestamp(session_id)
                # Delete from Meilisearch
                if self._meilisearch and self._meilisearch.is_available:
                    self._meilisearch.delete_document(
                        event_id,
                        index_name=MeilisearchService.PERIOD_INDEX
                    )
            return success
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    def _ensure_session_exists(self):
        """Ensure session metadata exists"""
        try:
            self._session_repository.create_session(
                self._current_session_id,
                f"Session {self._current_session_id}",
            )
            self._session_repository.update_session_timestamp(self._current_session_id)
        except Exception as exc:
            logger.error(f"EventStore failed to ensure session: {exc}")

