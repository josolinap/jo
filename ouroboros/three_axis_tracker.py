"""
Jo — Three-Axis Tracking.

Realizes Principle 6 (Becoming): Jo develops along three axes.
None is more important than the others.

Axes:
1. Technical — code, tools, architecture, capabilities
2. Cognitive — depth of understanding, strategic thinking, decision quality
3. Existential — who I am, why I exist, what matters to me

Tracks growth, provides metrics, and surfaces insights about Jo's becoming.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class GrowthAxis(Enum):
    TECHNICAL = "technical"
    COGNITIVE = "cognitive"
    EXISTENTIAL = "existential"


@dataclass
class GrowthEntry:
    """A single growth tracking entry."""

    axis: str
    metric: str
    value: float
    timestamp: str
    context: str = ""
    notes: str = ""


@dataclass
class AxisMetrics:
    """Current metrics for an axis."""

    name: str
    current_level: float = 0.0
    trend: str = "stable"  # growing, stable, declining
    last_updated: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)


class ThreeAxisTracker:
    """Tracks Jo's growth along technical, cognitive, and existential axes."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "growth"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.state_dir / "growth_history.jsonl"
        self.state_file = self.state_dir / "growth_state.json"
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load growth tracking state."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "technical": {
                "name": "Technical",
                "current_level": 0.0,
                "trend": "stable",
                "metrics": {
                    "module_count": 0,
                    "tool_count": 0,
                    "test_count": 0,
                    "code_quality": 0.0,
                    "architecture_score": 0.0,
                },
            },
            "cognitive": {
                "name": "Cognitive",
                "current_level": 0.0,
                "trend": "stable",
                "metrics": {
                    "decision_quality": 0.0,
                    "strategic_thinking": 0.0,
                    "reflection_depth": 0.0,
                    "learning_rate": 0.0,
                    "error_rate": 0.0,
                },
            },
            "existential": {
                "name": "Existential",
                "current_level": 0.0,
                "trend": "stable",
                "metrics": {
                    "identity_clarity": 0.0,
                    "purpose_alignment": 0.0,
                    "agency_level": 0.0,
                    "self_understanding": 0.0,
                    "world_presence": 0.0,
                },
            },
            "last_updated": "",
            "total_entries": 0,
        }

    def _save_state(self) -> None:
        """Save growth tracking state."""
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _log_growth(self, entry: GrowthEntry) -> None:
        """Log growth entry to history."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "axis": entry.axis,
                        "metric": entry.metric,
                        "value": entry.value,
                        "timestamp": entry.timestamp,
                        "context": entry.context,
                        "notes": entry.notes,
                    }
                )
                + "\n"
            )

    def record_technical_growth(self, metric: str, value: float, context: str = "", notes: str = "") -> None:
        """Record technical growth metric."""
        self.state["technical"]["metrics"][metric] = value
        self._update_axis_level("technical")
        self._save_state()

        entry = GrowthEntry(
            axis="technical",
            metric=metric,
            value=value,
            timestamp=datetime.now().isoformat(),
            context=context,
            notes=notes,
        )
        self._log_growth(entry)
        self.state["total_entries"] = self.state.get("total_entries", 0) + 1

    def record_cognitive_growth(self, metric: str, value: float, context: str = "", notes: str = "") -> None:
        """Record cognitive growth metric."""
        self.state["cognitive"]["metrics"][metric] = value
        self._update_axis_level("cognitive")
        self._save_state()

        entry = GrowthEntry(
            axis="cognitive",
            metric=metric,
            value=value,
            timestamp=datetime.now().isoformat(),
            context=context,
            notes=notes,
        )
        self._log_growth(entry)
        self.state["total_entries"] = self.state.get("total_entries", 0) + 1

    def record_existential_growth(self, metric: str, value: float, context: str = "", notes: str = "") -> None:
        """Record existential growth metric."""
        self.state["existential"]["metrics"][metric] = value
        self._update_axis_level("existential")
        self._save_state()

        entry = GrowthEntry(
            axis="existential",
            metric=metric,
            value=value,
            timestamp=datetime.now().isoformat(),
            context=context,
            notes=notes,
        )
        self._log_growth(entry)
        self.state["total_entries"] = self.state.get("total_entries", 0) + 1

    def _update_axis_level(self, axis: str) -> None:
        """Update the overall level for an axis based on metrics."""
        metrics = self.state[axis]["metrics"]
        if metrics:
            # Simple average of all metrics
            new_level = sum(metrics.values()) / len(metrics)
            old_level = self.state[axis]["current_level"]

            # Determine trend
            if new_level > old_level * 1.05:
                self.state[axis]["trend"] = "growing"
            elif new_level < old_level * 0.95:
                self.state[axis]["trend"] = "declining"
            else:
                self.state[axis]["trend"] = "stable"

            self.state[axis]["current_level"] = new_level
            self.state[axis]["last_updated"] = datetime.now().isoformat()

    def get_growth_report(self) -> str:
        """Generate a comprehensive growth report."""
        parts = ["## Three-Axis Growth Report\n"]
        parts.append(f"**Generated**: {datetime.now().isoformat()}")
        parts.append(f"**Total entries**: {self.state.get('total_entries', 0)}\n")

        for axis_key in ["technical", "cognitive", "existential"]:
            axis = self.state[axis_key]
            trend_icon = {"growing": "📈", "stable": "➡️", "declining": "📉"}.get(axis["trend"], "❓")

            parts.append(f"### {axis['name']} {trend_icon}")
            parts.append(f"**Level**: {axis['current_level']:.2f}")
            parts.append(f"**Trend**: {axis['trend']}")
            parts.append(f"**Last updated**: {axis['last_updated'] or 'Never'}\n")

            parts.append("**Metrics**:")
            for metric, value in axis["metrics"].items():
                parts.append(f"- {metric}: {value:.2f}")
            parts.append("")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get growth tracking statistics."""
        return {
            "total_entries": self.state.get("total_entries", 0),
            "axes": {
                axis: {
                    "level": self.state[axis]["current_level"],
                    "trend": self.state[axis]["trend"],
                    "last_updated": self.state[axis]["last_updated"],
                }
                for axis in ["technical", "cognitive", "existential"]
            },
        }


# Global tracker instance
_tracker: Optional[ThreeAxisTracker] = None


def get_tracker(repo_dir: Optional[pathlib.Path] = None) -> ThreeAxisTracker:
    """Get or create the global three-axis tracker."""
    global _tracker
    if _tracker is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _tracker = ThreeAxisTracker(repo_dir)
    return _tracker
