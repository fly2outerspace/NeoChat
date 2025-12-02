"""High-level store for schedule records"""
from typing import List, Optional, Dict, Any

from app.logger import logger
from app.schema import ScheduleEntry
from app.storage.period_repository import PeriodRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.storage.meilisearch_service import MeilisearchService


class ScheduleStore:
    """Singleton store managing schedule records"""

    _instance: Optional["ScheduleStore"] = None

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
        logger.debug(f"ScheduleStore switched to session: {session_id}")

    def add_schedule_entry(self, entry: ScheduleEntry, character_id: Optional[str] = None) -> ScheduleEntry:
        """Add a schedule entry using schema"""
        if not entry.entry_id:
            raise ValueError("schedule entry requires non-empty entry_id")
        content = entry.content or ""
        # Schedule entries don't use title, pass empty string
        schedule_id = self._repository.insert_period(
            self._current_session_id,
            entry.entry_id,
            PeriodRepository.PERIOD_TYPE_SCHEDULE,
            entry.start_at,
            entry.end_at,
            content,
            "",  # title is empty for schedule
            character_id,
            entry.created_at,
        )
        self._session_repository.update_session_timestamp(self._current_session_id)
        stored_entry = ScheduleEntry(
            entry_id=entry.entry_id,
            session_id=self._current_session_id,
            start_at=entry.start_at,
            end_at=entry.end_at,
            content=content,
            created_at=entry.created_at,
        )
        self._sync_entry_to_meilisearch(stored_entry, character_id)
        return stored_entry

    def list_entries(self, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """List all schedules for a session"""
        target_session = session_id or self._current_session_id
        rows = self._repository.list_by_session(target_session, PeriodRepository.PERIOD_TYPE_SCHEDULE, character_id)
        return self._rows_to_schedule_entries(rows)

    def find_entries_at(self, time_point: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """Find schedules covering a specific time point"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_time(target_session, time_point, PeriodRepository.PERIOD_TYPE_SCHEDULE, character_id)
        return self._rows_to_schedule_entries(rows)

    def find_entries_by_date(self, date: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """Find schedules where start_at or end_at matches the date"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_date(target_session, date, PeriodRepository.PERIOD_TYPE_SCHEDULE, character_id)
        return self._rows_to_schedule_entries(rows)

    @staticmethod
    def _rows_to_schedule_entries(rows: List[dict]) -> List[ScheduleEntry]:
        """Convert database rows to ScheduleEntry objects"""
        items: List[ScheduleEntry] = []
        for row in rows:
            items.append(
                ScheduleEntry(
                    entry_id=row.get("period_id"),  # period_id maps to entry_id
                    session_id=row["session_id"],
                    start_at=row["start_at"],
                    end_at=row["end_at"],
                    content=row.get("content") or "",
                    created_at=row.get("created_at"),
                )
            )
        return items

    def _prepare_meilisearch_document(self, entry: ScheduleEntry, character_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert entry to Meilisearch document"""
        return {
            "id": entry.entry_id,
            "period_id": entry.entry_id,
            "period_type": PeriodRepository.PERIOD_TYPE_SCHEDULE,
            "session_id": entry.session_id,
            "content": entry.content or "",
            "title": "",  # Schedule entries don't use title
            "start_at": entry.start_at,
            "end_at": entry.end_at,
            "character_id": character_id,
            "created_at": entry.created_at or "",
        }

    def _sync_entry_to_meilisearch(self, entry: ScheduleEntry, character_id: Optional[str] = None):
        """Sync single schedule entry to Meilisearch"""
        if not getattr(self, "_meilisearch", None):
            return
        if not self._meilisearch.is_available:
            return
        document = self._prepare_meilisearch_document(entry, character_id)
        ok = self._meilisearch.add_document(
            document,
            index_name=MeilisearchService.PERIOD_INDEX,
        )
        if not ok:
            logger.warning(f"Failed to index schedule entry to Meilisearch: {document}")
        else:
            logger.debug(f"Successfully indexed schedule entry to Meilisearch: entry_id={entry.entry_id}, character_id={character_id}")

    def update_entry_content(self, entry_id: int, content: str) -> Optional[ScheduleEntry]:
        """Update content of a schedule entry by database id"""
        try:
            success = self._repository.update_content_by_id(entry_id, content)
            if not success:
                return None
            
            # Get updated entry
            row = self._repository.get_by_id(entry_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCHEDULE:
                return None
            
            updated_entry = self._rows_to_schedule_entries([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_entry.session_id)
            self._sync_entry_to_meilisearch(updated_entry, character_id)
            return updated_entry
        except Exception as e:
            logger.error(f"Failed to update schedule entry content: {e}")
            return None

    def update_entry_content_by_entry_id(self, entry_id: str, content: str) -> Optional[ScheduleEntry]:
        """Update content of a schedule entry by business entry_id"""
        try:
            success = self._repository.update_content_by_period_id(entry_id, content)
            if not success:
                return None
            
            # Get updated entry
            row = self._repository.get_by_period_id(entry_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCHEDULE:
                return None
            
            updated_entry = self._rows_to_schedule_entries([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_entry.session_id)
            self._sync_entry_to_meilisearch(updated_entry, character_id)
            return updated_entry
        except Exception as e:
            logger.error(f"Failed to update schedule entry content: {e}")
            return None

    def update_entry_by_entry_id(
        self,
        entry_id: str,
        content: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
    ) -> Optional[ScheduleEntry]:
        """Update schedule entry fields by business entry_id"""
        try:
            success = self._repository.update_by_period_id(
                entry_id, content, start_at, end_at
            )
            if not success:
                return None
            
            # Get updated entry
            row = self._repository.get_by_period_id(entry_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCHEDULE:
                return None
            
            updated_entry = self._rows_to_schedule_entries([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_entry.session_id)
            self._sync_entry_to_meilisearch(updated_entry, character_id)
            return updated_entry
        except Exception as e:
            logger.error(f"Failed to update schedule entry: {e}")
            return None

    def delete_entry(self, entry_id: int) -> bool:
        """Delete a schedule entry by database id"""
        try:
            # Get entry before deletion for Meilisearch cleanup
            row = self._repository.get_by_id(entry_id)
            if row and row.get("period_type") == PeriodRepository.PERIOD_TYPE_SCHEDULE:
                entry = self._rows_to_schedule_entries([row])[0]
                session_id = entry.session_id
                entry_identifier = entry.entry_id
            else:
                session_id = None
                entry_identifier = None
            
            success = self._repository.delete_by_id(entry_id)
            if success and session_id:
                self._session_repository.update_session_timestamp(session_id)
                # Delete from Meilisearch
                if entry_identifier and self._meilisearch and self._meilisearch.is_available:
                    self._meilisearch.delete_document(
                        entry_identifier,
                        index_name=MeilisearchService.PERIOD_INDEX
                    )
            return success
        except Exception as e:
            logger.error(f"Failed to delete schedule entry: {e}")
            return False

    def delete_entry_by_entry_id(self, entry_id: str) -> bool:
        """Delete a schedule entry by business entry_id"""
        try:
            # Get entry before deletion for Meilisearch cleanup
            row = self._repository.get_by_period_id(entry_id)
            if row and row.get("period_type") == PeriodRepository.PERIOD_TYPE_SCHEDULE:
                entry = self._rows_to_schedule_entries([row])[0]
                session_id = entry.session_id
            else:
                session_id = None
            
            success = self._repository.delete_by_period_id(entry_id)
            if success and session_id:
                self._session_repository.update_session_timestamp(session_id)
                # Delete from Meilisearch
                if row:
                    entry = self._rows_to_schedule_entries([row])[0]
                    if self._meilisearch and self._meilisearch.is_available:
                        self._meilisearch.delete_document(
                            entry.entry_id,
                            index_name=MeilisearchService.PERIOD_INDEX
                        )
            return success
        except Exception as e:
            logger.error(f"Failed to delete schedule entry: {e}")
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
            logger.error(f"ScheduleStore failed to ensure session: {exc}")
 