"""
Jo — Context Compaction System.

Inspired by Claude Code's 5-level compaction architecture.
Prevents context overflow while preserving critical information.

Five levels of defense:
1. MicroCompact: Time-based clearing of old tool results (>30 min old)
2. AutoCompact: Near-limit summarization (80% of context window)
3. Full Compact: Emergency compression + selective re-injection
4. Context Collapse: Summarizes conversation spans into key points
5. PTL Truncation: Drops oldest message groups (last resort)

Circuit breaker: MAX_CONSECUTIVE_FAILURES = 3
(Prevents 250K wasted API calls/day like Claude Code experienced)
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class CompactionLevel(Enum):
    MICRO = "micro"  # Level 1: Clear old tool results
    AUTO = "auto"  # Level 2: Summarize near limit
    FULL = "full"  # Level 3: Emergency compression
    COLLAPSE = "collapse"  # Level 4: Summarize conversation spans
    PTL_TRUNCATION = "ptl"  # Level 5: Drop oldest messages


@dataclass
class CompactionRecord:
    """Record of a compaction event."""

    level: str
    timestamp: str
    tokens_before: int
    tokens_after: int
    tokens_saved: int
    success: bool
    error: str = ""


class ContextCompaction:
    """Manages 5-level context compaction with circuit breaker."""

    # Claude Code learned this the hard way: 250K API calls/day wasted
    MAX_CONSECUTIVE_FAILURES = 3
    CONTEXT_WINDOW_LIMIT = 128_000  # Claude Sonnet 4 context window
    AUTO_COMPACT_THRESHOLD = 0.80  # 80% of context window
    MICRO_COMPACT_AGE_MINUTES = 30  # Clear tool results older than 30 min

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "compaction"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._consecutive_failures = 0
        self._total_compactions = 0
        self._history: List[CompactionRecord] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load compaction state."""
        state_file = self.state_dir / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self._consecutive_failures = data.get("consecutive_failures", 0)
                self._total_compactions = data.get("total_compactions", 0)
                self._history = [CompactionRecord(**r) for r in data.get("history", [])[-50:]]
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save compaction state."""
        state_file = self.state_dir / "state.json"
        state_file.write_text(
            json.dumps(
                {
                    "consecutive_failures": self._consecutive_failures,
                    "total_compactions": self._total_compactions,
                    "history": [
                        {
                            "level": r.level,
                            "timestamp": r.timestamp,
                            "tokens_before": r.tokens_before,
                            "tokens_after": r.tokens_after,
                            "tokens_saved": r.tokens_saved,
                            "success": r.success,
                            "error": r.error,
                        }
                        for r in self._history[-50:]
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def estimate_tokens(self, messages: List[Dict[str, Any]]) -> int:
        """Estimate token count for messages (rough approximation)."""
        # Rough estimate: 4 chars per token
        total_chars = sum(len(json.dumps(m)) for m in messages)
        return total_chars // 4

    def should_compact(self, messages: List[Dict[str, Any]]) -> Optional[CompactionLevel]:
        """Determine if compaction is needed and at what level."""
        # Circuit breaker check
        if self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES:
            log.warning("[Compaction] Circuit breaker tripped - %d consecutive failures", self._consecutive_failures)
            return None

        token_count = self.estimate_tokens(messages)
        usage_ratio = token_count / self.CONTEXT_WINDOW_LIMIT

        # Level 5: PTL Truncation - Emergency (>95%)
        if usage_ratio > 0.95:
            return CompactionLevel.PTL_TRUNCATION

        # Level 4: Context Collapse - Critical (>90%)
        if usage_ratio > 0.90:
            return CompactionLevel.COLLAPSE

        # Level 3: Full Compact - High (>85%)
        if usage_ratio > 0.85:
            return CompactionLevel.FULL

        # Level 2: AutoCompact - Near limit (>80%)
        if usage_ratio > self.AUTO_COMPACT_THRESHOLD:
            return CompactionLevel.AUTO

        # Level 1: MicroCompact - Check for old tool results
        has_old_results = self._has_old_tool_results(messages)
        if has_old_results:
            return CompactionLevel.MICRO

        return None

    def _has_old_tool_results(self, messages: List[Dict[str, Any]]) -> bool:
        """Check if there are tool results older than MICRO_COMPACT_AGE_MINUTES."""
        cutoff = time.time() - (self.MICRO_COMPACT_AGE_MINUTES * 60)
        for msg in messages:
            if msg.get("role") == "tool":
                # Check if message has timestamp metadata
                timestamp = msg.get("timestamp", 0)
                if timestamp > 0 and timestamp < cutoff:
                    return True
        return False

    def compact(self, messages: List[Dict[str, Any]], level: CompactionLevel) -> Tuple[List[Dict[str, Any]], bool]:
        """Execute compaction at specified level.

        Returns (compacted_messages, success).
        """
        tokens_before = self.estimate_tokens(messages)

        try:
            if level == CompactionLevel.MICRO:
                compacted = self._micro_compact(messages)
            elif level == CompactionLevel.AUTO:
                compacted = self._auto_compact(messages)
            elif level == CompactionLevel.FULL:
                compacted = self._full_compact(messages)
            elif level == CompactionLevel.COLLAPSE:
                compacted = self._context_collapse(messages)
            elif level == CompactionLevel.PTL_TRUNCATION:
                compacted = self._ptl_truncation(messages)
            else:
                compacted = messages

            tokens_after = self.estimate_tokens(compacted)
            success = tokens_after < tokens_before

            if success:
                self._consecutive_failures = 0
                self._total_compactions += 1
                log.info(
                    "[Compaction] %s: %d -> %d tokens (saved %d)",
                    level.value,
                    tokens_before,
                    tokens_after,
                    tokens_before - tokens_after,
                )
            else:
                self._consecutive_failures += 1
                log.warning(
                    "[Compaction] %s failed to reduce tokens: %d -> %d", level.value, tokens_before, tokens_after
                )

            record = CompactionRecord(
                level=level.value,
                timestamp=datetime.now().isoformat(),
                tokens_before=tokens_before,
                tokens_after=tokens_after,
                tokens_saved=tokens_before - tokens_after,
                success=success,
            )
            self._history.append(record)
            self._save_state()

            return compacted, success

        except Exception as e:
            self._consecutive_failures += 1
            log.error("[Compaction] %s failed: %s", level.value, e)

            record = CompactionRecord(
                level=level.value,
                timestamp=datetime.now().isoformat(),
                tokens_before=tokens_before,
                tokens_after=tokens_before,
                tokens_saved=0,
                success=False,
                error=str(e),
            )
            self._history.append(record)
            self._save_state()

            return messages, False

    def _micro_compact(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Level 1: Clear old tool results (>30 min old)."""
        cutoff = time.time() - (self.MICRO_COMPACT_AGE_MINUTES * 60)
        compacted = []
        for msg in messages:
            if msg.get("role") == "tool":
                timestamp = msg.get("timestamp", 0)
                if timestamp > 0 and timestamp < cutoff:
                    # Replace old tool result with summary placeholder
                    compacted.append(
                        {
                            "role": "tool",
                            "content": f"[Tool result compacted - was {len(msg.get('content', ''))} chars]",
                            "timestamp": timestamp,
                        }
                    )
                    continue
            compacted.append(msg)
        return compacted

    def _auto_compact(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Level 2: Summarize near-limit messages."""
        # Keep system prompt and last 5 messages intact
        # Summarize middle messages
        if len(messages) <= 7:
            return messages  # Not enough to compact

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        recent_messages = messages[-5:]

        # Summarize middle messages
        middle_messages = messages[1:-5] if system_msg else messages[:-5]
        summary = self._summarize_messages(middle_messages)

        compacted = []
        if system_msg:
            compacted.append(system_msg)
        compacted.append(
            {
                "role": "assistant",
                "content": f"[Context compacted: {len(middle_messages)} messages summarized]\n\n{summary}",
                "timestamp": time.time(),
            }
        )
        compacted.extend(recent_messages)
        return compacted

    def _full_compact(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Level 3: Emergency compression + selective re-injection."""
        if len(messages) <= 3:
            return messages

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        last_message = messages[-1]

        # Summarize everything except system and last message
        all_middle = messages[1:-1]
        summary = self._summarize_messages(all_middle, max_length=500)

        compacted = []
        if system_msg:
            compacted.append(system_msg)
        compacted.append(
            {
                "role": "assistant",
                "content": f"[FULL COMPACT: {len(all_middle)} messages compressed]\n\n{summary}",
                "timestamp": time.time(),
            }
        )
        compacted.append(last_message)
        return compacted

    def _context_collapse(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Level 4: Summarize conversation spans into key points."""
        if len(messages) <= 3:
            return messages

        system_msg = messages[0] if messages[0].get("role") == "system" else None
        last_two = messages[-2:]

        # Extract key points from conversation
        key_points = self._extract_key_points(messages[1:-2])

        compacted = []
        if system_msg:
            compacted.append(system_msg)
        compacted.append(
            {
                "role": "assistant",
                "content": f"[CONTEXT COLLAPSE: Conversation summarized to {len(key_points)} key points]\n\n"
                + "\n".join(f"- {p}" for p in key_points),
                "timestamp": time.time(),
            }
        )
        compacted.extend(last_two)
        return compacted

    def _ptl_truncation(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Level 5: Drop oldest message groups (last resort)."""
        if len(messages) <= 3:
            return messages

        # Keep system, last 3 messages
        system_msg = messages[0] if messages[0].get("role") == "system" else None
        last_three = messages[-3:]

        compacted = []
        if system_msg:
            compacted.append(system_msg)
        compacted.append(
            {
                "role": "assistant",
                "content": f"[PTL TRUNCATION: Dropped {len(messages) - 4} oldest messages to prevent context overflow]",
                "timestamp": time.time(),
            }
        )
        compacted.extend(last_three)
        return compacted

    def _summarize_messages(self, messages: List[Dict[str, Any]], max_length: int = 200) -> str:
        """Summarize a list of messages into key points."""
        key_points = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if len(content) > 100:
                key_points.append(f"{role}: {content[:100]}...")
            elif content:
                key_points.append(f"{role}: {content}")

        # Truncate to max_length
        summary = "\n".join(key_points)
        if len(summary) > max_length:
            summary = summary[:max_length] + "..."
        return summary

    def _extract_key_points(self, messages: List[Dict[str, Any]]) -> List[str]:
        """Extract key points from conversation for context collapse."""
        key_points = []
        tool_calls = 0
        files_changed = set()

        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if role == "tool":
                tool_calls += 1
                # Extract file changes
                if "file" in content.lower():
                    # Simple heuristic for file mentions
                    for word in content.split():
                        if word.endswith(".py") or word.endswith(".md"):
                            files_changed.add(word)

        if tool_calls > 0:
            key_points.append(f"Used {tool_calls} tools during conversation")
        if files_changed:
            key_points.append(f"Modified files: {', '.join(list(files_changed)[:5])}")

        if not key_points:
            key_points.append("Conversation contained standard task execution")

        return key_points

    def get_stats(self) -> Dict[str, Any]:
        """Get compaction statistics."""
        return {
            "total_compactions": self._total_compactions,
            "consecutive_failures": self._consecutive_failures,
            "circuit_breaker_tripped": self._consecutive_failures >= self.MAX_CONSECUTIVE_FAILURES,
            "history_count": len(self._history),
            "recent_compactions": [
                {
                    "level": r.level,
                    "tokens_saved": r.tokens_saved,
                    "success": r.success,
                    "timestamp": r.timestamp,
                }
                for r in self._history[-10:]
            ],
        }

    def reset_circuit_breaker(self) -> None:
        """Manually reset the circuit breaker."""
        self._consecutive_failures = 0
        self._save_state()
        log.info("[Compaction] Circuit breaker reset")


# Global compaction instance
_compaction: Optional[ContextCompaction] = None


def get_compaction(repo_dir: Optional[pathlib.Path] = None) -> ContextCompaction:
    """Get or create the global context compaction."""
    global _compaction
    if _compaction is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _compaction = ContextCompaction(repo_dir)
    return _compaction
