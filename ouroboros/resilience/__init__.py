"""Resilience patterns for stable agent operation.

Implements: circuit breakers, stuck detection, backoff strategies,
context management, supervision, checkpointing, graceful degradation.

Following Principle 5 (Minimalism): each module under 300 lines.
"""

from __future__ import annotations

from ouroboros.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    CircuitBreakerRegistry,
    get_circuit,
    get_all_circuits_status,
)
from ouroboros.resilience.stuck_detector import StuckDetector, FailureType
from ouroboros.resilience.backoff import backoff_with_jitter, BackoffStrategy, RetryPolicy
from ouroboros.resilience.context_manager import ContextWindowManager
from ouroboros.resilience.supervisor import AgentSupervisor, RestartStrategy, ChildType, SupervisedChild
from ouroboros.resilience.checkpoint import HybridCheckpointer
from ouroboros.resilience.degradation import (
    GracefulDegradation,
    DependencyClass,
    DependencyUnavailableError,
    create_default_degradation,
)

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitOpenError",
    "CircuitBreakerRegistry",
    "get_circuit",
    "get_all_circuits_status",
    "StuckDetector",
    "FailureType",
    "backoff_with_jitter",
    "BackoffStrategy",
    "RetryPolicy",
    "ContextWindowManager",
    "AgentSupervisor",
    "RestartStrategy",
    "ChildType",
    "SupervisedChild",
    "HybridCheckpointer",
    "GracefulDegradation",
    "DependencyClass",
    "DependencyUnavailableError",
    "create_default_degradation",
]
