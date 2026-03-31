"""Evolution benchmark infrastructure for systematic testing.

Measures evolution cycle performance across multiple dimensions.
Inspired by TurboQuant+'s comprehensive benchmark approach.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class BenchmarkResult:
    """Result of a single benchmark run."""

    task: str
    duration_seconds: float
    tokens_used: int
    cost_usd: float
    success: bool
    files_changed: int
    tests_passed: int
    tests_failed: int
    timestamp: str = ""


@dataclass
class EvolutionBenchmark:
    """Benchmark evolution cycle performance.

    Tracks and compares evolution cycle metrics to measure
    improvement over time.

    Usage:
        benchmark = EvolutionBenchmark()
        result = benchmark.run("implement feature X", execute_fn)
        benchmark.save(result)
        comparison = benchmark.compare(baseline, current)
    """

    history: List[BenchmarkResult] = field(default_factory=list)
    persistence_path: Optional[Path] = None

    def __post_init__(self) -> None:
        """Load history if path exists."""
        if self.persistence_path and self.persistence_path.exists():
            self._load()

    def run(
        self,
        task: str,
        execute_fn: Any,
        **kwargs: Any,
    ) -> BenchmarkResult:
        """Run a benchmark.

        Args:
            task: Task description
            execute_fn: Function to execute (returns dict with results)
            **kwargs: Additional arguments for execute_fn

        Returns:
            BenchmarkResult
        """
        start = time.time()
        timestamp = datetime.now().isoformat()

        try:
            result = execute_fn(task, **kwargs)
            duration = time.time() - start

            benchmark = BenchmarkResult(
                task=task,
                duration_seconds=round(duration, 2),
                tokens_used=result.get("tokens_used", 0),
                cost_usd=result.get("cost", 0.0),
                success=result.get("success", False),
                files_changed=result.get("files_changed", 0),
                tests_passed=result.get("tests_passed", 0),
                tests_failed=result.get("tests_failed", 0),
                timestamp=timestamp,
            )
        except Exception as e:
            duration = time.time() - start
            benchmark = BenchmarkResult(
                task=task,
                duration_seconds=round(duration, 2),
                tokens_used=0,
                cost_usd=0.0,
                success=False,
                files_changed=0,
                tests_passed=0,
                tests_failed=1,
                timestamp=timestamp,
            )
            log.warning(f"Benchmark failed for '{task}': {e}")

        self.history.append(benchmark)
        return benchmark

    def compare(
        self,
        baseline: BenchmarkResult,
        current: BenchmarkResult,
    ) -> Dict[str, Any]:
        """Compare two benchmark results."""

        def pct_change(old: float, new: float) -> float:
            if old == 0:
                return 0.0
            return ((new - old) / old) * 100

        return {
            "task": current.task,
            "speed_change": pct_change(baseline.duration_seconds, current.duration_seconds),
            "cost_change": current.cost_usd - baseline.cost_usd,
            "tokens_change": current.tokens_used - baseline.tokens_used,
            "quality_change": current.tests_passed - baseline.tests_passed,
            "success": current.success and not baseline.success,
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get benchmark summary statistics."""
        if not self.history:
            return {"runs": 0}

        successful = [r for r in self.history if r.success]
        failed = [r for r in self.history if not r.success]

        return {
            "total_runs": len(self.history),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(self.history),
            "avg_duration": sum(r.duration_seconds for r in self.history) / len(self.history),
            "avg_cost": sum(r.cost_usd for r in self.history) / len(self.history),
            "total_tokens": sum(r.tokens_used for r in self.history),
            "total_cost": sum(r.cost_usd for r in self.history),
            "best_duration": min(r.duration_seconds for r in self.history),
            "worst_duration": max(r.duration_seconds for r in self.history),
        }

    def format_report(self) -> str:
        """Format benchmark report."""
        summary = self.get_summary()

        if summary.get("runs", 0) == 0:
            return "No benchmark runs recorded"

        lines = [
            "Evolution Benchmark Report",
            "=" * 30,
            f"Total Runs: {summary['total_runs']}",
            f"Success Rate: {summary['success_rate']:.0%}",
            f"Avg Duration: {summary['avg_duration']:.1f}s",
            f"Avg Cost: ${summary['avg_cost']:.4f}",
            f"Total Tokens: {summary['total_tokens']}",
            f"Total Cost: ${summary['total_cost']:.4f}",
            "",
            "Duration Range:",
            f"  Best: {summary['best_duration']:.1f}s",
            f"  Worst: {summary['worst_duration']:.1f}s",
        ]

        return "\n".join(lines)

    def save(self, result: Optional[BenchmarkResult] = None) -> None:
        """Save benchmark result(s) to disk."""
        if not self.persistence_path:
            return

        if result:
            self.history.append(result)

        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
            data = [
                {
                    "task": r.task,
                    "duration_seconds": r.duration_seconds,
                    "tokens_used": r.tokens_used,
                    "cost_usd": r.cost_usd,
                    "success": r.success,
                    "files_changed": r.files_changed,
                    "tests_passed": r.tests_passed,
                    "tests_failed": r.tests_failed,
                    "timestamp": r.timestamp,
                }
                for r in self.history
            ]
            self.persistence_path.write_text(
                json.dumps(data, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            log.warning(f"Failed to save benchmark: {e}")

    def _load(self) -> None:
        """Load benchmark history from disk."""
        if not self.persistence_path:
            return

        try:
            data = json.loads(self.persistence_path.read_text(encoding="utf-8"))
            for item in data:
                self.history.append(BenchmarkResult(**item))
        except Exception as e:
            log.warning(f"Failed to load benchmark: {e}")


def create_benchmark(persistence_path: Optional[str] = None) -> EvolutionBenchmark:
    """Create a benchmark instance."""
    path = Path(persistence_path) if persistence_path else None
    return EvolutionBenchmark(persistence_path=path)
