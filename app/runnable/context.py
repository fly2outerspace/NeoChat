"""Execution Context - Shared state passed between Runnables

The ExecutionContext carries all necessary information for execution,
including user input, session data, and shared state between nodes.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ExecutionContext(BaseModel):
    """Execution context passed between Runnables
    
    This is the shared state that flows through the execution graph.
    Each Runnable can read from and write to the context.
    
    The context follows an immutable pattern - modifications return
    a new context instance rather than mutating the original.
    """
    
    # Basic identification
    session_id: str = Field(..., description="Session identifier")
    
    # User input
    user_input: Optional[str] = Field(
        default=None,
        description="User input text"
    )
    
    # Shared data store (readable/writable by all nodes)
    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Shared data between nodes"
    )
    
    # Control flags
    stop_response_requested: bool = Field(
        default=False,
        description="Flag to indicate HTTP response should stop"
    )
    
    # Character visibility control
    character_id: Optional[str] = Field(
        default=None,
        description="Character ID for message filtering"
    )
    visible_for_characters: Optional[List[str]] = Field(
        default=None,
        description="List of character IDs that can see messages (None = all)"
    )
    
    class Config:
        arbitrary_types_allowed = True
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the data store
        
        Args:
            key: Key to look up
            default: Default value if key not found
            
        Returns:
            Value from data store or default
        """
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any) -> "ExecutionContext":
        """Set a value and return a new context (immutable pattern)
        
        Args:
            key: Key to set
            value: Value to store
            
        Returns:
            New ExecutionContext with updated data
        """
        new_data = {**self.data, key: value}
        return self.model_copy(update={"data": new_data})
    
    def merge(self, **kwargs) -> "ExecutionContext":
        """Merge multiple values into data and return new context
        
        Args:
            **kwargs: Key-value pairs to merge
            
        Returns:
            New ExecutionContext with merged data
        """
        if not kwargs:
            return self
        new_data = {**self.data, **kwargs}
        return self.model_copy(update={"data": new_data})
    
    def update_data(self, updates: Dict[str, Any]) -> "ExecutionContext":
        """Update data with a dictionary and return new context
        
        Args:
            updates: Dictionary of updates
            
        Returns:
            New ExecutionContext with updated data
        """
        if not updates:
            return self
        new_data = {**self.data, **updates}
        return self.model_copy(update={"data": new_data})
    
    def request_stop_response(self) -> "ExecutionContext":
        """Request that the HTTP response should stop
        
        Returns:
            New ExecutionContext with stop_response_requested=True
        """
        return self.model_copy(update={"stop_response_requested": True})
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for compatibility
        
        Returns:
            Dictionary representation of context
        """
        result = {
            "session_id": self.session_id,
            "user_input": self.user_input,
            **self.data,
        }
        if self.character_id:
            result["character_id"] = self.character_id
        if self.visible_for_characters:
            result["visible_for_characters"] = self.visible_for_characters
        return result
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExecutionContext":
        """Create context from dictionary
        
        Args:
            data: Dictionary with context data
            
        Returns:
            New ExecutionContext instance
        """
        # Extract known fields
        session_id = data.pop("session_id", "")
        user_input = data.pop("user_input", None)
        character_id = data.pop("character_id", None)
        visible_for_characters = data.pop("visible_for_characters", None)
        
        # Remaining fields (including input_mode) go into data
        return cls(
            session_id=session_id,
            user_input=user_input,
            character_id=character_id,
            visible_for_characters=visible_for_characters,
            data=data,
        )

