"""Context window manager with progressive compression.

Three thresholds: WARNING (70%), CRITICAL (85%), HARD LIMIT (95%).
Progressive compression prevents context overflow.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

from ouroboros.utils import estimate_tokens

log = logging.getLogger(__name__)


@dataclass
class ContextWindowManager:
    """Manages context window with progressive compression.

    Tracks token usage and triggers compression at configurable thresholds
    to prevent context overflow while preserving important information.

    Usage:
        manager = ContextWindowManager(token_limit=120000)
        messages, status = manager.check_and_compress(messages)
    """

    token_limit: int = 120000
    warning_threshold: float = 0.70
    critical_threshold: float = 0.85
    hard_limit: float = 0.95
    _last_usage: float = 0.0
    _compression_count: int = 0

    def estimate_usage(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate total tokens in messages."""
        total = 0
        for msg in messages:
            content = msg.get("content", "")
            if isinstance(content, str):
                total += estimate_tokens(content)
            elif isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        total += estimate_tokens(str(block.get("text", "")))
            total += 6  # Message overhead
        return total

    def get_usage_ratio(self, messages: List[Dict[str, Any]]) -> float:
        """Get current token usage as ratio of limit."""
        usage = self.estimate_usage(messages)
        self._last_usage = usage / self.token_limit
        return self._last_usage

    def check_and_compress(
        self,
        messages: List[Dict[str, Any]],
        compact_fn: Optional[Callable] = None,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Check context usage and compress if needed.

        Args:
            messages: Current message list
            compact_fn: Function to compact old messages (compact_tool_history)

        Returns:
            Tuple of (messages, status_dict)
        """
        usage_ratio = self.get_usage_ratio(messages)
        status = {
            "usage_ratio": round(usage_ratio, 3),
            "token_estimate": int(usage_ratio * self.token_limit),
            "token_limit": self.token_limit,
            "compressed": False,
            "level": "normal",
        }

        if usage_ratio >= self.hard_limit:
            status["level"] = "hard_limit"
            log.warning(f"Context at HARD LIMIT: {usage_ratio:.1%}")
            messages = self._hard_compress(messages, compact_fn)
            status["compressed"] = True

        elif usage_ratio >= self.critical_threshold:
            status["level"] = "critical"
            log.info(f"Context at CRITICAL: {usage_ratio:.1%}")
            messages = self._critical_compress(messages, compact_fn)
            status["compressed"] = True

        elif usage_ratio >= self.warning_threshold:
            status["level"] = "warning"
            log.debug(f"Context at WARNING: {usage_ratio:.1%}")
            messages = self._warning_compress(messages, compact_fn)
            status["compressed"] = True

        if status["compressed"]:
            self._compression_count += 1
            new_ratio = self.get_usage_ratio(messages)
            status["usage_ratio_after"] = round(new_ratio, 3)

        return messages, status

    def _warning_compress(
        self,
        messages: List[Dict[str, Any]],
        compact_fn: Optional[Callable],
    ) -> List[Dict[str, Any]]:
        """Light compression: compact old tool results."""
        if compact_fn:
            return compact_fn(messages, keep_recent=6)
        return messages

    def _critical_compress(
        self,
        messages: List[Dict[str, Any]],
        compact_fn: Optional[Callable],
    ) -> List[Dict[str, Any]]:
        """Medium compression: aggressive compaction."""
        if compact_fn:
            return compact_fn(messages, keep_recent=4)
        return messages

    def _hard_compress(
        self,
        messages: List[Dict[str, Any]],
        compact_fn: Optional[Callable],
    ) -> List[Dict[str, Any]]:
        """Hard compression: keep only system + recent."""
        # Keep system messages and last 2 rounds
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        # Keep last 10 messages (approx 2 rounds)
        recent = other_msgs[-10:] if len(other_msgs) > 10 else other_msgs

        return system_msgs + recent

    def get_status(self) -> Dict[str, Any]:
        """Get current manager status."""
        return {
            "token_limit": self.token_limit,
            "last_usage_ratio": round(self._last_usage, 3),
            "compression_count": self._compression_count,
            "thresholds": {
                "warning": self.warning_threshold,
                "critical": self.critical_threshold,
                "hard_limit": self.hard_limit,
            },
        }
