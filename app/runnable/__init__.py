"""Runnable framework - Unified abstraction for Agent and Flow

This module provides the core Runnable abstraction that unifies Agent and Flow
into a single composable interface. Any Runnable can:
1. Execute independently
2. Be composed with other Runnables using | and & operators
3. Be nested within other Runnables

Key Components:
- Runnable: Abstract base class for all executable units
- ExecutionContext: Shared context passed between Runnables
- ExecutionEvent: Unified event type for streaming execution (in app.schema)
- RunnableNode: Node definition for Flow composition

Composition Operators:
- |: Pipeline (sequential execution): agent1 | agent2
- &: Parallel (concurrent execution): agent1 & agent2

Example Usage:
    from app.runnable import Runnable, ExecutionContext
    from app.agent import MyAgent
    from app.flow import SequentialFlow, ParallelFlow
    
    # All of these are Runnables:
    agent = MyAgent(...)
    flow = SequentialFlow(...)
    parallel = ParallelFlow(...)
    
    # They can be composed:
    pipeline = agent1 | agent2  # Sequential
    parallel = agent1 & agent2  # Concurrent
    
    # And executed uniformly:
    async for event in runnable.run_stream(context):
        print(event)
"""

from app.runnable.base import Runnable
from app.runnable.context import ExecutionContext
from app.runnable.node import RunnableNode
from app.runnable.pipeline import Pipeline
from app.runnable.parallel import ParallelGroup

__all__ = [
    # Core abstraction
    "Runnable",
    # Context
    "ExecutionContext",
    # Node definition
    "RunnableNode",
    # Composition helpers
    "Pipeline",
    "ParallelGroup",
]
