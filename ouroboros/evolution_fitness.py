"""Multi-objective fitness function for evolution quality.

Tracks complexity trends and evaluates code improvement candidates.
Blocks evolution if net complexity grows too fast.

Following Principle 5 (Minimalism): under 250 lines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ComplexitySnapshot:
    """Snapshot of codebase complexity at a point in time."""

    timestamp: str
    total_lines: int
    max_module_lines: int
    avg_complexity: float
    critical_violations: int
    test_pass_rate: float = 1.0

    def delta(self, other: "ComplexitySnapshot") -> Dict[str, float]:
        """Compute delta between two snapshots."""
        return {
            "lines_growth": self.total_lines - other.total_lines,
            "max_module_change": self.max_module_lines - other.max_module_lines,
            "complexity_change": self.avg_complexity - other.avg_complexity,
            "violations_change": self.critical_violations - other.critical_violations,
            "test_change": self.test_pass_rate - other.test_pass_rate,
        }


@dataclass
class EvolutionFitness:
    """Multi-objective fitness for code improvement.

    Balances five dimensions:
    - Size: modules under 1000 lines (Principle 5)
    - Complexity: cyclomatic complexity under 15
    - Tests: all tests passing
    - Coupling: low cross-module dependencies
    - Cohesion: high intra-module relatedness

    Usage:
        fitness = EvolutionFitness()
        score = fitness.compute(metrics)
        if fitness.should_allow_evolution():
            # Proceed with evolution
            pass
    """

    size_weight: float = 0.25
    complexity_weight: float = 0.20
    test_weight: float = 0.25
    coupling_weight: float = 0.15
    cohesion_weight: float = 0.15
    max_lines_per_module: int = 1000
    max_complexity: float = 15.0
    max_growth_per_cycle: int = 500
    history: List[ComplexitySnapshot] = field(default_factory=list)

    def compute(self, metrics: Dict[str, Any]) -> float:
        """Compute multi-objective fitness score (0-1, higher is better).

        Args:
            metrics: Dict with keys:
                - max_module_lines: int
                - avg_cyclomatic_complexity: float
                - test_pass_rate: float (0-1)
                - coupling_score: float (0-1, lower is better)
                - cohesion_score: float (0-1, higher is better)

        Returns:
            Fitness score between 0 and 1
        """
        size_score = max(0, 1 - (metrics.get("max_module_lines", 0) / self.max_lines_per_module))
        complexity_score = max(0, 1 - (metrics.get("avg_cyclomatic_complexity", 0) / self.max_complexity))
        test_score = metrics.get("test_pass_rate", 1.0)
        coupling_score = 1 - metrics.get("coupling_score", 0.0)
        cohesion_score = metrics.get("cohesion_score", 0.5)

        return (
            size_score * self.size_weight
            + complexity_score * self.complexity_weight
            + test_score * self.test_weight
            + coupling_score * self.coupling_weight
            + cohesion_score * self.cohesion_weight
        )

    def record_snapshot(self, snapshot: ComplexitySnapshot) -> None:
        """Record a complexity snapshot."""
        self.history.append(snapshot)

    def should_allow_evolution(self) -> bool:
        """Check if evolution should be allowed based on complexity trends.

        Following Principle 5: block if net complexity is growing too fast.
        Every 2-3 cycles must include a simplification.
        """
        if len(self.history) < 2:
            return True

        recent = self.history[-3:] if len(self.history) >= 3 else self.history[-2:]
        total_growth = 0

        for i in range(1, len(recent)):
            delta = recent[i].delta(recent[i - 1])
            total_growth += delta["lines_growth"]

        # Block if >500 lines added without reduction
        if total_growth > self.max_growth_per_cycle:
            log.warning(f"Evolution blocked: net complexity growth {total_growth} > {self.max_growth_per_cycle}")
            return False

        # Block if test pass rate is declining
        if len(recent) >= 2:
            if recent[-1].test_pass_rate < recent[-2].test_pass_rate - 0.1:
                log.warning("Evolution blocked: test pass rate declining")
                return False

        return True

    def get_trend(self) -> Dict[str, Any]:
        """Get complexity trend analysis."""
        if len(self.history) < 2:
            return {"trend": "insufficient_data", "snapshots": len(self.history)}

        first = self.history[0]
        last = self.history[-1]
        delta = last.delta(first)

        if delta["lines_growth"] > 100:
            trend = "growing"
        elif delta["lines_growth"] < -100:
            trend = "shrinking"
        else:
            trend = "stable"

        return {
            "trend": trend,
            "total_snapshots": len(self.history),
            "lines_change": delta["lines_growth"],
            "violations_change": delta["violations_change"],
            "complexity_change": delta["complexity_change"],
            "test_change": delta["test_change"],
        }

    def suggest_focus(self) -> List[str]:
        """Suggest focus areas based on current state."""
        suggestions = []

        if not self.history:
            return ["Record first complexity snapshot"]

        latest = self.history[-1]

        if latest.max_module_lines > self.max_lines_per_module:
            suggestions.append(
                f"Decompose: largest module is {latest.max_module_lines} lines (max {self.max_lines_per_module})"
            )

        if latest.critical_violations > 0:
            suggestions.append(f"Fix {latest.critical_violations} critical violations first")

        if latest.test_pass_rate < 0.9:
            suggestions.append(f"Improve tests: pass rate is {latest.test_pass_rate:.0%}")

        if latest.avg_complexity > self.max_complexity:
            suggestions.append(f"Reduce complexity: avg is {latest.avg_complexity:.1f} (max {self.max_complexity})")

        if not suggestions:
            suggestions.append("System healthy - continue with planned evolution")

        return suggestions


def create_snapshot_from_health(health_report: Dict[str, Any]) -> ComplexitySnapshot:
    """Create a complexity snapshot from health checker output."""
    return ComplexitySnapshot(
        timestamp=datetime.now().isoformat(),
        total_lines=health_report.get("total_lines", 0),
        max_module_lines=health_report.get("max_lines", 0),
        avg_complexity=health_report.get("avg_complexity", 0.0),
        critical_violations=health_report.get("critical_count", 0),
        test_pass_rate=health_report.get("test_pass_rate", 1.0),
    )
