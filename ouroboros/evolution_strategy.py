"""Adaptive evolution strategy for Jo's self-improvement cycles.

Tracks cycle history, computes health trends, prioritizes issues,
and suggests focus areas for the next evolution cycle.
"""

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class CycleRecord:
    """Record of a single evolution cycle."""

    cycle_id: str
    timestamp: str
    issues_found: List[str] = field(default_factory=list)
    issues_resolved: List[str] = field(default_factory=list)
    status: str = "unknown"  # complete, degraded, failed
    duration_sec: float = 0.0
    health_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class EvolutionStrategy:
    """Adaptive strategy that learns from past evolution cycles.

    Tracks health trends, prioritizes issues by impact, and suggests
    focus areas based on recurring patterns.
    """

    def __init__(self, persistence_path: Optional[pathlib.Path] = None):
        self._history: List[CycleRecord] = []
        self._persistence_path = persistence_path
        self._load_history()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        if self._persistence_path and self._persistence_path.exists():
            try:
                data = json.loads(self._persistence_path.read_text(encoding="utf-8"))
                self._history = [
                    CycleRecord(
                        cycle_id=r["cycle_id"],
                        timestamp=r["timestamp"],
                        issues_found=r.get("issues_found", []),
                        issues_resolved=r.get("issues_resolved", []),
                        status=r.get("status", "unknown"),
                        duration_sec=r.get("duration_sec", 0.0),
                        health_score=r.get("health_score", 0.0),
                        metadata=r.get("metadata", {}),
                    )
                    for r in data
                ]
            except Exception:
                log.debug("Failed to load evolution history", exc_info=True)

    def _save_history(self) -> None:
        if not self._persistence_path:
            return
        try:
            self._persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "cycle_id": r.cycle_id,
                    "timestamp": r.timestamp,
                    "issues_found": r.issues_found,
                    "issues_resolved": r.issues_resolved,
                    "status": r.status,
                    "duration_sec": r.duration_sec,
                    "health_score": r.health_score,
                    "metadata": r.metadata,
                }
                for r in self._history
            ]
            self._persistence_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            log.debug("Failed to save evolution history", exc_info=True)

    # ------------------------------------------------------------------
    # Recording
    # ------------------------------------------------------------------

    def record_cycle(self, record: CycleRecord) -> None:
        """Record a completed evolution cycle."""
        self._history.insert(0, record)
        # Keep last 50 cycles
        if len(self._history) > 50:
            self._history = self._history[:50]
        self._save_history()

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------

    def get_trend(self) -> Dict[str, Any]:
        """Analyse recent health scores to determine trend direction."""
        if len(self._history) < 2:
            return {"trend": "unknown", "total_cycles": len(self._history)}

        recent = self._history[:10]
        scores = [r.health_score for r in recent if r.health_score > 0]
        if len(scores) < 2:
            return {
                "trend": "unknown",
                "total_cycles": len(self._history),
                "recent_health": scores[0] if scores else 0.0,
            }

        # Simple linear slope
        n = len(scores)
        x_mean = (n - 1) / 2
        y_mean = sum(scores) / n
        numerator = sum((i - x_mean) * (s - y_mean) for i, s in enumerate(scores))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0

        if slope > 0.01:
            trend = "improving"
        elif slope < -0.01:
            trend = "degrading"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "total_cycles": len(self._history),
            "recent_health": round(scores[0], 3),
            "avg_health": round(y_mean, 3),
            "health_delta": round(scores[0] - scores[-1], 3),
        }

    def suggest_focus(self) -> List[str]:
        """Suggest focus areas based on recurring issues."""
        if not self._history:
            return []

        issue_counts: Dict[str, int] = {}
        for record in self._history[:20]:
            for issue in record.issues_found:
                # Normalise: take the part before the first colon
                key = issue.split(":")[0].strip().lower()
                issue_counts[key] = issue_counts.get(key, 0) + 1

        # Return issues that appeared in >= 3 cycles
        recurring = [k for k, v in sorted(issue_counts.items(), key=lambda x: -x[1]) if v >= 3]
        return recurring[:5]

    # ------------------------------------------------------------------
    # Issue prioritisation
    # ------------------------------------------------------------------

    def prioritize_issues(self, issues: List[str]) -> List[Tuple[str, float]]:
        """Prioritise issues by estimated impact.

        Returns list of (issue, impact_score) sorted descending.
        """
        if not issues:
            return []

        scored = []
        for issue in issues:
            score = self._score_issue(issue)
            scored.append((issue, score))

        scored.sort(key=lambda x: -x[1])
        return scored

    def _score_issue(self, issue: str) -> float:
        """Score a single issue by estimated impact (0..1)."""
        score = 0.5  # base

        issue_lower = issue.lower()

        # Syntax / compilation errors are highest priority
        if any(kw in issue_lower for kw in ("syntax", "compile", "import error", "traceback")):
            score += 0.3

        # Security issues
        if any(kw in issue_lower for kw in ("secret", "credential", "security", "vulnerability")):
            score += 0.25

        # Module size / complexity
        if any(kw in issue_lower for kw in ("module", "too large", "complexity", "cohesion")):
            score += 0.15

        # Drift / constitution violations
        if "drift" in issue_lower:
            score += 0.2

        # Recurring issues get a bonus
        key = issue.split(":")[0].strip().lower()
        recurring_count = sum(
            1 for r in self._history[:10] for i in r.issues_found if i.split(":")[0].strip().lower() == key
        )
        if recurring_count >= 2:
            score += 0.1 * recurring_count

        return min(score, 1.0)

    # ------------------------------------------------------------------
    # Health score
    # ------------------------------------------------------------------

    def compute_health_score(self, issues: List[str]) -> float:
        """Compute a health score from 0 (bad) to 1 (healthy)."""
        if not issues:
            return 1.0

        # Penalise per issue, more for severe categories
        penalty = 0.0
        for issue in issues:
            issue_lower = issue.lower()
            if any(kw in issue_lower for kw in ("syntax", "compile", "traceback")):
                penalty += 0.15
            elif any(kw in issue_lower for kw in ("secret", "security")):
                penalty += 0.12
            elif "drift" in issue_lower:
                penalty += 0.10
            else:
                penalty += 0.05

        return max(0.0, 1.0 - penalty)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    def stats(self) -> Dict[str, Any]:
        """Return summary statistics."""
        total = len(self._history)
        if total == 0:
            return {"total_cycles": 0}

        statuses = {}
        for r in self._history:
            statuses[r.status] = statuses.get(r.status, 0) + 1

        health_scores = [r.health_score for r in self._history if r.health_score > 0]
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0.0

        return {
            "total_cycles": total,
            "statuses": statuses,
            "avg_health": round(avg_health, 3),
            "latest_health": round(self._history[0].health_score, 3) if self._history else 0.0,
        }
