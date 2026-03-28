"""Predictive health — predict failures before they happen.

Simple linear regression on historical health scores.
If a metric is trending down, predict WHEN it will cross the danger line.

Metrics tracked:
- Test pass rate
- Drift violation count
- Module size growth
- Evolution cycle success rate
- Confidence score trend
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

HISTORY_PATH = "~/.jo_data/health_predictions.json"
PREDICTION_HORIZON = 5  # Predict 5 cycles ahead


class HealthPredictor:
    """Predict health trends and alert before failures."""

    def __init__(self, repo_dir: pathlib.Path, drive_root: pathlib.Path):
        self._repo_dir = repo_dir
        self._drive_root = drive_root
        self._history_path = pathlib.Path(HISTORY_PATH).expanduser()
        self._history: List[Dict[str, Any]] = []

    def record_snapshot(self, metrics: Dict[str, float]) -> None:
        """Record a health snapshot for trend analysis."""
        snapshot = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "timestamp": time.time(),
            **metrics,
        }
        self._history.append(snapshot)
        self._save_history()

    def predict_trends(self) -> Dict[str, Any]:
        """Predict health trends for all tracked metrics."""
        if len(self._history) < 3:
            return {"status": "insufficient_data", "snapshots": len(self._history)}

        predictions = {}
        metrics = self._get_tracked_metrics()

        for metric in metrics:
            values = [h.get(metric) for h in self._history if h.get(metric) is not None]
            if len(values) >= 3:
                trend = self._linear_regression(values)
                predictions[metric] = trend

        # Generate alerts
        alerts = []
        for metric, trend in predictions.items():
            if trend["slope"] < 0 and trend["predicted_at_horizon"] < trend["danger_threshold"]:
                alerts.append(
                    {
                        "metric": metric,
                        "severity": "warning",
                        "message": f"{metric} declining, predicted {trend['predicted_at_horizon']:.2f} in {PREDICTION_HORIZON} cycles (danger: {trend['danger_threshold']})",
                        "slope": trend["slope"],
                    }
                )

        return {
            "status": "ok",
            "snapshots": len(self._history),
            "predictions": predictions,
            "alerts": alerts,
            "overall_trend": self._overall_trend(predictions),
        }

    def get_health_report(self) -> str:
        """Generate a predictive health report."""
        trends = self.predict_trends()

        if trends["status"] == "insufficient_data":
            return f"Need more data ({trends['snapshots']} snapshots, need 3+)"

        lines = [
            "## Predictive Health Report",
            "",
            f"**Snapshots:** {trends['snapshots']}",
            f"**Overall trend:** {trends['overall_trend']}",
        ]

        if trends.get("alerts"):
            lines.append("\n### Alerts")
            for alert in trends["alerts"]:
                lines.append(f"- [{alert['severity'].upper()}] {alert['message']}")

        if trends.get("predictions"):
            lines.append("\n### Metric Trends")
            for metric, pred in trends["predictions"].items():
                direction = "up" if pred["slope"] > 0 else "down" if pred["slope"] < 0 else "flat"
                lines.append(
                    f"- {metric}: {direction} (slope={pred['slope']:.4f}, predicted={pred['predicted_at_horizon']:.2f})"
                )

        if not trends.get("alerts"):
            lines.append("\nNo alerts — all metrics trending healthy.")

        return "\n".join(lines)

    def take_snapshot_now(self) -> Dict[str, float]:
        """Take a health snapshot right now."""
        metrics = {}

        # Test pass rate
        try:
            import subprocess

            import sys

            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-q", "--tb=no"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            output = result.stdout + result.stderr
            if "passed" in output:
                # Extract pass count
                import re

                match = re.search(r"(\d+) passed", output)
                if match:
                    metrics["test_pass_count"] = int(match.group(1))
                match = re.search(r"(\d+) failed", output)
                metrics["test_fail_count"] = int(match.group(1)) if match else 0
        except Exception:
            pass

        # Drift violations
        try:
            from ouroboros.drift_detector import DriftDetector

            d = DriftDetector(repo_dir=self._repo_dir, drive_root=self._drive_root)
            violations = d.run_all_checks()
            metrics["drift_violations"] = len(violations)
        except Exception:
            pass

        # Module size (largest module)
        try:
            import pathlib

            max_lines = 0
            for py_file in pathlib.Path(self._repo_dir / "ouroboros").rglob("*.py"):
                lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                max_lines = max(max_lines, lines)
            metrics["max_module_lines"] = max_lines
        except Exception:
            pass

        # Vault notes count
        try:
            vault_dir = self._repo_dir / "vault"
            if vault_dir.exists():
                metrics["vault_note_count"] = len(list(vault_dir.rglob("*.md")))
        except Exception:
            pass

        self.record_snapshot(metrics)
        return metrics

    def _get_tracked_metrics(self) -> List[str]:
        """Get list of metrics that have been tracked."""
        all_metrics = set()
        for h in self._history:
            all_metrics.update(k for k, v in h.items() if isinstance(v, (int, float)) and k not in ("timestamp",))
        return list(all_metrics)

    def _linear_regression(self, values: List[float]) -> Dict[str, float]:
        """Simple linear regression on values."""
        n = len(values)
        if n < 2:
            return {
                "slope": 0,
                "intercept": values[0] if values else 0,
                "predicted_at_horizon": values[0] if values else 0,
                "danger_threshold": 0,
            }

        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator != 0 else 0
        intercept = y_mean - slope * x_mean

        predicted = intercept + slope * (n - 1 + PREDICTION_HORIZON)

        # Danger threshold depends on metric type
        last_value = values[-1]
        danger = last_value * 0.5  # 50% drop is danger

        return {
            "slope": slope,
            "intercept": intercept,
            "current": last_value,
            "predicted_at_horizon": predicted,
            "danger_threshold": danger,
        }

    def _overall_trend(self, predictions: Dict[str, Any]) -> str:
        """Determine overall health trend."""
        if not predictions:
            return "unknown"

        negative = sum(1 for p in predictions.values() if p.get("slope", 0) < -0.01)
        positive = sum(1 for p in predictions.values() if p.get("slope", 0) > 0.01)

        if negative > positive:
            return "declining"
        elif positive > negative:
            return "improving"
        else:
            return "stable"

    def _save_history(self) -> None:
        """Save history to disk."""
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(
                json.dumps(self._history[-100:], indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass
