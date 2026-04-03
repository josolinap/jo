"""
Jo — Behavioral Drift Detection.

Inspired by N-iX Research and AI Agent Observability best practices.
Detects when Jo's output quality degrades over time.

Problem: AI agents can degrade silently — hallucinating, skipping steps,
or producing lower-quality outputs without triggering any traditional error signal.

Solution: Track behavioral metrics over time and alert when they deviate
from established baselines.

Metrics tracked:
- Response length distribution
- Tool call success rate
- Task completion rate
- Error rate per task type
- Confidence score distribution
- Response format adherence (schema validation pass rates)
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class DriftMetric:
    """A single behavioral metric measurement."""

    name: str
    value: float
    timestamp: str
    context: str = ""


@dataclass
class DriftAlert:
    """An alert when a metric deviates from baseline."""

    metric: str
    current_value: float
    baseline_value: float
    deviation_pct: float
    severity: str  # "warning", "critical"
    timestamp: str
    context: str = ""


class BehavioralDriftDetector:
    """Detects behavioral drift in Jo's outputs over time."""

    def __init__(self, repo_dir: pathlib.Path, window_size: int = 100):
        self.repo_dir = repo_dir
        self.window_size = window_size
        self.state_dir = repo_dir / ".jo_state" / "behavioral_drift"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Metric history (rolling window)
        self._metrics: Dict[str, deque] = {}
        self._baselines: Dict[str, float] = {}
        self._alerts: List[DriftAlert] = []
        self._load_state()

    def _load_state(self) -> None:
        """Load drift detection state."""
        state_file = self.state_dir / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self._baselines = data.get("baselines", {})
                self._alerts = [DriftAlert(**a) for a in data.get("alerts", [])[-50:]]
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save drift detection state."""
        state_file = self.state_dir / "state.json"
        state_file.write_text(
            json.dumps(
                {
                    "baselines": self._baselines,
                    "alerts": [
                        {
                            "metric": a.metric,
                            "current_value": a.current_value,
                            "baseline_value": a.baseline_value,
                            "deviation_pct": a.deviation_pct,
                            "severity": a.severity,
                            "timestamp": a.timestamp,
                            "context": a.context,
                        }
                        for a in self._alerts[-50:]
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def record_metric(self, name: str, value: float, context: str = "") -> None:
        """Record a metric measurement."""
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self.window_size)

        self._metrics[name].append(
            {
                "value": value,
                "timestamp": datetime.now().isoformat(),
                "context": context,
            }
        )

        # Check for drift if we have enough data
        if len(self._metrics[name]) >= 10:
            self._check_drift(name)

    def set_baseline(self, name: str, value: float) -> None:
        """Set a baseline value for a metric."""
        self._baselines[name] = value
        self._save_state()
        log.info("[BehavioralDrift] Set baseline for %s: %.4f", name, value)

    def _check_drift(self, name: str) -> None:
        """Check if a metric has drifted from its baseline."""
        if name not in self._baselines or name not in self._metrics:
            return

        baseline = self._baselines[name]
        recent = list(self._metrics[name])[-10:]  # Last 10 measurements
        current_avg = sum(m["value"] for m in recent) / len(recent)

        if baseline == 0:
            deviation_pct = 0.0
        else:
            deviation_pct = abs(current_avg - baseline) / baseline * 100

        # Alert thresholds
        if deviation_pct > 50:
            severity = "critical"
        elif deviation_pct > 25:
            severity = "warning"
        else:
            return  # No alert needed

        alert = DriftAlert(
            metric=name,
            current_value=current_avg,
            baseline_value=baseline,
            deviation_pct=deviation_pct,
            severity=severity,
            timestamp=datetime.now().isoformat(),
            context=f"Based on last {len(recent)} measurements",
        )
        self._alerts.append(alert)
        self._save_state()

        log.warning(
            "[BehavioralDrift] %s alert: %s deviated %.1f%% from baseline (%.4f -> %.4f)",
            severity.upper(),
            name,
            deviation_pct,
            baseline,
            current_avg,
        )

    def auto_set_baselines(self) -> Dict[str, float]:
        """Auto-set baselines from current metric history."""
        baselines = {}
        for name, history in self._metrics.items():
            if len(history) >= 20:
                baseline = sum(m["value"] for m in history) / len(history)
                baselines[name] = baseline
                self._baselines[name] = baseline

        if baselines:
            self._save_state()
            log.info("[BehavioralDrift] Auto-set baselines for %d metrics", len(baselines))

        return baselines

    def get_alerts(self, limit: int = 10) -> List[DriftAlert]:
        """Get recent drift alerts."""
        return self._alerts[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get drift detection statistics."""
        return {
            "metrics_tracked": list(self._metrics.keys()),
            "baselines": self._baselines,
            "recent_alerts": len(self._alerts),
            "critical_alerts": sum(1 for a in self._alerts if a.severity == "critical"),
            "warning_alerts": sum(1 for a in self._alerts if a.severity == "warning"),
        }


# Global drift detector instance
_detector: Optional[BehavioralDriftDetector] = None


def get_behavioral_drift_detector(repo_dir: Optional[pathlib.Path] = None) -> BehavioralDriftDetector:
    """Get or create the global behavioral drift detector."""
    global _detector
    if _detector is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _detector = BehavioralDriftDetector(repo_dir)
    return _detector
