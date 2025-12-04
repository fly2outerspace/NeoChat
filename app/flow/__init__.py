"""Flow framework for multi-agent orchestration

This module provides flow implementations for orchestrating multiple agents
and other Runnables. All flows inherit from BaseFlow, which extends the
unified Runnable abstraction.

Available Flows:
- SequentialFlow: Executes nodes one by one with conditional routing
- ParallelFlow: Executes nodes concurrently with background task support
- CharacterFlow: Pre-configured flow for character-based chat (StrategyAgent → Speak/Telegram)
- SeraFlow: Simple sequential flow (UserAgent → Character)
- LinaFlow: Full featured flow (UserAgent → Parallel(WriterAgent + CharacterFlow))

Flow Types:
- BaseFlow: Abstract base class for all flows (extends Runnable)
- FlowNode: Node definition for flow composition
"""

from app.flow.base import BaseFlow, FlowNode
from app.flow.sequential_flow import SequentialFlow
from app.flow.parallel_flow import ParallelFlow
from app.flow.character_flow import CharacterFlow
from app.flow.sera_flow import SeraFlow
from app.flow.lina_flow import LinaFlow

__all__ = [
    # Base classes
    "BaseFlow",
    "FlowNode",
    # Flow implementations
    "SequentialFlow",
    "ParallelFlow",
    "CharacterFlow",
    "SeraFlow",
    "LinaFlow",
]
