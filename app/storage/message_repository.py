"""Repository pattern for message storage - abstract base class"""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from app.schema import Message


class MessageRepository(ABC):
    """Abstract repository for message storage operations"""
    
    @abstractmethod
    def insert_message(
        self,
        session_id: str,
        role: str,
        content: Optional[str],
        tool_calls: Optional[str],
        tool_name: Optional[str],
        speaker: Optional[str],
        tool_call_id: Optional[str],
        created_at: Optional[str] = None,
        category: int = 0,
        character_id_list: Optional[List[str]] = None,
    ) -> int:
        """Insert a message into database
        
        Args:
            session_id: Session ID
            role: Message role
            content: Message content
            tool_calls: Serialized tool calls JSON string
            tool_name: Optional tool/function name (for tool messages)
            speaker: Optional speaker/agent name
            tool_call_id: Optional tool call ID
            created_at: Optional timestamp (ISO format: 'YYYY-MM-DD HH:MM:SS'). 
                       If None, uses current time.
            category: Message category identifier (default: 0)
            character_id_list: Optional list of character IDs to associate with this message
        
        Returns:
            The ID of the inserted message
        """
        pass
    
    @abstractmethod
    def get_messages_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all messages for a session, returns raw dicts
        
        Note: The returned dicts may include a 'character_ids' key with a list of associated character IDs
        """
        pass
    
    @abstractmethod
    def delete_messages_by_session(self, session_id: str) -> None:
        """Delete all messages for a session"""
        pass
    
    @abstractmethod
    def get_messages_around_time(
        self,
        session_id: str,
        time_point: str,
        hours: float = 1.0,
        max_messages: int = 100,
        categories: Optional[List[int]] = None,
        character_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get messages around a specific time point
        
        Algorithm: Scan forward and backward from time_point within the time range,
        then merge and sort by time distance, return the closest messages.
        
        Args:
            session_id: Session ID
            time_point: Time point string in format 'YYYY-MM-DD HH:MM:SS'
            hours: Time range in hours before and after time_point (default: 1.0)
            max_messages_per_direction: Max messages to scan in each direction (default: 100)
            category: Optional category filter. If None, returns all categories.
            
        Returns:
            List of message dicts sorted by created_at, closest to time_point first
        """
        pass
    
    @abstractmethod
    def get_messages_in_range(
        self,
        session_id: str,
        start_time: str,
        end_time: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Get messages within a specific time range
        
        Args:
            session_id: Session ID
            start_time: Start time string in format 'YYYY-MM-DD HH:MM:SS'
            end_time: End time string in format 'YYYY-MM-DD HH:MM:SS'
            max_results: Maximum number of messages to return (default: 100)
            category: Optional category filter. If None, returns all categories.
            
        Returns:
            List of message dicts within the time range, sorted by created_at
        """
        pass
    
    @abstractmethod
    def get_messages_by_date(
        self,
        session_id: str,
        date: str,
        max_results: int = 100,
        categories: Optional[List[int]] = None
    ) -> List[Dict[str, Any]]:
        """Get all messages on a specific date
        
        Args:
            session_id: Session ID
            date: Date string in format 'YYYY-MM-DD'
            max_results: Maximum number of messages to return (default: 100)
            category: Optional category filter. If None, returns all categories.
            
        Returns:
            List of message dicts on the specified date, sorted by created_at
        """
        pass
    
    @abstractmethod
    def count_dialogue_messages(
        self,
        session_id: str,
        speaker: str,
        categories: Optional[List[int]] = None
    ) -> int:
        """Count dialogue messages by speaker and categories
        
        This is an efficient COUNT query for calculating dialogue turns.
        
        Args:
            session_id: Session ID
            speaker: Speaker name to filter by
            categories: List of category filters (default: [1, 2] for TELEGRAM and SPEAK_IN_PERSON)
            
        Returns:
            Count of matching messages
        """
        pass

