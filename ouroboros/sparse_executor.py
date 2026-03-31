"""Sparse executor for skipping low-value tool calls.

Inspired by TurboQuant+ Sparse V: skip computations that
contribute negligibly to output. Reduces token usage and cost.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import hashlib
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


@dataclass
class ToolStats:
    """Statistics for a tool."""

    call_count: int = 0
    success_count: int = 0
    total_cost: float = 0.0
    avg_duration: float = 0.0
    last_called: float = 0.0


@dataclass
class SparseExecutor:
    """Skip low-value tool calls to optimize execution.

    Tracks tool usage patterns and skips:
    - Duplicate calls (same tool + args)
    - Low-success-rate tools
    - Optional tools under time pressure
    - Recently failed tools

    Usage:
        executor = SparseExecutor()

        for call in pending_calls:
            if executor.should_execute(call, context):
                result = await execute(call)
                executor.record(call, result)
            else:
                executor.skip(call, "low_value")
    """

    history_window: int = 100
    min_success_rate: float = 0.3
    duplicate_window_seconds: float = 300.0
    cooldown_after_fail: float = 60.0
    _recent_calls: deque = field(default_factory=lambda: deque(maxlen=100))
    _tool_stats: Dict[str, ToolStats] = field(default_factory=lambda: defaultdict(ToolStats))
    _recent_hashes: Dict[str, float] = field(default_factory=dict)
    _optional_tools: Set[str] = field(default_factory=set)
    _skip_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def __post_init__(self) -> None:
        """Initialize with correct maxlen."""
        self._recent_calls = deque(maxlen=self.history_window)

    def mark_optional(self, tool_name: str) -> None:
        """Mark a tool as optional (skippable under pressure)."""
        self._optional_tools.add(tool_name)

    def should_execute(
        self,
        tool_name: str,
        args: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, str]:
        """Check if a tool call should be executed.

        Args:
            tool_name: Name of the tool
            args: Tool arguments
            context: Execution context (time_pressure, budget_remaining, etc.)

        Returns:
            Tuple of (should_execute, reason)
        """
        if context is None:
            context = {}

        # Check for duplicate call
        call_hash = self._hash_call(tool_name, args)
        if call_hash in self._recent_hashes:
            last_time = self._recent_hashes[call_hash]
            if time.time() - last_time < self.duplicate_window_seconds:
                self._skip_counts[tool_name] += 1
                return False, "duplicate_call"

        # Check tool success rate
        stats = self._tool_stats.get(tool_name)
        if stats and stats.call_count >= 5:
            success_rate = stats.success_count / stats.call_count
            if success_rate < self.min_success_rate:
                self._skip_counts[tool_name] += 1
                return False, f"low_success_rate ({success_rate:.0%})"

        # Check cooldown after recent failure
        if stats and stats.last_called > 0:
            time_since_last = time.time() - stats.last_called
            if time_since_last < self.cooldown_after_fail:
                # Check if last call failed
                if stats.success_count < stats.call_count:
                    self._skip_counts[tool_name] += 1
                    return False, "cooldown_after_fail"

        # Check optional tools under time pressure
        time_pressure = context.get("time_pressure", 0.0)
        if time_pressure > 0.8 and tool_name in self._optional_tools:
            self._skip_counts[tool_name] += 1
            return False, "optional_under_pressure"

        # Check budget
        budget_remaining = context.get("budget_remaining", float("inf"))
        if budget_remaining < 1.0 and tool_name in self._optional_tools:
            self._skip_counts[tool_name] += 1
            return False, "budget_constrained"

        return True, "ok"

    def record(
        self,
        tool_name: str,
        args: Dict[str, Any],
        success: bool,
        duration: float = 0.0,
        cost: float = 0.0,
    ) -> None:
        """Record tool execution result."""
        call_hash = self._hash_call(tool_name, args)
        self._recent_hashes[call_hash] = time.time()

        stats = self._tool_stats[tool_name]
        stats.call_count += 1
        if success:
            stats.success_count += 1
        stats.total_cost += cost
        stats.avg_duration = (stats.avg_duration * (stats.call_count - 1) + duration) / stats.call_count
        stats.last_called = time.time()

        self._recent_calls.append(
            {
                "tool": tool_name,
                "success": success,
                "time": time.time(),
            }
        )

    def skip(self, tool_name: str, reason: str) -> None:
        """Record that a tool call was skipped."""
        log.debug(f"Skipped {tool_name}: {reason}")
        self._skip_counts[tool_name] += 1

    def _hash_call(self, tool_name: str, args: Dict[str, Any]) -> str:
        """Create hash of tool call for deduplication."""
        import json

        args_str = json.dumps(args, sort_keys=True, default=str)
        return hashlib.md5(f"{tool_name}:{args_str}".encode()).hexdigest()[:12]

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics."""
        total_calls = sum(s.call_count for s in self._tool_stats.values())
        total_success = sum(s.success_count for s in self._tool_stats.values())
        total_skipped = sum(self._skip_counts.values())

        return {
            "total_calls": total_calls,
            "total_success": total_success,
            "total_skipped": total_skipped,
            "overall_success_rate": total_success / max(1, total_calls),
            "skip_rate": total_skipped / max(1, total_calls + total_skipped),
            "tools": {
                name: {
                    "calls": stats.call_count,
                    "success_rate": stats.success_count / max(1, stats.call_count),
                    "avg_duration": round(stats.avg_duration, 3),
                    "total_cost": round(stats.total_cost, 4),
                }
                for name, stats in sorted(
                    self._tool_stats.items(),
                    key=lambda x: -x[1].call_count,
                )[:10]
            },
            "most_skipped": sorted(
                self._skip_counts.items(),
                key=lambda x: -x[1],
            )[:5],
        }

    def reset(self) -> None:
        """Reset all statistics."""
        self._recent_calls.clear()
        self._tool_stats.clear()
        self._recent_hashes.clear()
        self._skip_counts.clear()


# Global executor instance
_global_executor = SparseExecutor()


def get_executor() -> SparseExecutor:
    """Get the global sparse executor."""
    return _global_executor
