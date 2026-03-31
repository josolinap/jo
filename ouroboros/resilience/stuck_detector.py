"""Stuck detection for AI agent loops.

Detects three failure patterns:
- Repeater: same action N times without progress
- Wanderer: different actions but no progress
- Looper: cycling between 2-3 actions without resolution

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import hashlib
import logging
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class FailureType(Enum):
    """Types of stuck patterns."""

    NONE = "none"
    REPEATER = "repeater"
    WANDERER = "wanderer"
    LOOPER = "looper"
    NO_PROGRESS = "no_progress"


@dataclass
class StuckDetector:
    """Detects when agent is alive but not advancing.

    Monitors recent actions and progress metrics to identify
    stuck patterns before they become critical.

    Usage:
        detector = StuckDetector(window_size=10)

        for action, progress in agent_loop:
            failure = detector.detect(action, progress)
            if failure == FailureType.REPEATER:
                # Inject goal reassessment prompt
                pass
    """

    window_size: int = 10
    recent_actions: deque = field(default_factory=lambda: deque(maxlen=10))
    progress_history: deque = field(default_factory=lambda: deque(maxlen=10))
    action_counts: Dict[str, int] = field(default_factory=dict)
    _last_progress: float = 0.0
    _stagnant_rounds: int = 0

    def __post_init__(self) -> None:
        """Initialize deques with correct maxlen."""
        self.recent_actions = deque(maxlen=self.window_size)
        self.progress_history = deque(maxlen=self.window_size)

    def _hash_action(self, action: str) -> str:
        """Create stable hash of action for comparison."""
        return hashlib.md5(action.encode()).hexdigest()[:8]

    def detect(self, action: str, progress: float) -> FailureType:
        """Detect stuck patterns from current action and progress.

        Args:
            action: Description of current action/tool call
            progress: Numeric progress metric (0-1, higher is better)

        Returns:
            FailureType indicating the pattern detected, or NONE if healthy
        """
        action_hash = self._hash_action(action)

        self.recent_actions.append(action_hash)
        self.progress_history.append(progress)

        # Track action frequency
        self.action_counts[action_hash] = self.action_counts.get(action_hash, 0) + 1

        # Check progress stagnation
        if progress == self._last_progress:
            self._stagnant_rounds += 1
        else:
            self._stagnant_rounds = 0
            self._last_progress = progress

        # Need minimum data to detect patterns
        if len(self.recent_actions) < 5:
            return FailureType.NONE

        # The Repeater: same action N times
        if self._is_repeater():
            log.warning("Stuck pattern detected: REPEATER - same action repeating")
            return FailureType.REPEATER

        # The Looper: cycling between 2-3 actions
        if self._is_looper():
            log.warning("Stuck pattern detected: LOOPER - cycling between actions")
            return FailureType.LOOPER

        # The Wanderer: many different actions but no progress
        if self._is_wanderer():
            log.warning("Stuck pattern detected: WANDERER - active but no progress")
            return FailureType.WANDERER

        # No progress for extended period
        if self._stagnant_rounds >= self.window_size:
            log.warning("Stuck pattern detected: NO_PROGRESS - progress metric flat")
            return FailureType.NO_PROGRESS

        return FailureType.NONE

    def _is_repeater(self) -> bool:
        """Check if agent is repeating the same action."""
        if len(self.recent_actions) < 5:
            return False
        # Last 5 actions are identical
        last_five = list(self.recent_actions)[-5:]
        return len(set(last_five)) == 1

    def _is_looper(self) -> bool:
        """Check if agent is cycling between 2-3 actions."""
        if len(self.recent_actions) < 6:
            return False
        unique_actions = set(self.recent_actions)
        # Cycling between exactly 2-3 actions
        if 2 <= len(unique_actions) <= 3:
            # Check for repetitive pattern
            last_six = list(self.recent_actions)[-6:]
            # Each action should appear at least twice
            return all(self.action_counts.get(a, 0) >= 2 for a in unique_actions)
        return False

    def _is_wanderer(self) -> bool:
        """Check if agent is active but making no progress."""
        if len(self.recent_actions) < 5 or len(self.progress_history) < 5:
            return False
        # Many different actions
        unique_actions = len(set(self.recent_actions))
        # But no progress change
        progress_range = max(self.progress_history) - min(self.progress_history)
        return unique_actions > 5 and progress_range == 0.0

    def get_diagnosis(self) -> Dict[str, Any]:
        """Get detailed diagnosis of current state."""
        unique_actions = len(set(self.recent_actions))
        progress_range = max(self.progress_history) - min(self.progress_history) if self.progress_history else 0.0

        return {
            "window_size": self.window_size,
            "actions_tracked": len(self.recent_actions),
            "unique_actions": unique_actions,
            "stagnant_rounds": self._stagnant_rounds,
            "progress_range": progress_range,
            "last_progress": self._last_progress,
            "action_distribution": dict(self.action_counts),
        }

    def reset(self) -> None:
        """Reset detector state."""
        self.recent_actions.clear()
        self.progress_history.clear()
        self.action_counts.clear()
        self._last_progress = 0.0
        self._stagnant_rounds = 0
