"""Temporal Tool Learning — Track which tool sequences succeed, reinforce them.

Inspired by RuVector's self-learning search:
- Track tool call sequences and their outcomes
- Reinforce patterns that lead to successful completions
- Decay patterns that lead to failures
- Used by semantic tool routing to select optimal tools

Three-speed learning (from RuVector):
    Instant: session-local pattern boost
    Session: reinforce successful sequences during active work
    Long-term: persist learned patterns across sessions
"""

from __future__ import annotations

import json
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ToolSequence:
    """A recorded tool call sequence."""

    tools: List[str]
    task_type: str
    success: bool
    timestamp: float
    round_count: int = 0
    token_count: int = 0


@dataclass
class PatternScore:
    """Score for a tool pattern."""

    tool: str
    task_type: str
    success_count: int = 0
    failure_count: int = 0
    last_used: float = 0.0
    avg_rounds: float = 0.0

    @property
    def score(self) -> float:
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Unknown, neutral
        base = self.success_count / total
        # Recency bonus: recent usage is more relevant
        age_hours = (time.time() - self.last_used) / 3600
        recency = max(0.0, 1.0 - (age_hours / 168))  # Decay over 1 week
        return base * 0.7 + recency * 0.3


class TemporalToolLearner:
    """Learns which tools work best for which task types.

    Tracks tool usage patterns and their outcomes to build
    a model of optimal tool selection per task type.
    """

    def __init__(self, persistence_path: Optional[Path] = None):
        # tool -> task_type -> PatternScore
        self._patterns: Dict[str, Dict[str, PatternScore]] = defaultdict(dict)
        self._session_sequences: List[ToolSequence] = []
        self._current_sequence: List[str] = []
        self._persistence_path = persistence_path
        if persistence_path and persistence_path.exists():
            self._load()

    def record_tool_call(self, tool_name: str) -> None:
        """Record that a tool was called (instant learning)."""
        self._current_sequence.append(tool_name)

    def record_sequence_outcome(
        self,
        success: bool,
        task_type: str = "general",
        round_count: int = 0,
        token_count: int = 0,
    ) -> None:
        """Record the outcome of the current tool sequence."""
        if not self._current_sequence:
            return

        seq = ToolSequence(
            tools=list(self._current_sequence),
            task_type=task_type,
            success=success,
            timestamp=time.time(),
            round_count=round_count,
            token_count=token_count,
        )
        self._session_sequences.append(seq)

        # Update pattern scores (session learning)
        for tool in set(self._current_sequence):
            if task_type not in self._patterns[tool]:
                self._patterns[tool][task_type] = PatternScore(tool=tool, task_type=task_type)
            pattern = self._patterns[tool][task_type]
            if success:
                pattern.success_count += 1
            else:
                pattern.failure_count += 1
            pattern.last_used = time.time()
            pattern.avg_rounds = pattern.avg_rounds * 0.8 + round_count * 0.2 if pattern.avg_rounds > 0 else round_count

        self._current_sequence.clear()

        # Persist if configured
        if self._persistence_path:
            self._save()

    def get_tool_scores(self, task_type: str) -> List[Tuple[str, float]]:
        """Get tool scores for a task type, sorted by score descending."""
        scores = []
        for tool, task_patterns in self._patterns.items():
            pattern = task_patterns.get(task_type)
            if pattern and (pattern.success_count + pattern.failure_count) >= 2:
                scores.append((tool, pattern.score))
        scores.sort(key=lambda x: -x[1])
        return scores

    def suggest_tools(self, task_type: str, candidate_tools: List[str], top_n: int = 5) -> List[str]:
        """Suggest best tools for a task type from candidates."""
        scores = self.get_tool_scores(task_type)
        score_map = {tool: score for tool, score in scores}

        # Sort candidates by learned score, with unknown tools at medium priority
        scored = [(t, score_map.get(t, 0.5)) for t in candidate_tools]
        scored.sort(key=lambda x: -x[1])
        return [t for t, _ in scored[:top_n]]

    def get_report(self) -> str:
        """Get human-readable learning report."""
        if not self._patterns:
            return "No tool patterns learned yet."

        lines = ["## Temporal Tool Learning Report", ""]

        task_types = set()
        for task_patterns in self._patterns.values():
            task_types.update(task_patterns.keys())

        for task_type in sorted(task_types):
            lines.append(f"### Task: {task_type}")
            scores = []
            for tool, task_patterns in self._patterns.items():
                pattern = task_patterns.get(task_type)
                if pattern:
                    total = pattern.success_count + pattern.failure_count
                    scores.append((tool, pattern.score, total))

            scores.sort(key=lambda x: -x[1])
            for tool, score, total in scores[:10]:
                bar = "█" * int(score * 10) + "░" * (10 - int(score * 10))
                lines.append(f"  {tool:25s} {bar} {score:.2f} ({total} uses)")
            lines.append("")

        return "\n".join(lines)

    def _save(self) -> None:
        try:
            data = {}
            for tool, task_patterns in self._patterns.items():
                data[tool] = {
                    task_type: {
                        "success_count": p.success_count,
                        "failure_count": p.failure_count,
                        "last_used": p.last_used,
                        "avg_rounds": p.avg_rounds,
                    }
                    for task_type, p in task_patterns.items()
                }
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            self._persistence_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            log.debug("Failed to save tool patterns: %s", e)

    def _load(self) -> None:
        try:
            data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
            for tool, task_data in data.items():
                for task_type, p_data in task_data.items():
                    self._patterns[tool][task_type] = PatternScore(
                        tool=tool,
                        task_type=task_type,
                        success_count=p_data.get("success_count", 0),
                        failure_count=p_data.get("failure_count", 0),
                        last_used=p_data.get("last_used", 0),
                        avg_rounds=p_data.get("avg_rounds", 0),
                    )
        except Exception as e:
            log.debug("Failed to load tool patterns: %s", e)


# Global singleton
_learner: Optional[TemporalToolLearner] = None


def get_learner(repo_dir: Optional[Path] = None) -> TemporalToolLearner:
    global _learner
    if _learner is None:
        path = repo_dir / ".jo_data" / "tool_patterns.json" if repo_dir else None
        _learner = TemporalToolLearner(persistence_path=path)
    return _learner
