"""Delta Evaluation — Formal quantification of improvement quality.

Inspired by SAFLA's delta evaluation system.
Measures whether evolution cycles actually improve Jo.

Formula:
    Δ_total = α₁ × Δ_performance + α₂ × Δ_efficiency + α₃ × Δ_stability + α₄ × Δ_capability

Where:
    Δ_performance = (current_reward - previous_reward) / max(tokens_used, 1)
    Δ_efficiency  = (current_throughput - previous_throughput) / max(resource_used, 1)
    Δ_stability   = 1 - divergence_score
    Δ_capability  = new_capabilities / max(total_capabilities, 1)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.utils import utc_now_iso

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DeltaResult:
    """Result of a delta evaluation."""

    total_delta: float
    performance_delta: float
    efficiency_delta: float
    stability_delta: float
    capability_delta: float
    is_improvement: bool
    context: str
    timestamp: str


@dataclass
class EvaluationHistory:
    """Tracks evaluation history for trend analysis."""

    entries: List[Dict[str, Any]] = field(default_factory=list)
    max_entries: int = 100

    def add(self, result: DeltaResult) -> None:
        self.entries.append(
            {
                "total_delta": result.total_delta,
                "is_improvement": result.is_improvement,
                "context": result.context,
                "timestamp": result.timestamp,
            }
        )
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries :]

    def trend(self, window: int = 10) -> float:
        """Return trend (-1 to +1) over last N entries."""
        recent = self.entries[-window:]
        if not recent:
            return 0.0
        improvements = sum(1 for e in recent if e["is_improvement"])
        return (improvements / len(recent)) * 2 - 1  # -1 to +1


class DeltaEvaluator:
    """Quantifies the quality of changes (evolution cycles, refactors, etc.)."""

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        history_path: Optional[Path] = None,
    ):
        self.weights = weights or {
            "performance": 0.35,
            "efficiency": 0.25,
            "stability": 0.25,
            "capability": 0.15,
        }
        self.history = EvaluationHistory()
        self._history_path = history_path
        if history_path and history_path.exists():
            self._load_history()

    def evaluate(self, data: Dict[str, Any], context: str = "") -> DeltaResult:
        """Evaluate delta from structured data.

        Args:
            data: Dict with keys:
                - performance: {current_reward, previous_reward, tokens_used}
                - efficiency: {current_throughput, previous_throughput, resource_used}
                - stability: {divergence_score} (0-1, lower is more stable)
                - capability: {new_capabilities, total_capabilities}
            context: Description of what was evaluated

        Returns:
            DeltaResult with total_delta and component deltas
        """
        perf = self._calc_performance(data.get("performance", {}))
        eff = self._calc_efficiency(data.get("efficiency", {}))
        stab = self._calc_stability(data.get("stability", {}))
        cap = self._calc_capability(data.get("capability", {}))

        total = (
            self.weights["performance"] * perf
            + self.weights["efficiency"] * eff
            + self.weights["stability"] * stab
            + self.weights["capability"] * cap
        )

        result = DeltaResult(
            total_delta=round(total, 4),
            performance_delta=round(perf, 4),
            efficiency_delta=round(eff, 4),
            stability_delta=round(stab, 4),
            capability_delta=round(cap, 4),
            is_improvement=total > 0,
            context=context,
            timestamp=utc_now_iso(),
        )

        self.history.add(result)
        if self._history_path:
            self._save_history()

        return result

    def evaluate_change(
        self,
        lines_added: int,
        lines_removed: int,
        tests_passing: int,
        tests_failing: int,
        tools_added: int = 0,
        tools_removed: int = 0,
        context: str = "",
    ) -> DeltaResult:
        """Evaluate a code change using concrete metrics."""
        total_changes = max(lines_added + lines_removed, 1)
        test_total = max(tests_passing + tests_failing, 1)

        return self.evaluate(
            {
                "performance": {
                    "current_reward": tests_passing / test_total,
                    "previous_reward": 1.0 if tests_failing == 0 else 0.8,
                    "tokens_used": total_changes,
                },
                "efficiency": {
                    "current_throughput": max(lines_removed - lines_added, 0) + 1,
                    "previous_throughput": 1,
                    "resource_used": total_changes,
                },
                "stability": {
                    "divergence_score": tests_failing / test_total,
                },
                "capability": {
                    "new_capabilities": max(tools_added - tools_removed, 0),
                    "total_capabilities": max(tools_added + tools_removed, 1),
                },
            },
            context=context,
        )

    def get_report(self) -> str:
        """Get human-readable report of evaluation history."""
        trend = self.history.trend()
        entries = self.history.entries
        if not entries:
            return "No evaluations recorded yet."

        improvements = sum(1 for e in entries if e["is_improvement"])
        avg_delta = sum(e["total_delta"] for e in entries) / len(entries)

        lines = [
            "## Delta Evaluation Report",
            "",
            f"**Total evaluations:** {len(entries)}",
            f"**Improvements:** {improvements}/{len(entries)} ({improvements / max(len(entries), 1) * 100:.0f}%)",
            f"**Average delta:** {avg_delta:+.4f}",
            f"**Trend (last 10):** {'improving' if trend > 0.2 else 'declining' if trend < -0.2 else 'stable'} ({trend:+.2f})",
        ]
        return "\n".join(lines)

    def _calc_performance(self, data: Dict[str, Any]) -> float:
        current = data.get("current_reward", 0.0)
        previous = data.get("previous_reward", 0.0)
        tokens = max(data.get("tokens_used", 1), 1)
        raw = (current - previous) / tokens
        return self._normalize(raw)

    def _calc_efficiency(self, data: Dict[str, Any]) -> float:
        current = data.get("current_throughput", 0.0)
        previous = data.get("previous_throughput", 0.0)
        resource = max(data.get("resource_used", 1), 1)
        if previous == 0:
            return 0.0
        raw = (current - previous) / (previous * resource)
        return self._normalize(raw)

    def _calc_stability(self, data: Dict[str, Any]) -> float:
        divergence = data.get("divergence_score", 0.0)
        return max(0.0, min(1.0, 1.0 - divergence))

    def _calc_capability(self, data: Dict[str, Any]) -> float:
        new = data.get("new_capabilities", 0)
        total = max(data.get("total_capabilities", 1), 1)
        return min(new / total, 1.0)

    @staticmethod
    def _normalize(value: float) -> float:
        """Normalize a value to [-1, 1] range using tanh-like clamping."""
        return max(-1.0, min(1.0, value))

    def _load_history(self) -> None:
        try:
            raw = json.loads(self._history_path.read_text(encoding="utf-8"))
            self.history.entries = raw.get("entries", [])[-self.history.max_entries :]
        except Exception as e:
            log.debug("Failed to load delta history: %s", e)

    def _save_history(self) -> None:
        try:
            self._history_path.parent.mkdir(parents=True, exist_ok=True)
            self._history_path.write_text(
                json.dumps({"entries": self.history.entries}, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning("Failed to save delta history: %s", e)
