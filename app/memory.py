"""Memory management for agent conversation history"""
from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field

from app.logger import logger
from app.schema import Message, QueryMetadata, ScheduleEntry, Scenario, Event, Relation
from app.storage.meilisearch_service import MeilisearchService
from app.storage.message_store import MessageStore
from app.storage.period_repository import PeriodRepository
from app.storage.schedule_store import ScheduleStore
from app.storage.scenario_store import ScenarioStore
from app.storage.event_store import EventStore
from app.storage.relation_store import RelationStore
from app.utils import get_current_time, get_current_datetime
from app.utils.time_provider import time_provider
from app.storage.session_clock_repository import SessionClockRepository


class Memory(BaseModel):
    """Agent memory store for conversation messages
    
    All memory operations are automatically synchronized with MessageStore.
    When session_id is provided, messages are persisted to storage.
    """
    
    messages: List[Message] = Field(default_factory=list)
    max_messages: int = Field(default=100)
    session_id: Optional[str] = Field(
        default=None, description="Session ID for loading messages from storage"
    )
    character_id: Optional[str] = Field(
        default=None, description="Character ID for filtering data by character"
    )

    def model_post_init(self, __context: Any) -> None:
        """Initialize session clock configuration if session_id is provided
        
        Only loads session clock configuration. Messages are loaded on-demand
        via the agent's messages property using static methods.
        """
        if self.session_id:
            try:
                # Load session clock configuration
                self._load_session_clock()
                self.messages = []
            except Exception as e:
                logger.warning(f"Failed to load session clock for session {self.session_id}: {e}")
    
    def _load_session_clock(self) -> None:
        """Load session clock configuration from database"""
        try:
            clock_repo = SessionClockRepository()
            clock_data = clock_repo.get_by_session_id(self.session_id)
            if clock_data:
                time_provider.load_session_clock(
                    session_id=self.session_id,
                    base_virtual=clock_data.get('virtual_base'),
                    base_real=clock_data.get('real_base'),
                    actions=clock_data.get('actions'),
                )
        except Exception as e:
            logger.warning(f"Failed to load session clock for {self.session_id}: {e}")

    def _get_message_store(self) -> MessageStore:
        """Get message store instance and ensure session is set"""
        message_store = MessageStore()
        if self.session_id:
            message_store.set_session(self.session_id)
        return message_store

    @staticmethod
    def get_messages(
        session_id: str,
        max_messages: int = 100
    ) -> List[Message]:
        """Get messages for a session (basic method without time filters)
        
        This is the most basic method to retrieve messages. It loads all messages
        for the session and returns the most recent ones up to max_messages.
        
        Args:
            session_id: Session ID for querying messages
            max_messages: Maximum number of messages to return (default: 100)
            
        Returns:
            List of messages sorted by created_at (most recent first)
            
        Example:
            Memory.get_messages('session_id', max_messages=50)
            # Returns the 50 most recent messages for the session
        """
        if not session_id:
            logger.warning("session_id is required for message queries")
            return []
        
        try:
            message_store = MessageStore()
            message_store.set_session(session_id)
            all_messages = message_store.load_messages()
            # Return most recent messages, limited by max_messages
            return all_messages[-max_messages:] if len(all_messages) > max_messages else all_messages
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    @staticmethod
    def get_messages_around_time(
        session_id: str,
        time_point: str, 
        hours: float = 1.0,
        max_messages: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get messages around a specific time point
        
        Algorithm: Scan forward and backward from time_point within the time range,
        then merge and sort by time distance, return the closest messages.
        Queries the database directly for better performance.
        Requires session_id to be set.
        
        Args:
            session_id: Session ID for querying messages
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            hours: Time range in hours before and after time_point (default: 1.0)
            max_messages_per_direction: Max messages to scan in each direction (default: 100)
            categories: Optional list of category filters. If None or empty, returns all categories.
            
        Returns:
            Tuple of (List of messages sorted by created_at, QueryMetadata)
            
        Warning:
            The messages returned by this function should NOT be directly sent to LLM,
            as there is a high probability of breaking the correspondence between assistant
            and tool messages. When using category filter, this correspondence may not exist
            at all. Post-processing is required before use.
            
        Example:
            Memory.get_messages_around_time('session_id', '2024-01-15 14:30:00', category=1)
            # Returns up to 100 messages before and 100 messages after 14:30:00
            # within 1 hour range, sorted by proximity to the time point
        """
        if not session_id:
            logger.warning("session_id is required for time-based queries")
            return [], QueryMetadata()
        
        try:
            message_store = MessageStore()
            message_store.set_session(session_id)
            return message_store.get_messages_around_time(
                time_point, hours, max_messages, categories, character_id
            )
        except Exception as e:
            logger.error(f"Failed to get messages around time: {e}")
            return [], QueryMetadata()

    @staticmethod
    def get_messages_in_range(
        session_id: str,
        start_time: str, 
        end_time: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get messages within a specific time range
        
        Queries the database directly for better performance.
        Requires session_id to be set.
        
        Args:
            session_id: Session ID for querying messages
            start_time: Start time string in format 'YYYY-MM-DD HH:MM:SS'
            end_time: End time string in format 'YYYY-MM-DD HH:MM:SS'
            max_results: Maximum number of messages to return (default: 100)
            categories: Optional list of category filters. If None or empty, returns all categories.
            character_id: Optional character ID for filtering. If None, returns messages visible to all characters.
            
        Returns:
            Tuple of (List of messages within the time range, QueryMetadata)
            
        Warning:
            The messages returned by this function should NOT be directly sent to LLM,
            as there is a high probability of breaking the correspondence between assistant
            and tool messages. When using category filter, this correspondence may not exist
            at all. Post-processing is required before use.
            
        Example:
            Memory.get_messages_in_range('session_id', '2024-01-15 09:00:00', '2024-01-15 18:00:00', category=1)
            # Returns messages between 9:00 and 18:00 on 2024-01-15 with category=1
        """
        if not session_id:
            logger.warning("session_id is required for time-based queries")
            return [], QueryMetadata()
        
        try:
            message_store = MessageStore()
            message_store.set_session(session_id)
            return message_store.get_messages_in_range(start_time, end_time, max_results, categories, character_id)
        except Exception as e:
            logger.error(f"Failed to get messages in range: {e}")
            return [], QueryMetadata()

    @staticmethod
    def get_messages_by_date(
        session_id: str,
        date: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> tuple[List[Message], QueryMetadata]:
        """Get all messages on a specific date
        
        Queries the database directly for better performance.
        Requires session_id to be set.
        
        Args:
            session_id: Session ID for querying messages
            date: Date string in format 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM:SS'
                  If time is included, only date part is used
            max_results: Maximum number of messages to return (default: 100)
            categories: Optional list of category filters. If None or empty, returns all categories.
            character_id: Optional character ID for filtering. If None, returns messages visible to all characters.
            
        Returns:
            Tuple of (List of messages on the specified date, QueryMetadata)
            
        Warning:
            The messages returned by this function should NOT be directly sent to LLM,
            as there is a high probability of breaking the correspondence between assistant
            and tool messages. When using category filter, this correspondence may not exist
            at all. Post-processing is required before use.
            
        Example:
            Memory.get_messages_by_date('session_id', '2024-01-15', category=1)
            # Returns messages on January 15, 2024 with category=1 (up to max_results)
        """
        if not session_id:
            logger.warning("session_id is required for time-based queries")
            return [], QueryMetadata()
        
        try:
            message_store = MessageStore()
            message_store.set_session(session_id)
            return message_store.get_messages_by_date(date, max_results, categories, character_id)
        except Exception as e:
            logger.error(f"Failed to get messages by date: {e}")
            return [], QueryMetadata()

    def add_message(self, message: Message) -> None:
        """Add a message to memory and save to storage
        
        Raises:
            ValueError: If session_id is not set
        """
        if not self.session_id:
            raise ValueError("session_id is required. Set Memory.session_id before adding messages")
        
        self.messages.append(message)
        if len(self.messages) > self.max_messages:
            self.messages = self.messages[-self.max_messages :]
        
        # Save to storage
        try:
            message_store = self._get_message_store()
            message_store.save_message(message)
        except Exception as e:
            logger.error(f"Failed to save message to storage: {e}")
            raise


    def clear(self) -> None:
        """Clear all messages from memory and storage"""
        self.messages.clear()
        
        # Clear from storage if session_id is set
        if self.session_id:
            try:
                message_store = self._get_message_store()
                message_store.clear_messages(self.session_id)
            except Exception as e:
                logger.error(f"Failed to clear messages from storage: {e}")


    def set_messages(self, messages: List[Message]) -> None:
        """Set messages list and sync to storage
        
        WARNING: This method will overwrite all messages in the database for this session.
        Use with caution. For normal operations, use add_message() instead.
        
        This method should be used instead of directly assigning to messages
        to ensure synchronization with storage.
        
        Args:
            messages: List of messages to set
        """
        self.messages = messages
        # Sync to storage if session_id is set
        if self.session_id:
            try:
                message_store = self._get_message_store()
                # WARNING: This overwrites all messages in database
                # Only use this when you intentionally want to replace all messages
                message_store.save_messages(self.messages)
                logger.warning(f"set_messages() called - all messages for session {self.session_id} were overwritten in database")
            except Exception as e:
                logger.error(f"Failed to sync messages to storage: {e}")

    # ========== Schedule Methods ==========
    
    def add_schedule_entry(self, entry: ScheduleEntry) -> ScheduleEntry:
        """Add a schedule entry to memory and save to storage
        
        Args:
            entry: ScheduleEntry to add. session_id will be set from self.session_id if not provided.
            
        Returns:
            ScheduleEntry with id and session_id set
            
        Raises:
            ValueError: If session_id is not set and entry.session_id is not provided
        """
        if not self.session_id and not entry.session_id:
            raise ValueError("session_id is required. Set Memory.session_id or provide entry.session_id")
        
        target_session = self.session_id or entry.session_id
        entry.session_id = target_session
        
        try:
            schedule_store = ScheduleStore()
            schedule_store.set_session(target_session)
            stored_entry = schedule_store.add_schedule_entry(entry, character_id=self.character_id)
            return stored_entry
        except Exception as e:
            logger.error(f"Failed to add schedule entry to storage: {e}")
            raise

    @staticmethod
    def get_schedule_entries(session_id: str, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """Get all schedule entries for a session
        
        Args:
            session_id: Session ID for querying schedules
            character_id: Optional character ID for filtering
            
        Returns:
            List of ScheduleEntry objects
            
        Example:
            Memory.get_schedule_entries('session_id')
            # Returns all schedule entries for the session
        """
        if not session_id:
            logger.warning("session_id is required for schedule queries")
            return []
        
        try:
            schedule_store = ScheduleStore()
            schedule_store.set_session(session_id)
            return schedule_store.list_entries(session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get schedule entries: {e}")
            return []

    @staticmethod
    def get_schedule_entries_at(session_id: str, time_point: str, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """Get schedule entries covering a specific time point
        
        Args:
            session_id: Session ID for querying schedules
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            character_id: Optional character ID for filtering
            
        Returns:
            List of ScheduleEntry objects that cover the time point
            
        Example:
            Memory.get_schedule_entries_at('session_id', '2024-01-15 14:30:00')
            # Returns schedule entries that cover 14:30:00
        """
        if not session_id:
            logger.warning("session_id is required for schedule queries")
            return []
        
        try:
            schedule_store = ScheduleStore()
            schedule_store.set_session(session_id)
            return schedule_store.find_entries_at(time_point, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get schedule entries at time: {e}")
            return []

    @staticmethod
    def get_schedule_entries_by_date(session_id: str, date: str, character_id: Optional[str] = None) -> List[ScheduleEntry]:
        """Get schedule entries where start_at or end_at matches the date
        
        Args:
            session_id: Session ID for querying schedules
            date: Date string in format 'YYYY-MM-DD' (e.g., '2024-01-15')
            character_id: Optional character ID for filtering
            
        Returns:
            List of ScheduleEntry objects where start_at or end_at matches the date
            
        Example:
            Memory.get_schedule_entries_by_date('session_id', '2024-01-15')
            # Returns schedule entries where start_at or end_at is on 2024-01-15
        """
        if not session_id:
            logger.warning("session_id is required for schedule queries")
            return []
        
        try:
            schedule_store = ScheduleStore()
            schedule_store.set_session(session_id)
            return schedule_store.find_entries_by_date(date, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get schedule entries by date: {e}")
            return []

    # ========== Scenario Methods ==========
    
    def add_scenario(self, scenario: Scenario) -> Scenario:
        """Add a scenario to memory and save to storage
        
        Args:
            scenario: Scenario to add. session_id will be set from self.session_id if not provided.
            
        Returns:
            Scenario with id and session_id set
            
        Raises:
            ValueError: If session_id is not set and scenario.session_id is not provided
        """
        if not self.session_id and not scenario.session_id:
            raise ValueError("session_id is required. Set Memory.session_id or provide scenario.session_id")
        
        target_session = self.session_id or scenario.session_id
        scenario.session_id = target_session
        
        try:
            scenario_store = ScenarioStore()
            scenario_store.set_session(target_session)
            stored_scenario = scenario_store.add_scenarioitem(scenario, character_id=self.character_id)
            return stored_scenario
        except Exception as e:
            logger.error(f"Failed to add scenario to storage: {e}")
            raise


    @staticmethod
    def get_scenario_by_scenario_id(scenario_id: str, session_id: str) -> Optional[Scenario]:
        """Get a scenario by business scenario_id
        
        Args:
            scenario_id: Business scenario_id of the scenario
            session_id: Session ID for querying scenarios
            
        Returns:
            Scenario object if found, None otherwise
            
        Example:
            Memory.get_scenario_by_scenario_id('scenario-123', 'session_id')
            # Returns the scenario with scenario_id='scenario-123' if it exists
        """
        if not session_id:
            logger.warning("session_id is required for scenario queries")
            return None
        
        if not scenario_id:
            logger.warning("scenario_id is required")
            return None
        
        try:
            scenario_store = ScenarioStore()
            scenario_store.set_session(session_id)
            
            # Get period from repository by period_id (scenario_id maps to period_id)
            row = scenario_store._repository.get_by_period_id(scenario_id)
            
            if not row:
                return None
            
            # Verify it's a scenario and belongs to the current session
            if row.get("period_type") != PeriodRepository.PERIOD_TYPE_SCENARIO:
                return None
            
            if row.get("session_id") != session_id:
                return None
            
            # Convert to Scenario object
            scenario = ScenarioStore._rows_to_scenarios([row])[0]
            
            return scenario
        except Exception as e:
            logger.error(f"Failed to get scenario by scenario_id: {e}")
            return None

    @staticmethod
    def get_scenarios_at(session_id: str, time_point: str, character_id: Optional[str] = None) -> List[Scenario]:
        """Get scenarios covering a specific time point
        
        Args:
            session_id: Session ID for querying scenarios
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            character_id: Optional character ID for filtering
            
        Returns:
            List of Scenario objects that cover the time point
            
        Example:
            Memory.get_scenarios_at('session_id', '2024-01-15 14:30:00')
            # Returns scenarios that cover 14:30:00
        """
        if not session_id:
            logger.warning("session_id is required for scenario queries")
            return []
        
        try:
            scenario_store = ScenarioStore()
            scenario_store.set_session(session_id)
            return scenario_store.find_scenarios_at(time_point, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get scenarios at time: {e}")
            return []

    @staticmethod
    def get_scenarios_in_range(session_id: str, start_at: str, end_at: str, character_id: Optional[str] = None) -> List[Scenario]:
        """Get scenarios that overlap with the given time range
        
        Args:
            session_id: Session ID for querying scenarios
            start_at: Start time of the query range in format 'YYYY-MM-DD HH:MM:SS'
            end_at: End time of the query range in format 'YYYY-MM-DD HH:MM:SS'
            character_id: Optional character ID for filtering
            
        Returns:
            List of Scenario objects that overlap with the time range
            
        Example:
            Memory.get_scenarios_in_range('session_id', '2024-01-15 10:00:00', '2024-01-15 15:00:00')
            # Returns scenarios that overlap with the time range
        """
        if not session_id:
            logger.warning("session_id is required for scenario queries")
            return []
        
        try:
            scenario_store = ScenarioStore()
            scenario_store.set_session(session_id)
            return scenario_store.find_scenarios_in_range(start_at, end_at, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get scenarios in range: {e}")
            return []


    # ========== Schedule Update & Delete Methods ==========
    
    @staticmethod
    def update_schedule_entry_by_entry_id(
        entry_id: str,
        content: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[ScheduleEntry]:
        """Update schedule entry fields by business entry_id
        
        Args:
            entry_id: Business entry_id of the schedule entry
            content: New content to set (optional)
            start_at: New start time to set (optional)
            end_at: New end time to set (optional)
            session_id: Optional session_id for setting store context
            
        Returns:
            Updated ScheduleEntry if successful, None otherwise
            
        Example:
            Memory.update_schedule_entry_by_entry_id("entry-123", content="Updated", start_at="2024-01-15 10:00:00", session_id="session_id")
        """
        try:
            schedule_store = ScheduleStore()
            if session_id:
                schedule_store.set_session(session_id)
            return schedule_store.update_entry_by_entry_id(entry_id, content, start_at, end_at)
        except Exception as e:
            logger.error(f"Failed to update schedule entry: {e}")
            return None


    @staticmethod
    def delete_schedule_entry_by_entry_id(entry_id: str, session_id: Optional[str] = None) -> bool:
        """Delete a schedule entry by business entry_id
        
        Args:
            entry_id: Business entry_id of the schedule entry
            session_id: Optional session_id for setting store context
            
        Returns:
            True if deletion was successful, False otherwise
            
        Example:
            Memory.delete_schedule_entry_by_entry_id("entry-123", "session_id")
        """
        try:
            schedule_store = ScheduleStore()
            if session_id:
                schedule_store.set_session(session_id)
            return schedule_store.delete_entry_by_entry_id(entry_id)
        except Exception as e:
            logger.error(f"Failed to delete schedule entry: {e}")
            return False

    # ========== Scenario Update & Delete Methods ==========
    

    @staticmethod
    def update_scenario_by_scenario_id(
        scenario_id: str,
        content: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Scenario]:
        """Update scenario fields by business scenario_id
        
        Args:
            scenario_id: Business scenario_id of the scenario
            content: New content to set (optional)
            start_at: New start time to set (optional)
            end_at: New end time to set (optional)
            title: New title to set (optional)
            session_id: Optional session_id for setting store context
            
        Returns:
            Updated Scenario if successful, None otherwise
            
        Example:
            Memory.update_scenario_by_scenario_id("scenario-123", content="Updated", start_at="2024-01-15 10:00:00", title="New Title", session_id="session_id")
        """
        try:
            scenario_store = ScenarioStore()
            if session_id:
                scenario_store.set_session(session_id)
            return scenario_store.update_scenario_by_scenario_id(scenario_id, content, start_at, end_at, title)
        except Exception as e:
            logger.error(f"Failed to update scenario: {e}")
            return None


    @staticmethod
    def delete_scenario_by_scenario_id(scenario_id: str, session_id: Optional[str] = None) -> bool:
        """Delete a scenario by business scenario_id
        
        Args:
            scenario_id: Business scenario_id of the scenario
            session_id: Optional session_id for setting store context
            
        Returns:
            True if deletion was successful, False otherwise
            
        Example:
            Memory.delete_scenario_by_scenario_id("scenario-123", "session_id")
        """
        try:
            scenario_store = ScenarioStore()
            if session_id:
                scenario_store.set_session(session_id)
            return scenario_store.delete_scenario_by_scenario_id(scenario_id)
        except Exception as e:
            logger.error(f"Failed to delete scenario: {e}")
            return False

    # ========== Meilisearch Search Methods ==========
    
    @staticmethod
    def search_messages_by_keyword(
        session_id: str,
        keyword: str,
        category: Optional[Union[int, List[int]]] = None,
        limit: int = 100,
        offset: int = 0,
        sort: Optional[List[str]] = None,
        character_id: Optional[str] = None,
    ) -> tuple[List[Message], QueryMetadata]:
        """Search messages by keyword using Meilisearch
        
        Args:
            session_id: Session ID for querying messages
            keyword: Keyword to search for
            category: Optional category filter (default: None, searches all categories)
                     Can be a single int or a list of ints. If list, searches each category and merges results.
            limit: Maximum number of results to return (default: 100)
            offset: Offset for pagination (default: 0)
            sort: Optional sort order (default: ["created_at:desc"])
            character_id: Optional character ID for filtering. If None, returns messages visible to all characters.
            
        Returns:
            Tuple of (List of Message objects, QueryMetadata)
            
        Example:
            Memory.search_messages_by_keyword('session_id', 'test', category=1, limit=50)
            Memory.search_messages_by_keyword('session_id', 'test', category=[1, 2], limit=50)
        """
        if not session_id:
            logger.warning("session_id is required for message search")
            return [], QueryMetadata()
        
        try:
            meilisearch = MeilisearchService()
            if not meilisearch.is_available:
                logger.warning("Meilisearch is not available for message search")
                return [], QueryMetadata()
            
            # Handle multiple categories by searching each and merging results
            if isinstance(category, list) and len(category) > 0:
                all_messages = []
                all_message_ids = set()  # For deduplication
                total_estimated = 0
                
                # Search each category separately
                for cat in category:
                    results = meilisearch.search(
                        query=keyword,
                        session_id=session_id,
                        category=cat,
                        limit=limit,  # Get limit results per category
                        offset=0,  # Start from 0 for each category
                        sort=sort or ["created_at:desc"],
                        character_id=character_id,
                    )
                    
                    # Convert search results to Message objects
                    for hit in results.get("hits", []):
                        msg_id = hit.get("id")
                        # Deduplicate by message ID
                        if msg_id not in all_message_ids:
                            all_message_ids.add(msg_id)
                            msg = Message(
                                role=hit.get("role", "user"),
                                content=hit.get("content"),
                                tool_name=hit.get("tool_name"),
                                speaker=hit.get("speaker"),
                                tool_call_id=hit.get("tool_call_id"),
                                created_at=hit.get("created_at"),
                                category=hit.get("category", 0),
                                visible_for_characters=hit.get("character_ids") or []
                            )
                            all_messages.append(msg)
                    
                    # Accumulate estimated total
                    total_estimated += results.get("estimatedTotalHits", 0)
                
                # Sort all messages by created_at (descending by default)
                sort_desc = True
                if sort:
                    for s in sort:
                        if ":asc" in s.lower():
                            sort_desc = False
                            break
                
                all_messages.sort(
                    key=lambda m: m.created_at or "",
                    reverse=sort_desc
                )
                
                # Apply limit and offset
                total_messages = len(all_messages)
                start_idx = offset
                end_idx = offset + limit
                messages = all_messages[start_idx:end_idx]
                
                # Create metadata
                metadata = QueryMetadata(
                    has_more_before=start_idx > 0,
                    has_more_after=end_idx < total_messages,
                    time_point=None
                )
                
                return messages, metadata
            else:
                # Single category or None - use original logic
                results = meilisearch.search(
                    query=keyword,
                    session_id=session_id,
                    category=category if not isinstance(category, list) else None,
                limit=limit,
                offset=offset,
                sort=sort or ["created_at:desc"],
                    character_id=character_id,
            )
            
            # Convert search results to Message objects
            messages = []
            for hit in results.get("hits", []):
                msg = Message(
                    role=hit.get("role", "user"),
                    content=hit.get("content"),
                    tool_name=hit.get("tool_name"),
                    speaker=hit.get("speaker"),
                    tool_call_id=hit.get("tool_call_id"),
                    created_at=hit.get("created_at"),
                        category=hit.get("category", 0),
                        visible_for_characters=hit.get("character_ids") or []
                )
                messages.append(msg)
            
            # Create metadata
            estimated_total = results.get("estimatedTotalHits", 0)
            metadata = QueryMetadata(
                has_more_before=estimated_total > offset + len(messages),
                has_more_after=False,
                time_point=None
            )
            
            return messages, metadata
        except Exception as e:
            logger.error(f"Failed to search messages by keyword: {e}")
            return [], QueryMetadata()

    @staticmethod
    def search_schedule_entries_by_keyword(
        session_id: str,
        keyword: str,
        limit: int = 50,
        offset: int = 0,
        sort: Optional[List[str]] = None,
        character_id: Optional[str] = None,
    ) -> List[ScheduleEntry]:
        """Search schedule entries by keyword using Meilisearch
        
        Args:
            session_id: Session ID for querying schedules
            keyword: Keyword to search for
            limit: Maximum number of results to return (default: 50)
            offset: Offset for pagination (default: 0)
            sort: Optional sort order (default: ["start_at:asc"])
            
        Returns:
            List of ScheduleEntry objects
            
        Example:
            Memory.search_schedule_entries_by_keyword('session_id', 'meeting')
        """
        if not session_id:
            logger.warning("session_id is required for schedule search")
            return []
        
        try:
            meilisearch = MeilisearchService()
            if not meilisearch.is_available:
                logger.warning("Meilisearch is not available for schedule search")
                return []
            
            # Build filters
            filters = ['period_type = "schedule"']
            if character_id is not None:
                filters.append(f'character_id = "{character_id}"')
            else:
                filters.append('character_id = null')
            
            # Search schedule entries
            results = meilisearch.search(
                query=keyword,
                session_id=session_id,
                limit=limit,
                offset=offset,
                sort=sort or ["start_at:asc"],
                index_name=MeilisearchService.PERIOD_INDEX,
                filters=filters,
            )
            
            # Convert search results to ScheduleEntry objects
            entries = []
            for hit in results.get("hits", []):
                entry = ScheduleEntry(
                    entry_id=hit.get("period_id") or "",
                    session_id=hit.get("session_id") or session_id,
                    start_at=hit.get("start_at") or "",
                    end_at=hit.get("end_at") or "",
                    content=hit.get("content") or "",
                    created_at=hit.get("created_at"),
                )
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"Failed to search schedule entries by keyword: {e}")
            return []

    @staticmethod
    def search_scenarios_by_keyword(
        session_id: str,
        keyword: str,
        limit: int = 50,
        offset: int = 0,
        sort: Optional[List[str]] = None,
        character_id: Optional[str] = None,
    ) -> List[Scenario]:
        """Search scenarios by keyword using Meilisearch
        
        Args:
            session_id: Session ID for querying scenarios
            keyword: Keyword to search for
            limit: Maximum number of results to return (default: 50)
            offset: Offset for pagination (default: 0)
            sort: Optional sort order (default: ["start_at:asc"])
            
        Returns:
            List of Scenario objects
            
        Example:
            Memory.search_scenarios_by_keyword('session_id', 'meeting')
        """
        if not session_id:
            logger.warning("session_id is required for scenario search")
            return []
        
        try:
            meilisearch = MeilisearchService()
            if not meilisearch.is_available:
                logger.warning("Meilisearch is not available for scenario search")
                return []
            
            # Build filters
            filters = ['period_type = "scenario"']
            if character_id is not None:
                filters.append(f'character_id = "{character_id}"')
            else:
                filters.append('character_id = null')
            
            # Search scenario entries
            results = meilisearch.search(
                query=keyword,
                session_id=session_id,
                limit=limit,
                offset=offset,
                sort=sort or ["start_at:asc"],
                index_name=MeilisearchService.PERIOD_INDEX,
                filters=filters,
            )
            
            # Convert search results to Scenario objects
            entries = []
            for hit in results.get("hits", []):
                entry = Scenario(
                    session_id=hit.get("session_id") or session_id,
                    scenario_id=hit.get("period_id"),
                    start_at=hit.get("start_at") or "",
                    end_at=hit.get("end_at") or "",
                    content=hit.get("content") or "",
                    title=hit.get("title") or "",
                    created_at=hit.get("created_at"),
                )
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"Failed to search scenarios by keyword: {e}")
            return []

    # ========== Event Methods ==========
    
    def add_event(self, event: Event) -> Event:
        """Add an event to memory and save to storage
        
        Args:
            event: Event to add. session_id will be set from self.session_id if not provided.
            
        Returns:
            Event with id and session_id set
            
        Raises:
            ValueError: If session_id is not set and event.session_id is not provided
        """
        if not self.session_id and not event.session_id:
            raise ValueError("session_id is required. Set Memory.session_id or provide event.session_id")
        
        target_session = self.session_id or event.session_id
        event.session_id = target_session
        
        try:
            event_store = EventStore()
            event_store.set_session(target_session)
            stored_event = event_store.add_event(event, character_id=self.character_id)
            return stored_event
        except Exception as e:
            logger.error(f"Failed to add event to storage: {e}")
            raise

    @staticmethod
    def get_events_at(session_id: str, time_point: str, character_id: Optional[str] = None) -> List[Event]:
        """Get events covering a specific time point
        
        Args:
            session_id: Session ID for querying events
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            character_id: Optional character ID for filtering
            
        Returns:
            List of Event objects that cover the time point
            
        Example:
            Memory.get_events_at('session_id', '2024-01-15 14:30:00')
            # Returns events that cover 14:30:00
        """
        if not session_id:
            logger.warning("session_id is required for event queries")
            return []
        
        try:
            event_store = EventStore()
            event_store.set_session(session_id)
            return event_store.find_events_at(time_point, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get events at time: {e}")
            return []

    @staticmethod
    def get_events_in_range(session_id: str, start_at: str, end_at: str, character_id: Optional[str] = None) -> List[Event]:
        """Get events that overlap with the given time range
        
        Args:
            session_id: Session ID for querying events
            start_at: Start time of the query range in format 'YYYY-MM-DD HH:MM:SS'
            end_at: End time of the query range in format 'YYYY-MM-DD HH:MM:SS'
            character_id: Optional character ID for filtering
            
        Returns:
            List of Event objects that overlap with the time range
            
        Example:
            Memory.get_events_in_range('session_id', '2024-01-15 10:00:00', '2024-01-15 15:00:00')
            # Returns events that overlap with the time range
        """
        if not session_id:
            logger.warning("session_id is required for event queries")
            return []
        
        try:
            event_store = EventStore()
            event_store.set_session(session_id)
            return event_store.find_events_in_range(start_at, end_at, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get events in range: {e}")
            return []

    @staticmethod
    def search_events_by_keyword(
        session_id: str,
        keyword: str,
        limit: int = 50,
        offset: int = 0,
        sort: Optional[List[str]] = None,
        character_id: Optional[str] = None,
    ) -> List[Event]:
        """Search events by keyword using Meilisearch
        
        Args:
            session_id: Session ID for querying events
            keyword: Keyword to search for
            limit: Maximum number of results to return (default: 50)
            offset: Offset for pagination (default: 0)
            sort: Optional sort order (default: ["start_at:asc"])
            character_id: Optional character ID for filtering
            
        Returns:
            List of Event objects matching the keyword
            
        Example:
            Memory.search_events_by_keyword('session_id', 'meeting', limit=50)
        """
        if not session_id:
            logger.warning("session_id is required for event search")
            return []
        
        try:
            meilisearch = MeilisearchService()
            if not meilisearch.is_available:
                logger.warning("Meilisearch is not available for event search")
                return []
            
            # Build filters
            filters = ['period_type = "event"']
            if character_id is not None:
                filters.append(f'character_id = "{character_id}"')
            else:
                filters.append('character_id = null')
            
            # Search event entries
            results = meilisearch.search(
                query=keyword,
                session_id=session_id,
                limit=limit,
                offset=offset,
                sort=sort or ["start_at:asc"],
                index_name=MeilisearchService.PERIOD_INDEX,
                filters=filters,
            )
            
            # Convert search results to Event objects
            entries = []
            for hit in results.get("hits", []):
                entry = Event(
                    session_id=hit.get("session_id") or session_id,
                    event_id=hit.get("period_id"),
                    start_at=hit.get("start_at") or "",
                    end_at=hit.get("end_at") or "",
                    scene=hit.get("content") or "",  # content maps to scene
                    title=hit.get("title") or "",
                    created_at=hit.get("created_at"),
                )
                entries.append(entry)
            
            return entries
        except Exception as e:
            logger.error(f"Failed to search events by keyword: {e}")
            return []

    @staticmethod
    def update_event_by_event_id(
        event_id: str,
        scene: Optional[str] = None,
        start_at: Optional[str] = None,
        end_at: Optional[str] = None,
        title: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Optional[Event]:
        """Update event fields by business event_id
        
        Args:
            event_id: Business event_id of the event
            scene: New scene to set (optional)
            start_at: New start time to set (optional)
            end_at: New end time to set (optional)
            title: New title to set (optional)
            session_id: Optional session_id for setting store context
            
        Returns:
            Updated Event if successful, None otherwise
            
        Example:
            Memory.update_event_by_event_id("event-123", scene="Updated scene", start_at="2024-01-15 10:00:00", title="New Title", session_id="session_id")
        """
        try:
            event_store = EventStore()
            if session_id:
                event_store.set_session(session_id)
            return event_store.update_event_by_event_id(event_id, scene, start_at, end_at, title)
        except Exception as e:
            logger.error(f"Failed to update event: {e}")
            return None

    @staticmethod
    def delete_event_by_event_id(event_id: str, session_id: Optional[str] = None) -> bool:
        """Delete an event by business event_id
        
        Args:
            event_id: Business event_id of the event
            session_id: Optional session_id for setting store context
            
        Returns:
            True if deletion was successful, False otherwise
            
        Example:
            Memory.delete_event_by_event_id("event-123", "session_id")
        """
        try:
            event_store = EventStore()
            if session_id:
                event_store.set_session(session_id)
            return event_store.delete_event_by_event_id(event_id)
        except Exception as e:
            logger.error(f"Failed to delete event: {e}")
            return False

    # ========== Relation Methods ==========
    
    def add_relation(self, relation: Relation) -> Relation:
        """Add a relation to memory and save to storage
        
        Args:
            relation: Relation to add. session_id will be set from self.session_id if not provided.
            
        Returns:
            Relation with id and session_id set
            
        Raises:
            ValueError: If session_id is not set and relation.session_id is not provided
        """
        if not self.session_id and not relation.session_id:
            raise ValueError("session_id is required. Set Memory.session_id or provide relation.session_id")
        
        target_session = self.session_id or relation.session_id
        relation.session_id = target_session
        
        try:
            relation_store = RelationStore()
            relation_store.set_session(target_session)
            stored_relation = relation_store.add_relation(relation, character_id=self.character_id)
            return stored_relation
        except Exception as e:
            logger.error(f"Failed to add relation to storage: {e}")
            raise

    @staticmethod
    def get_relation_by_relation_id(relation_id: str, session_id: str, character_id: Optional[str] = None) -> Optional[Relation]:
        """Get a relation by business relation_id, optionally filtered by character_id
        
        Args:
            relation_id: Business relation_id of the relation
            session_id: Session ID for querying relations
            character_id: Optional character ID for filtering. If None, returns relations where character_id IS NULL.
            
        Returns:
            Relation object if found, None otherwise
            
        Example:
            Memory.get_relation_by_relation_id('relation-123', 'session_id')
            Memory.get_relation_by_relation_id('relation-123', 'session_id', character_id='char-123')
        """
        if not session_id:
            logger.warning("session_id is required for relation queries")
            return None
        
        if not relation_id:
            logger.warning("relation_id is required")
            return None
        
        try:
            relation_store = RelationStore()
            relation_store.set_session(session_id)
            return relation_store.get_by_relation_id(relation_id, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get relation by relation_id: {e}")
            return None

    @staticmethod
    def get_relations(session_id: str, character_id: Optional[str] = None) -> List[Relation]:
        """Get all relations for a session, optionally filtered by character_id
        
        Args:
            session_id: Session ID for querying relations
            character_id: Optional character ID for filtering. If None, returns relations where character_id IS NULL.
            
        Returns:
            List of Relation objects
            
        Example:
            Memory.get_relations('session_id')
            Memory.get_relations('session_id', character_id='char-123')
        """
        if not session_id:
            logger.warning("session_id is required for relation queries")
            return []
        
        try:
            relation_store = RelationStore()
            relation_store.set_session(session_id)
            return relation_store.list_relations(session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to get relations: {e}")
            return []

    @staticmethod
    def update_relation_by_relation_id(
        relation_id: str,
        name: Optional[str] = None,
        knowledge: Optional[str] = None,
        progress: Optional[str] = None,
        session_id: Optional[str] = None,
        character_id: Optional[str] = None,
    ) -> Optional[Relation]:
        """Update relation fields by business relation_id, optionally filtered by character_id
        
        Args:
            relation_id: Business relation_id of the relation
            name: New name to set (optional)
            knowledge: New knowledge to set (optional)
            progress: New progress to set (optional)
            session_id: Optional session_id for setting store context
            character_id: Optional character ID for filtering. If None, only updates relations where character_id IS NULL.
            
        Returns:
            Updated Relation if successful, None otherwise
            
        Example:
            Memory.update_relation_by_relation_id("relation-123", name="Alice", progress="Close friend", session_id="session_id")
            Memory.update_relation_by_relation_id("relation-123", name="Alice", session_id="session_id", character_id="char-123")
        """
        try:
            relation_store = RelationStore()
            if session_id:
                relation_store.set_session(session_id)
            return relation_store.update_relation(relation_id, name, knowledge, progress, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to update relation: {e}")
            return None

    @staticmethod
    def delete_relation_by_relation_id(relation_id: str, session_id: Optional[str] = None, character_id: Optional[str] = None) -> bool:
        """Delete a relation by business relation_id, optionally filtered by character_id
        
        Args:
            relation_id: Business relation_id of the relation
            session_id: Optional session_id for setting store context
            character_id: Optional character ID for filtering. If None, only deletes relations where character_id IS NULL.
            
        Returns:
            True if deletion was successful, False otherwise
            
        Example:
            Memory.delete_relation_by_relation_id("relation-123", "session_id")
            Memory.delete_relation_by_relation_id("relation-123", "session_id", character_id="char-123")
        """
        try:
            relation_store = RelationStore()
            if session_id:
                relation_store.set_session(session_id)
            return relation_store.delete_relation(relation_id, session_id, character_id=character_id)
        except Exception as e:
            logger.error(f"Failed to delete relation: {e}")
            return False

    @staticmethod
    def search_relations_by_keyword(
        session_id: str,
        keyword: str,
        limit: int = 50,
        character_id: Optional[str] = None,
    ) -> List[Relation]:
        """Search relations by keyword using Meilisearch
        
        Args:
            session_id: Session ID for querying relations
            keyword: Keyword to search for
            limit: Maximum number of results to return (default: 50)
            character_id: Optional character ID for filtering. If None, returns relations where character_id IS NULL.
            
        Returns:
            List of Relation objects
            
        Example:
            Memory.search_relations_by_keyword('session_id', 'Alice')
            Memory.search_relations_by_keyword('session_id', 'Alice', character_id='char-123')
        """
        if not session_id:
            logger.warning("session_id is required for relation search")
            return []
        
        try:
            relation_store = RelationStore()
            relation_store.set_session(session_id)
            results = relation_store.search_relations(keyword, session_id, character_id=character_id)
            # Apply limit
            return results[:limit] if limit > 0 else results
        except Exception as e:
            logger.error(f"Failed to search relations by keyword: {e}")
            return []

    # ========== Dialogue Turn Counting ==========
    
    @staticmethod
    def count_dialogue_messages(
        session_id: str,
        speaker: str,
        categories: Optional[List[int]] = None
    ) -> int:
        """Count dialogue messages by speaker and categories
        
        This is an efficient COUNT query for calculating dialogue turns.
        Used to determine when to trigger periodic tasks (e.g., WriterAgent every 10 turns).
        
        Args:
            session_id: Session ID for querying messages
            speaker: Speaker name to filter by (e.g., character name)
            categories: List of category filters (default: [1, 2] for TELEGRAM and SPEAK_IN_PERSON)
            
        Returns:
            Count of matching messages
            
        Example:
            # Count how many times "Seraphina" has spoken via TELEGRAM or SPEAK_IN_PERSON
            count = Memory.count_dialogue_messages('session_id', 'Seraphina')
            
            # Trigger WriterAgent every 10 dialogue turns
            if count > 0 and count % 10 == 0:
                # Run WriterAgent
                pass
        """
        if not session_id:
            logger.warning("session_id is required for dialogue count")
            return 0
        
        try:
            from app.storage.sqlite_repository import SQLiteMessageRepository
            repo = SQLiteMessageRepository()
            return repo.count_dialogue_messages(session_id, speaker, categories)
        except Exception as e:
            logger.error(f"Failed to count dialogue messages: {e}")
            return 0