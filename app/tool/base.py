from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class BaseTool(ABC, BaseModel):
    name: str
    description: str
    parameters: Optional[dict] = None
    character_id: Optional[str] = Field(default=None, description="Character ID for filtering data by character")

    class Config:
        arbitrary_types_allowed = True

    async def __call__(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""
        return await self.execute(**kwargs)

    @abstractmethod
    async def execute(self, **kwargs) -> Any:
        """Execute the tool with given parameters."""

    def to_param(self) -> Dict:
        """Convert tool to function call format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


class ToolResult(BaseModel):
    """Represents the result of a tool execution."""

    content: str = Field(default="", description="Text content for display and general use")
    args: Dict[str, Any] = Field(default_factory=dict, description="Structured data fields (e.g., decision, strategy)")
    error: Optional[str] = Field(default=None, description="Error message if execution failed")
    system: Optional[str] = Field(default=None, description="System-level information")

    class Config:
        arbitrary_types_allowed = True

    def __bool__(self):
        return bool(self.content) or bool(self.args) or bool(self.error) or bool(self.system)

    def __add__(self, other: "ToolResult"):
        def combine_fields(
            field: Optional[str], other_field: Optional[str], concatenate: bool = True
        ):
            if field and other_field:
                if concatenate:
                    return field + other_field
                raise ValueError("Cannot combine tool results")
            return field or other_field

        # Merge args dictionaries
        merged_args = {**self.args, **other.args}

        return ToolResult(
            content=combine_fields(self.content, other.content),
            args=merged_args,
            error=combine_fields(self.error, other.error),
            system=combine_fields(self.system, other.system),
        )

    def __str__(self):
        """Return text representation for display"""
        if self.error:
            return f"Error: {self.error}"
        return self.content or ""

    def replace(self, **kwargs):
        """Returns a new ToolResult with the given fields replaced."""
        # return self.copy(update=kwargs)
        return type(self)(**{**self.dict(), **kwargs})
    
    @classmethod
    def from_output(cls, output: Any, **kwargs) -> "ToolResult":
        """Create ToolResult from legacy output field (for backward compatibility)"""
        if isinstance(output, str):
            return cls(content=output, **kwargs)
        elif output is None:
            return cls(**kwargs)
        else:
            # Convert other types to string
            return cls(content=str(output), **kwargs)


class CLIResult(ToolResult):
    """A ToolResult that can be rendered as a CLI output."""


class ToolFailure(ToolResult):
    """A ToolResult that represents a failure."""


class AgentAwareTool:
    agent: Optional = None
