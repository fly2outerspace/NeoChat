"""High-level store for scenario records"""
from typing import List, Optional, Dict, Any
from uuid import uuid4

from app.logger import logger
from app.schema import Scenario
from app.storage.period_repository import PeriodRepository
from app.storage.session_repository import SQLiteSessionRepository
from app.storage.meilisearch_service import MeilisearchService


class ScenarioStore:
    """Singleton store managing scenario records"""

    _instance: Optional["ScenarioStore"] = None

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
        logger.debug(f"ScenarioStore switched to session: {session_id}")

    def add_scenarioitem(self, scenario: Scenario, character_id: Optional[str] = None) -> Scenario:
        """Add a scenario entry using schema"""
        content = scenario.content or ""
        title = scenario.title or ""
        scenario_identifier = scenario.scenario_id or uuid4().hex
        scenario_db_id = self._repository.insert_period(
            self._current_session_id,
            scenario_identifier,
            PeriodRepository.PERIOD_TYPE_SCENARIO,
            scenario.start_at,
            scenario.end_at,
            content,
            title,
            character_id,
            scenario.created_at,
        )
        self._session_repository.update_session_timestamp(self._current_session_id)
        stored = Scenario(
            session_id=self._current_session_id,
            scenario_id=scenario_identifier,
            start_at=scenario.start_at,
            end_at=scenario.end_at,
            content=content,
            title=title,
            created_at=scenario.created_at,
        )
        self._sync_scenario_to_meilisearch(stored, character_id)
        return stored

    def list_scenarios(self, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Scenario]:
        """List all scenarios for a session"""
        target_session = session_id or self._current_session_id
        rows = self._repository.list_by_session(target_session, PeriodRepository.PERIOD_TYPE_SCENARIO, character_id)
        return self._rows_to_scenarios(rows)

    def find_scenarios_at(self, time_point: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Scenario]:
        """Find scenarios covering a specific time point"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_time(target_session, time_point, PeriodRepository.PERIOD_TYPE_SCENARIO, character_id)
        return self._rows_to_scenarios(rows)

    def find_scenarios_in_range(self, start_at: str, end_at: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> List[Scenario]:
        """Find scenarios that overlap with the given time range"""
        target_session = session_id or self._current_session_id
        rows = self._repository.find_by_time_range(target_session, start_at, end_at, PeriodRepository.PERIOD_TYPE_SCENARIO, character_id)
        return self._rows_to_scenarios(rows)

    @staticmethod
    def _rows_to_scenarios(rows: List[dict]) -> List[Scenario]:
        """Convert database rows to Scenario objects"""
        scenarios: List[Scenario] = []
        for row in rows:
            scenarios.append(
                Scenario(
                    session_id=row["session_id"],
                    scenario_id=row.get("period_id"),  # period_id maps to scenario_id
                    start_at=row["start_at"],
                    end_at=row["end_at"],
                    content=row.get("content") or "",
                    title=row.get("title") or "",
                    created_at=row.get("created_at"),
                )
            )
        return scenarios

    def _prepare_meilisearch_document(self, scenario: Scenario, character_id: Optional[str] = None) -> Dict[str, Any]:
        """Convert scenario to Meilisearch document"""
        return {
            "id": scenario.scenario_id or "",
            "period_id": scenario.scenario_id or "",
            "period_type": PeriodRepository.PERIOD_TYPE_SCENARIO,
            "session_id": scenario.session_id,
            "content": scenario.content or "",
            "title": scenario.title or "",
            "start_at": scenario.start_at,
            "end_at": scenario.end_at,
            "character_id": character_id,
            "created_at": scenario.created_at or "",
        }

    def _sync_scenario_to_meilisearch(self, scenario: Scenario, character_id: Optional[str] = None):
        """Sync single scenario to Meilisearch"""
        if not getattr(self, "_meilisearch", None):
            return
        if not self._meilisearch.is_available:
            return
        document = self._prepare_meilisearch_document(scenario, character_id)
        ok = self._meilisearch.add_document(
            document,
            index_name=MeilisearchService.PERIOD_INDEX,
        )
        if not ok:
            logger.warning(f"Failed to index scenario to Meilisearch: {document}")

    def update_scenario_content(self, scenario_id: int, content: str) -> Optional[Scenario]:
        """Update content of a scenario by database id"""
        try:
            success = self._repository.update_content_by_id(scenario_id, content)
            if not success:
                return None
            
            # Get updated scenario
            row = self._repository.get_by_id(scenario_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCENARIO:
                return None
            
            updated_scenario = self._rows_to_scenarios([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_scenario.session_id)
            self._sync_scenario_to_meilisearch(updated_scenario, character_id)
            return updated_scenario
        except Exception as e:
            logger.error(f"Failed to update scenario content: {e}")
            return None

    def update_scenario_content_by_scenario_id(self, scenario_id: str, content: str) -> Optional[Scenario]:
        """Update content of a scenario by business scenario_id"""
        try:
            success = self._repository.update_content_by_period_id(scenario_id, content)
            if not success:
                return None
            
            # Get updated scenario
            row = self._repository.get_by_period_id(scenario_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCENARIO:
                return None
            
            updated_scenario = self._rows_to_scenarios([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_scenario.session_id)
            self._sync_scenario_to_meilisearch(updated_scenario, character_id)
            return updated_scenario
        except Exception as e:
            logger.error(f"Failed to update scenario content: {e}")
            return None

    def update_scenario_by_scenario_id(
        self,
        scenario_id: str,
        content: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        title: Optional[str] = None,
    ) -> Optional[Scenario]:
        """Update scenario fields by business scenario_id"""
        try:
            success = self._repository.update_by_period_id(
                scenario_id, content, start_at, end_at, title
            )
            if not success:
                return None
            
            # Get updated scenario
            row = self._repository.get_by_period_id(scenario_id)
            if not row or row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCENARIO:
                return None
            
            updated_scenario = self._rows_to_scenarios([row])[0]
            character_id = row.get("character_id")
            self._session_repository.update_session_timestamp(updated_scenario.session_id)
            self._sync_scenario_to_meilisearch(updated_scenario, character_id)
            return updated_scenario
        except Exception as e:
            logger.error(f"Failed to update scenario: {e}")
            return None

    def delete_scenario(self, scenario_id: int) -> bool:
        """Delete a scenario by database id"""
        try:
            # Get scenario before deletion for Meilisearch cleanup
            row = self._repository.get_by_id(scenario_id)
            if row and row.get("period_type") == PeriodRepository.PERIOD_TYPE_SCENARIO:
                scenario = self._rows_to_scenarios([row])[0]
                session_id = scenario.session_id
                scenario_identifier = scenario.scenario_id
            else:
                session_id = None
                scenario_identifier = None
            
            success = self._repository.delete_by_id(scenario_id)
            if success and session_id:
                self._session_repository.update_session_timestamp(session_id)
                # Delete from Meilisearch
                if scenario_identifier and self._meilisearch and self._meilisearch.is_available:
                    self._meilisearch.delete_document(
                        scenario_identifier,
                        index_name=MeilisearchService.PERIOD_INDEX
                    )
            return success
        except Exception as e:
            logger.error(f"Failed to delete scenario: {e}")
            return False

    def delete_scenario_by_scenario_id(self, scenario_id: str) -> bool:
        """Delete a scenario by business scenario_id"""
        try:
            # Get scenario before deletion for Meilisearch cleanup
            row = self._repository.get_by_period_id(scenario_id)
            if row and row.get("period_type") == PeriodRepository.PERIOD_TYPE_SCENARIO:
                scenario = self._rows_to_scenarios([row])[0]
                session_id = scenario.session_id
            else:
                session_id = None
            
            success = self._repository.delete_by_period_id(scenario_id)
            if success and session_id:
                self._session_repository.update_session_timestamp(session_id)
                # Delete from Meilisearch
                if self._meilisearch and self._meilisearch.is_available:
                    self._meilisearch.delete_document(
                        scenario_id,
                        index_name=MeilisearchService.PERIOD_INDEX
                    )
            return success
        except Exception as e:
            logger.error(f"Failed to delete scenario: {e}")
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
            logger.error(f"ScenarioStore failed to ensure session: {exc}")


