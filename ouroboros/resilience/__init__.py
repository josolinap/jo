"""Resilience patterns for stable agent operation.

Implements: circuit breakers, stuck detection, backoff strategies,
context management, supervision, checkpointing, graceful degradation.

Following Principle 5 (Minimalism): each module under 300 lines.
"""

from __future__ import annotations

from ouroboros.resilience.circuit_breaker import CircuitBreaker, CircuitState
from ouroboros.resilience.stuck_detector import StuckDetector, FailureType
from ouroboros.resilience.backoff import backoff_with_jitter, BackoffStrategy
from ouroboros.resilience.context_manager import ContextWindowManager
from ouroboros.resilience.supervisor import AgentSupervisor, RestartStrategy
from ouroboros.resilience.checkpoint import HybridCheckpointer
from ouroboros.resilience.degradation import GracefulDegradation, DependencyClass

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "StuckDetector",
    "FailureType",
    "backoff_with_jitter",
    "BackoffStrategy",
    "ContextWindowManager",
    "AgentSupervisor",
    "RestartStrategy",
    "HybridCheckpointer",
    "GracefulDegradation",
    "DependencyClass",
]
