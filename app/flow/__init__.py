"""Flow framework for multi-agent orchestration

This module provides flow implementations for orchestrating multiple agents
and other Runnables. All flows inherit from BaseFlow, which extends the
unified Runnable abstraction.

Available Flows:
- SequentialFlow: Executes nodes one by one with conditional routing
- ParallelFlow: Executes nodes concurrently with background task support
- CharacterFlow: Pre-configured flow for character-based chat

Flow Types:
- BaseFlow: Abstract base class for all flows (extends Runnable)
- FlowNode: Node definition for flow composition
"""

from app.flow.base import BaseFlow, FlowNode
from app.flow.sequential_flow import SequentialFlow
from app.flow.parallel_flow import ParallelFlow
from app.flow.character_flow import CharacterFlow

__all__ = [
    # Base classes
    "BaseFlow",
    "FlowNode",
    # Flow implementations
    "SequentialFlow",
    "ParallelFlow",
    "CharacterFlow",
]
