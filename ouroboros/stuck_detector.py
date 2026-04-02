"""
Ouroboros — Sliding-Window Stuck Detector.

Detects repeated tool call patterns across multiple rounds using a sliding window.
Inspired by GSD-2's sliding-window stuck detection pattern.

Prevents infinite loops by identifying when the agent repeats the same actions.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ToolCallSignature:
    tool_name: str
    args_hash: str
    timestamp: str = ""


@dataclass
class StuckDetectionResult:
    is_stuck: bool
    confidence: float
    pattern_description: str
    repeated_calls: List[str] = field(default_factory=list)
    suggestion: str = ""


class SlidingWindowStuckDetector:
    """Detects stuck loops using a sliding window of tool call signatures."""

    def __init__(self, window_size: int = 10, repeat_threshold: int = 3):
        # Load configuration
        try:
            from ouroboros.config_manager import get_config

            config = get_config()
            stuck_config = config.get("stuck_detector", {})
            window_size = stuck_config.get("window_size", window_size)
            repeat_threshold = stuck_config.get("repeat_threshold", repeat_threshold)
        except Exception:
            pass

        self.window_size = window_size
        self.repeat_threshold = repeat_threshold
        self._window: Deque[ToolCallSignature] = deque(maxlen=window_size)
        self._round_signatures: Deque[str] = deque(maxlen=5)
        self._stats = {"total_checks": 0, "stuck_detected": 0, "patterns_found": 0}

    def _hash_args(self, args: Dict[str, Any]) -> str:
        try:
            serialized = json.dumps(args, sort_keys=True, default=str)
            return hashlib.md5(serialized.encode()).hexdigest()[:8]
        except Exception:
            return "unknown"

    def record_call(self, tool_name: str, args: Dict[str, Any]) -> None:
        sig = ToolCallSignature(
            tool_name=tool_name,
            args_hash=self._hash_args(args),
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._window.append(sig)

    def record_round(self, tool_calls: List[Tuple[str, Dict[str, Any]]]) -> None:
        if not tool_calls:
            return
        round_hash = hashlib.md5(
            json.dumps([(name, self._hash_args(args)) for name, args in tool_calls], sort_keys=True).encode()
        ).hexdigest()[:8]
        self._round_signatures.append(round_hash)

    def check(self) -> StuckDetectionResult:
        self._stats["total_checks"] += 1

        if len(self._window) < self.repeat_threshold:
            return StuckDetectionResult(is_stuck=False, confidence=0.0, pattern_description="Window too small")

        call_counts: Dict[str, int] = {}
        for sig in self._window:
            key = f"{sig.tool_name}:{sig.args_hash}"
            call_counts[key] = call_counts.get(key, 0) + 1

        repeated = {k: v for k, v in call_counts.items() if v >= self.repeat_threshold}

        if not repeated:
            if len(self._round_signatures) >= 3:
                unique_rounds = len(set(self._round_signatures))
                if unique_rounds <= 2:
                    self._stats["stuck_detected"] += 1
                    return StuckDetectionResult(
                        is_stuck=True,
                        confidence=0.7,
                        pattern_description=f"Repeating round pattern ({unique_rounds} unique rounds in last {len(self._round_signatures)})",
                        suggestion="The agent is repeating the same sequence of actions. Try a different approach or stop and reassess.",
                    )
            return StuckDetectionResult(is_stuck=False, confidence=0.0, pattern_description="No stuck pattern detected")

        self._stats["stuck_detected"] += 1
        self._stats["patterns_found"] += len(repeated)

        repeated_list = [f"{k} ({v}x)" for k, v in sorted(repeated.items(), key=lambda x: -x[1])]
        return StuckDetectionResult(
            is_stuck=True,
            confidence=min(1.0, len(repeated) * 0.3 + 0.3),
            pattern_description=f"{len(repeated)} tool calls repeated {self.repeat_threshold}+ times",
            repeated_calls=repeated_list[:5],
            suggestion="The agent is stuck in a loop. Consider: 1) Trying a different tool, 2) Reading more context first, 3) Breaking the task into smaller steps.",
        )

    def reset(self) -> None:
        self._window.clear()
        self._round_signatures.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "window_size": self.window_size,
            "current_window_size": len(self._window),
            "repeat_threshold": self.repeat_threshold,
        }

    def get_stuck_patterns(self) -> List[str]:
        """Get list of tools that are currently stuck in loops."""
        if len(self._window) < self.repeat_threshold:
            return []

        call_counts: Dict[str, int] = {}
        for sig in self._window:
            key = f"{sig.tool_name}:{sig.args_hash}"
            call_counts[key] = call_counts.get(key, 0) + 1

        return [k.split(":")[0] for k, v in call_counts.items() if v >= self.repeat_threshold]


_detector: Optional[SlidingWindowStuckDetector] = None


def get_detector() -> SlidingWindowStuckDetector:
    global _detector
    if _detector is None:
        _detector = SlidingWindowStuckDetector()
    return _detector


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def stuck_check(ctx) -> str:
        result = get_detector().check()
        if result.is_stuck:
            return f"⚠️ STUCK (confidence={result.confidence:.0%}): {result.pattern_description}\nSuggestion: {result.suggestion}"
        return f"✅ Not stuck: {result.pattern_description}"

    def stuck_stats(ctx) -> str:
        return json.dumps(get_detector().stats(), indent=2)

    def stuck_reset(ctx) -> str:
        get_detector().reset()
        return "Stuck detector window reset."

    return [
        ToolEntry(
            "stuck_check",
            {
                "name": "stuck_check",
                "description": "Check if the agent is stuck in a repeated tool call loop.",
                "parameters": {"type": "object", "properties": {}},
            },
            stuck_check,
        ),
        ToolEntry(
            "stuck_stats",
            {
                "name": "stuck_stats",
                "description": "Get stuck detector statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            stuck_stats,
        ),
        ToolEntry(
            "stuck_reset",
            {
                "name": "stuck_reset",
                "description": "Reset the stuck detector window after recovering from a stuck state.",
                "parameters": {"type": "object", "properties": {}},
            },
            stuck_reset,
        ),
    ]
