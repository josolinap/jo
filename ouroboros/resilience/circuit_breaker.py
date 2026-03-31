"""Circuit breaker pattern for fault tolerance.

Prevents cascading failures by stopping requests to failing dependencies.
States: CLOSED (normal) -> OPEN (blocked) -> HALF_OPEN (testing) -> CLOSED.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Optional

log = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    """Raised when circuit is open and requests are blocked."""

    pass


@dataclass
class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures.

    Prevents repeated calls to failing dependencies by tracking failure
    counts and blocking requests when threshold is exceeded.

    Usage:
        breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=30)

        async def call_api():
            return await breaker.call(make_api_request, *args)

        # Or use the context manager:
        async with breaker:
            await make_api_request()
    """

    name: str = "default"
    failure_threshold: int = 5
    timeout_seconds: float = 30.0
    success_threshold: int = 2
    state: CircuitState = field(default_factory=lambda: CircuitState.CLOSED)
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[float] = None
    last_error: Optional[str] = None

    def __post_init__(self) -> None:
        """Initialize circuit breaker."""
        self._lock = None  # Would be threading.Lock in threaded context

    def is_open(self) -> bool:
        """Check if circuit is currently open (blocking requests)."""
        if self.state == CircuitState.CLOSED:
            return False

        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed for half-open transition
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout_seconds:
                self.state = CircuitState.HALF_OPEN
                log.info(f"Circuit '{self.name}' transitioning to HALF_OPEN for testing")
                return False
            return True

        # HALF_OPEN: allow one request through
        return False

    def record_success(self) -> None:
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                log.info(f"Circuit '{self.name}' CLOSED - dependency recovered")
        else:
            self.failure_count = max(0, self.failure_count - 1)

    def record_failure(self, error: str = "") -> None:
        """Record a failed call."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.last_error = error
        self.success_count = 0

        if self.state == CircuitState.HALF_OPEN:
            # Failure during testing -> back to OPEN
            self.state = CircuitState.OPEN
            log.warning(f"Circuit '{self.name}' back to OPEN - test failed: {error}")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log.warning(
                f"Circuit '{self.name}' OPEN - {self.failure_count} failures, "
                f"blocking requests for {self.timeout_seconds}s"
            )

    async def call(self, fn: Callable, *args: Any, **kwargs: Any) -> Any:
        """Execute function through circuit breaker."""
        if self.is_open():
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN - "
                f"blocked after {self.failure_count} failures. "
                f"Last error: {self.last_error}"
            )

        try:
            result = await fn(*args, **kwargs) if callable(fn) and hasattr(fn, "__await__") else fn(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            self.record_failure(str(e))
            raise

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_error": self.last_error,
            "is_blocking": self.is_open(),
        }

    def reset(self) -> None:
        """Manually reset circuit to CLOSED state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_error = None
        log.info(f"Circuit '{self.name}' manually reset to CLOSED")


class CircuitBreakerRegistry:
    """Registry of circuit breakers for different dependencies."""

    def __init__(self) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}

    def get_or_create(
        self,
        name: str,
        failure_threshold: int = 5,
        timeout_seconds: float = 30.0,
    ) -> CircuitBreaker:
        """Get existing breaker or create new one."""
        if name not in self._breakers:
            self._breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                timeout_seconds=timeout_seconds,
            )
        return self._breakers[name]

    def get_all_status(self) -> list[dict]:
        """Get status of all circuit breakers."""
        return [b.get_status() for b in self._breakers.values()]

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()


# Global registry
_registry = CircuitBreakerRegistry()


def get_circuit(name: str, **kwargs: Any) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    return _registry.get_or_create(name, **kwargs)


def get_all_circuits_status() -> list[dict]:
    """Get status of all registered circuit breakers."""
    return _registry.get_all_status()
