"""Evolution strategy — adaptive issue prioritization and trend analysis.

Smart algorithm that:
- Tracks evolution history across cycles
- Prioritizes issues by impact score (severity × frequency × fixability)
- Adapts check focus based on what's been failing recently
- Detects trends (improving, stable, degrading)
- Learns which fixes actually resolved issues
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

HISTORY_PATH = "~/.jo_data/evolution_history.json"
MAX_HISTORY = 100


@dataclass
class IssueRecord:
    """A detected issue with scoring metadata."""

    category: str  # test, syntax, module_size, drift, performance
    description: str
    severity: float  # 0.0-1.0
    frequency: int  # how many cycles this appeared
    fixability: float  # 0.0-1.0, how likely a fix is
    first_seen: str = ""
    last_seen: str = ""

    @property
    def impact_score(self) -> float:
        """Combined priority score: severity × frequency_weight × fixability."""
        freq_weight = min(1.0, self.frequency / 5)  # Cap at 5 occurrences
        return self.severity * (0.3 + 0.7 * freq_weight) * self.fixability


@dataclass
class CycleRecord:
    """Record of a completed evolution cycle."""

    cycle_id: str
    timestamp: str
    issues_found: List[str]
    issues_resolved: List[str]
    status: str  # complete, degraded, failed
    duration_sec: float
    health_score: float  # 0.0-1.0 computed from issues


class EvolutionStrategy:
    """Adaptive evolution strategy with trend analysis."""

    def __init__(self, history_path: Optional[str] = None):
        self._path = pathlib.Path(str(pathlib.Path(history_path or HISTORY_PATH).expanduser()))
        self._history: List[CycleRecord] = []
        self._issue_registry: Dict[str, IssueRecord] = {}
        self._load_history()

    def _load_history(self) -> None:
        """Load evolution history from disk."""
        try:
            if self._path.exists():
                data = json.loads(self._path.read_text(encoding="utf-8"))
                for rec in data.get("cycles", [])[-MAX_HISTORY:]:
                    self._history.append(CycleRecord(**rec))
                for key, val in data.get("issues", {}).items():
                    self._issue_registry[key] = IssueRecord(**val)
                log.debug("Loaded %d cycle records", len(self._history))
        except Exception as e:
            log.warning("Failed to load evolution history: %s", e)
            self._history = []
            self._issue_registry = {}

    def save_history(self) -> None:
        """Persist evolution history to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "cycles": [
                    {
                        "cycle_id": c.cycle_id,
                        "timestamp": c.timestamp,
                        "issues_found": c.issues_found,
                        "issues_resolved": c.issues_resolved,
                        "status": c.status,
                        "duration_sec": c.duration_sec,
                        "health_score": c.health_score,
                    }
                    for c in self._history[-MAX_HISTORY:]
                ],
                "issues": {
                    k: {
                        "category": v.category,
                        "description": v.description,
                        "severity": v.severity,
                        "frequency": v.frequency,
                        "fixability": v.fixability,
                        "first_seen": v.first_seen,
                        "last_seen": v.last_seen,
                    }
                    for k, v in self._issue_registry.items()
                },
            }
            self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Failed to save evolution history: %s", e)

    def record_cycle(self, record: CycleRecord) -> None:
        """Record a completed cycle and update issue registry."""
        self._history.append(record)
        now = record.timestamp

        # Update issue registry
        for issue_desc in record.issues_found:
            key = self._issue_key(issue_desc)
            if key in self._issue_registry:
                ir = self._issue_registry[key]
                ir.frequency += 1
                ir.last_seen = now
            else:
                category = self._categorize_issue(issue_desc)
                severity = self._score_severity(issue_desc)
                fixability = self._score_fixability(issue_desc)
                self._issue_registry[key] = IssueRecord(
                    category=category,
                    description=issue_desc,
                    severity=severity,
                    frequency=1,
                    fixability=fixability,
                    first_seen=now,
                    last_seen=now,
                )

        # Mark resolved issues
        for issue_desc in record.issues_resolved:
            key = self._issue_key(issue_desc)
            if key in self._issue_registry:
                del self._issue_registry[key]

        self.save_history()

    def prioritize_issues(self, issues: List[str]) -> List[Tuple[str, float]]:
        """Rank issues by impact score (highest first)."""
        scored: List[Tuple[str, float]] = []
        for issue in issues:
            key = self._issue_key(issue)
            if key in self._issue_registry:
                scored.append((issue, self._issue_registry[key].impact_score))
            else:
                # New issue: score by severity and fixability
                score = self._score_severity(issue) * self._score_fixability(issue)
                scored.append((issue, score))

        scored.sort(key=lambda x: -x[1])
        return scored

    def get_trend(self) -> Dict[str, Any]:
        """Analyze health trend across recent cycles."""
        if len(self._history) < 2:
            return {"trend": "insufficient_data", "cycles": len(self._history)}

        recent = self._history[-5:]
        older = self._history[-10:-5] if len(self._history) >= 10 else self._history[: len(self._history) - 5]

        recent_health = sum(c.health_score for c in recent) / len(recent)
        older_health = sum(c.health_score for c in older) / len(older) if older else recent_health

        delta = recent_health - older_health
        if delta > 0.05:
            trend = "improving"
        elif delta < -0.05:
            trend = "degrading"
        else:
            trend = "stable"

        recent_fail_rate = sum(1 for c in recent if c.status == "failed") / len(recent)
        avg_duration = sum(c.duration_sec for c in recent) / len(recent)
        recurring_issues = [k for k, v in self._issue_registry.items() if v.frequency >= 3]

        return {
            "trend": trend,
            "health_delta": round(delta, 3),
            "recent_health": round(recent_health, 3),
            "older_health": round(older_health, 3),
            "failure_rate": round(recent_fail_rate, 2),
            "avg_duration_sec": round(avg_duration, 1),
            "recurring_issues": recurring_issues,
            "total_cycles": len(self._history),
            "unresolved_issues": len(self._issue_registry),
        }

    def suggest_focus(self) -> List[str]:
        """Suggest what checks to focus on based on history."""
        suggestions: List[str] = []

        trend = self.get_trend()
        if trend["trend"] == "degrading":
            suggestions.append("System degrading — investigate recent changes")
        if trend["failure_rate"] > 0.3:
            suggestions.append("High failure rate — check for environmental issues")
        if trend["recurring_issues"]:
            suggestions.append(f"Recurring issues: {', '.join(trend['recurring_issues'][:3])}")

        # Check for categories that keep appearing
        category_freq: Dict[str, int] = {}
        for ir in self._issue_registry.values():
            category_freq[ir.category] = category_freq.get(ir.category, 0) + ir.frequency
        for cat, freq in sorted(category_freq.items(), key=lambda x: -x[1]):
            if freq >= 3:
                suggestions.append(f"Category '{cat}' has {freq} recurring occurrences")

        return suggestions

    def compute_health_score(self, issues: List[str]) -> float:
        """Compute a 0.0-1.0 health score from current issues."""
        if not issues:
            return 1.0

        total_penalty = 0.0
        for issue in issues:
            key = self._issue_key(issue)
            if key in self._issue_registry:
                total_penalty += self._issue_registry[key].severity * 0.15
            else:
                total_penalty += self._score_severity(issue) * 0.15

        return max(0.0, 1.0 - total_penalty)

    @staticmethod
    def _issue_key(description: str) -> str:
        """Normalize issue description to a stable key."""
        # Extract the core issue type
        desc_lower = description.lower()
        if "test" in desc_lower and "fail" in desc_lower:
            return "test_failure"
        if "syntax" in desc_lower:
            return "syntax_error"
        if "module size" in desc_lower or "lines" in desc_lower:
            return "module_size"
        if "drift" in desc_lower:
            return "drift_violation"
        # Fallback: first 50 chars
        return description[:50].lower().strip()

    @staticmethod
    def _categorize_issue(description: str) -> str:
        """Categorize an issue description."""
        desc_lower = description.lower()
        if "test" in desc_lower:
            return "test"
        if "syntax" in desc_lower:
            return "syntax"
        if "module size" in desc_lower or "lines" in desc_lower:
            return "module_size"
        if "drift" in desc_lower or "identity" in desc_lower:
            return "drift"
        return "general"

    @staticmethod
    def _score_severity(description: str) -> float:
        """Score issue severity 0.0-1.0."""
        desc_lower = description.lower()
        if "critical" in desc_lower or "fail" in desc_lower:
            return 0.9
        if "syntax" in desc_lower:
            return 0.8
        if "module size" in desc_lower:
            return 0.6
        if "drift" in desc_lower:
            return 0.5
        if "stale" in desc_lower:
            return 0.3
        return 0.4

    @staticmethod
    def _score_fixability(description: str) -> float:
        """Score how fixable an issue is 0.0-1.0."""
        desc_lower = description.lower()
        if "syntax" in desc_lower:
            return 0.9
        if "stale" in desc_lower or "identity" in desc_lower:
            return 0.95
        if "test" in desc_lower and "fail" in desc_lower:
            return 0.7
        if "module size" in desc_lower:
            return 0.5  # Requires refactoring
        if "drift" in desc_lower:
            return 0.6
        return 0.5
