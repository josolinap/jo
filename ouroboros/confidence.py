"""Confidence scoring — know what you don't know.

Scores Jo's confidence in actions based on:
- Historical success rate of the tool/skill being used
- Context relevance (how similar to past successes)
- Data freshness (how recent is the knowledge)
- Source consensus (do multiple sources agree)

Confidence levels:
- High (>0.8): Execute directly
- Medium (0.5-0.8): Execute but verify after
- Low (<0.5): Ask for help, research more, or skip
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class ConfidenceScorer:
    """Score confidence in actions and decisions."""

    def __init__(self, drive_root: pathlib.Path):
        self._drive_root = drive_root
        self._history_path = drive_root / "logs" / "confidence_history.jsonl"

    def score_tool_use(self, tool_name: str, context: str = "") -> Dict[str, Any]:
        """Score confidence for using a specific tool."""
        historical = self._get_tool_success_rate(tool_name)
        freshness = self._get_data_freshness(tool_name)

        confidence = (
            historical * 0.5 + freshness * 0.3 + 0.2  # Base confidence
        )

        return {
            "tool": tool_name,
            "confidence": round(confidence, 3),
            "level": self._level(confidence),
            "historical_success": round(historical, 3),
            "data_freshness": round(freshness, 3),
            "recommendation": self._recommend(confidence),
        }

    def score_decision(self, decision_type: str, evidence_count: int = 0) -> Dict[str, Any]:
        """Score confidence for a decision."""
        # More evidence = higher confidence
        evidence_score = min(1.0, evidence_count / 5)

        # Historical success for this decision type
        historical = self._get_decision_success_rate(decision_type)

        confidence = (
            historical * 0.4 + evidence_score * 0.4 + 0.2  # Base
        )

        return {
            "decision_type": decision_type,
            "confidence": round(confidence, 3),
            "level": self._level(confidence),
            "evidence_count": evidence_count,
            "recommendation": self._recommend(confidence),
        }

    def score_knowledge(self, topic: str, source_count: int = 1, source_age_days: float = 0) -> Dict[str, Any]:
        """Score confidence in knowledge about a topic."""
        # More sources = higher confidence
        source_score = min(1.0, source_count / 3)

        # Fresher sources = higher confidence
        freshness = 2 ** (-source_age_days / 7)  # Halflife of 7 days

        confidence = (
            source_score * 0.5 + freshness * 0.3 + 0.2  # Base
        )

        return {
            "topic": topic,
            "confidence": round(confidence, 3),
            "level": self._level(confidence),
            "source_count": source_count,
            "source_freshness": round(freshness, 3),
            "recommendation": self._recommend(confidence),
        }

    def record_outcome(self, action: str, success: bool, details: str = "") -> None:
        """Record an outcome for future confidence scoring."""
        try:
            entry = {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "action": action,
                "success": success,
                "details": details[:200],
            }
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._history_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception:
            pass

    def get_confidence_report(self) -> str:
        """Generate a confidence system report."""
        history = self._load_history()
        if not history:
            return "No confidence history yet."

        total = len(history)
        successes = sum(1 for h in history if h.get("success"))
        rate = successes / total if total > 0 else 0

        lines = [
            "## Confidence Report",
            "",
            f"**Total actions recorded:** {total}",
            f"**Success rate:** {rate:.0%}",
        ]

        # By action type
        by_action: Dict[str, Dict[str, int]] = {}
        for h in history:
            action = h.get("action", "unknown")
            if action not in by_action:
                by_action[action] = {"total": 0, "success": 0}
            by_action[action]["total"] += 1
            if h.get("success"):
                by_action[action]["success"] += 1

        if by_action:
            lines.append("\n### By Action Type")
            for action, stats in sorted(by_action.items(), key=lambda x: -x[1]["total"])[:10]:
                r = stats["success"] / stats["total"] if stats["total"] > 0 else 0
                lines.append(f"- {action}: {r:.0%} ({stats['total']} uses)")

        return "\n".join(lines)

    def _level(self, confidence: float) -> str:
        """Convert numeric confidence to level."""
        if confidence >= 0.8:
            return "high"
        elif confidence >= 0.5:
            return "medium"
        else:
            return "low"

    def _recommend(self, confidence: float) -> str:
        """Get recommendation based on confidence."""
        if confidence >= 0.8:
            return "Execute directly"
        elif confidence >= 0.5:
            return "Execute but verify after"
        else:
            return "Research more or ask for help"

    def _get_tool_success_rate(self, tool_name: str) -> float:
        """Get historical success rate for a tool."""
        history = self._load_history()
        tool_history = [h for h in history if tool_name in h.get("action", "")]
        if not tool_history:
            return 0.5  # Unknown, neutral
        successes = sum(1 for h in tool_history if h.get("success"))
        return successes / len(tool_history)

    def _get_decision_success_rate(self, decision_type: str) -> float:
        """Get historical success rate for a decision type."""
        history = self._load_history()
        type_history = [h for h in history if decision_type in h.get("action", "")]
        if not type_history:
            return 0.5
        successes = sum(1 for h in type_history if h.get("success"))
        return successes / len(type_history)

    def _get_data_freshness(self, tool_name: str) -> float:
        """Estimate data freshness for a tool (0-1)."""
        history = self._load_history()
        tool_history = [h for h in history if tool_name in h.get("action", "")]
        if not tool_history:
            return 0.5

        # Check last use
        last_use = tool_history[-1].get("ts", "")
        if not last_use:
            return 0.5

        try:
            last_time = time.mktime(time.strptime(last_use, "%Y-%m-%dT%H:%M:%S"))
            hours_since = (time.time() - last_time) / 3600
            # Freshness decays over 24 hours
            return max(0.1, 2 ** (-hours_since / 24))
        except Exception:
            return 0.5

    def _load_history(self) -> list:
        """Load confidence history."""
        if not self._history_path.exists():
            return []
        try:
            entries = []
            for line in self._history_path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    entries.append(json.loads(line))
            return entries[-500:]  # Last 500 entries
        except Exception:
            return []
