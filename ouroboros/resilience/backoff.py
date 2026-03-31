"""Exponential backoff with jitter for retry strategies.

AWS-recommended decorrelated jitter prevents thundering herd.
Supports: exponential, decorrelated jitter, full jitter.

Following Principle 5 (Minimalism): under 150 lines.
"""

from __future__ import annotations

import logging
import random
from enum import Enum
from typing import Optional

log = logging.getLogger(__name__)


class BackoffStrategy(Enum):
    """Backoff strategy types."""

    EXPONENTIAL = "exponential"
    FULL_JITTER = "full_jitter"
    DECORRELATED_JITTER = "decorrelated_jitter"


def backoff_with_jitter(
    attempt: int,
    base_ms: float = 100.0,
    cap_ms: float = 30000.0,
    strategy: BackoffStrategy = BackoffStrategy.DECORRELATED_JITTER,
    prev_delay_ms: Optional[float] = None,
) -> float:
    """Calculate backoff delay with jitter.

    AWS-recommended decorrelated jitter produces better throughput
    than full jitter in most load scenarios.

    Args:
        attempt: Current retry attempt (0-indexed)
        base_ms: Base delay in milliseconds
        cap_ms: Maximum delay cap in milliseconds
        strategy: Backoff strategy to use
        prev_delay_ms: Previous delay (for decorrelated jitter)

    Returns:
        Delay in seconds
    """
    if strategy == BackoffStrategy.EXPONENTIAL:
        delay = min(cap_ms, base_ms * (2**attempt))
    elif strategy == BackoffStrategy.FULL_JITTER:
        delay = random.uniform(0, min(cap_ms, base_ms * (2**attempt)))
    else:  # DECORRELATED_JITTER
        if prev_delay_ms is None:
            delay = random.uniform(base_ms, min(cap_ms, base_ms * (2**attempt)))
        else:
            delay = min(cap_ms, random.uniform(base_ms, prev_delay_ms * 3))

    return delay / 1000.0


class RetryPolicy:
    """Configurable retry policy with backoff.

    Usage:
        policy = RetryPolicy(max_attempts=5, base_ms=100, cap_ms=30000)

        for attempt in range(policy.max_attempts):
            try:
                return await operation()
            except Exception as e:
                delay = policy.get_delay(attempt)
                log.warning(f"Attempt {attempt+1} failed, retrying in {delay:.2f}s")
                await asyncio.sleep(delay)
    """

    def __init__(
        self,
        max_attempts: int = 5,
        base_ms: float = 100.0,
        cap_ms: float = 30000.0,
        strategy: BackoffStrategy = BackoffStrategy.DECORRELATED_JITTER,
    ) -> None:
        self.max_attempts = max_attempts
        self.base_ms = base_ms
        self.cap_ms = cap_ms
        self.strategy = strategy
        self._prev_delay_ms: Optional[float] = None

    def get_delay(self, attempt: int) -> float:
        """Get delay for current attempt."""
        delay = backoff_with_jitter(
            attempt=attempt,
            base_ms=self.base_ms,
            cap_ms=self.cap_ms,
            strategy=self.strategy,
            prev_delay_ms=self._prev_delay_ms,
        )
        self._prev_delay_ms = delay * 1000.0
        return delay

    def should_retry(self, attempt: int) -> bool:
        """Check if should retry based on attempt count."""
        return attempt < self.max_attempts

    def reset(self) -> None:
        """Reset policy state."""
        self._prev_delay_ms = None
