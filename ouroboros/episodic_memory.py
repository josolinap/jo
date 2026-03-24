"""Episodic Memory — Decision/action/outcome tracking for Jo.

Inspired by SAFLA's episodic memory:
- Records decisions, actions taken, and outcomes
- Enables "what happened last time I did X?" queries
- Links episodes to vault concepts and tool patterns
- Feeds into delta evaluation and temporal learning

Structure:
    Episode = {decision, action, outcome, context, timestamp}
    Stored in ~/.jo_data/memory/episodes.jsonl
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Episode:
    """A recorded decision-action-outcome cycle."""

    decision: str
    action: str
    outcome: str
    context: str
    success: bool
    timestamp: str
    tools_used: List[str] = field(default_factory=list)
    concepts_involved: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "action": self.action,
            "outcome": self.outcome,
            "context": self.context,
            "success": self.success,
            "timestamp": self.timestamp,
            "tools_used": self.tools_used,
            "concepts_involved": self.concepts_involved,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Episode:
        return cls(
            decision=data.get("decision", ""),
            action=data.get("action", ""),
            outcome=data.get("outcome", ""),
            context=data.get("context", ""),
            success=data.get("success", False),
            timestamp=data.get("timestamp", ""),
            tools_used=data.get("tools_used", []),
            concepts_involved=data.get("concepts_involved", []),
            metadata=data.get("metadata", {}),
        )


class EpisodicMemory:
    """Stores and retrieves decision-action-outcome episodes.

    Backed by a JSONL file for append-only persistence.
    Supports semantic search by decision/action text matching.
    """

    def __init__(self, storage_path: Path, max_episodes: int = 500):
        self._path = Path(storage_path)
        self._max = max_episodes
        self._episodes: List[Episode] = []
        self._load()

    def record(
        self,
        decision: str,
        action: str,
        outcome: str,
        context: str = "",
        success: bool = True,
        tools_used: Optional[List[str]] = None,
        concepts_involved: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Episode:
        """Record a new episode."""
        from datetime import datetime, timezone

        episode = Episode(
            decision=decision,
            action=action,
            outcome=outcome,
            context=context,
            success=success,
            timestamp=datetime.now(timezone.utc).isoformat(),
            tools_used=tools_used or [],
            concepts_involved=concepts_involved or [],
            metadata=metadata or {},
        )
        self._episodes.append(episode)
        self._save(episode)

        # Trim if over max
        if len(self._episodes) > self._max:
            self._episodes = self._episodes[-self._max :]

        return episode

    def recall(
        self,
        query: str,
        limit: int = 5,
        success_only: bool = False,
    ) -> List[Episode]:
        """Find episodes related to a query.

        Simple text matching on decision, action, and context fields.
        Returns most recent matches first.
        """
        query_lower = query.lower()
        terms = [t for t in query_lower.split() if len(t) > 2]

        scored: List[tuple] = []
        for ep in self._episodes:
            if success_only and not ep.success:
                continue
            searchable = (f"{ep.decision} {ep.action} {ep.outcome} {ep.context}").lower()
            score = sum(1 for t in terms if t in searchable)
            if score > 0:
                scored.append((score, ep.timestamp, ep))

        scored.sort(key=lambda x: (-x[0], x[1]), reverse=False)
        return [ep for _, _, ep in scored[:limit]]

    def recall_by_tool(self, tool_name: str, limit: int = 5) -> List[Episode]:
        """Find episodes where a specific tool was used."""
        matches = [ep for ep in self._episodes if tool_name in ep.tools_used]
        return matches[-limit:]

    def recall_similar_outcome(self, outcome_keywords: str, limit: int = 5) -> List[Episode]:
        """Find episodes with similar outcomes."""
        terms = set(outcome_keywords.lower().split())
        scored = []
        for ep in self._episodes:
            outcome_lower = ep.outcome.lower()
            score = sum(1 for t in terms if t in outcome_lower)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: -x[0])
        return [ep for _, ep in scored[:limit]]

    def get_success_rate(self, context_filter: Optional[str] = None) -> float:
        """Get success rate, optionally filtered by context."""
        if context_filter:
            filtered = [ep for ep in self._episodes if context_filter.lower() in ep.context.lower()]
        else:
            filtered = self._episodes

        if not filtered:
            return 0.0
        return sum(1 for ep in filtered if ep.success) / len(filtered)

    def get_report(self) -> str:
        """Human-readable episodic memory report."""
        if not self._episodes:
            return "No episodes recorded yet."

        total = len(self._episodes)
        success = sum(1 for ep in self._episodes if ep.success)
        recent = self._episodes[-5:]

        lines = [
            "## Episodic Memory Report",
            "",
            f"**Total episodes:** {total}",
            f"**Success rate:** {success}/{total} ({success / max(total, 1) * 100:.0f}%)",
            "",
            "### Recent Episodes",
        ]
        for ep in reversed(recent):
            icon = "✅" if ep.success else "❌"
            lines.append(f"- {icon} **{ep.decision[:60]}**")
            lines.append(f"  Action: {ep.action[:80]}")
            if ep.outcome:
                lines.append(f"  Outcome: {ep.outcome[:80]}")
        return "\n".join(lines)

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        data = json.loads(line)
                        self._episodes.append(Episode.from_dict(data))
        except Exception as e:
            log.debug("Failed to load episodes: %s", e)

    def _save(self, episode: Episode) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(episode.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            log.warning("Failed to save episode: %s", e)


# Global singleton
_memory: Optional[EpisodicMemory] = None


def get_episodic_memory(repo_dir: Optional[Path] = None) -> EpisodicMemory:
    global _memory
    if _memory is None:
        path = (
            repo_dir / ".jo_data" / "memory" / "episodes.jsonl" if repo_dir else Path(".jo_data/memory/episodes.jsonl")
        )
        _memory = EpisodicMemory(storage_path=path)
    return _memory
