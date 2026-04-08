"""Enhanced cost tracking for Jo - per-task breakdown and budget estimation."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class CostEntry:
    timestamp: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    task_id: str = ""
    task_type: str = ""


@dataclass
class CostReport:
    total_cost: float
    total_input_tokens: int
    total_output_tokens: int
    by_model: Dict[str, float]
    by_task_type: Dict[str, float]
    rounds: int
    estimated_completion_cost: float = 0.0
    total_chars_saved: int = 0


class CostTracker:
    """Enhanced cost tracking with per-task and per-model breakdowns."""

    PRICING = {
        "openrouter": {
            "openai/gpt-4o": {"input": 2.5, "output": 10.0},
            "openai/gpt-4o-mini": {"input": 0.15, "output": 0.60},
            "anthropic/claude-3.5-sonnet": {"input": 3.0, "output": 15.0},
            "anthropic/claude-3-haiku": {"input": 0.25, "output": 1.25},
            "google/gemini-2.0-flash": {"input": 0.0, "output": 0.0},
            "deepseek/deepseek-chat-v3": {"input": 0.27, "output": 1.10},
        },
    }

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or Path.home() / ".jo_data" / "cost_history.jsonl"
        self.stats_path = self.storage_path.parent / "compression_stats.json"
        self.entries: List[CostEntry] = []
        self.total_chars_saved: int = 0
        self._load()

    def is_enabled(self) -> bool:
        return os.environ.get("OUROBOROS_COST_TRACKING", "1") == "1"

    def record(
        self,
        model: str,
        provider: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        task_id: str = "",
        task_type: str = "",
    ) -> None:
        """Record a cost entry."""
        if not self.is_enabled():
            return

        entry = CostEntry(
            timestamp=datetime.now(timezone.utc).isoformat(),
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            task_id=task_id,
            task_type=task_type,
        )
        self.entries.append(entry)
        self._save()

    def record_from_usage(
        self,
        model: str,
        usage: Dict[str, Any],
        task_id: str = "",
        task_type: str = "",
    ) -> None:
        """Record from LLM usage dict."""
        provider = "openrouter"
        if "anthropic" in model:
            provider = "anthropic"
        elif "openai" in model:
            provider = "openai"

        self.record(
            model=model,
            provider=provider,
            input_tokens=int(usage.get("prompt_tokens", usage.get("tokens_used", {}).get("prompt_tokens", 0))),
            output_tokens=int(usage.get("completion_tokens", usage.get("tokens_used", {}).get("completion_tokens", 0))),
            cost_usd=float(usage.get("cost", 0)),
            task_id=task_id,
            task_type=task_type,
        )

    def record_compression_savings(self, chars_saved: int) -> None:
        """Record how many characters/tokens were saved by internal compression."""
        if not self.is_enabled():
            return
        self.total_chars_saved += chars_saved
        self._save_stats()

    def calculate_burn_rate(self, window_minutes: int = 60) -> float:
        """Calculate cost burn rate (USD/hr) over the last X minutes."""
        if not self.entries:
            return 0.0
        
        now_iso = datetime.now(timezone.utc).isoformat()
        cutoff_dt = datetime.now(timezone.utc).timestamp() - (window_minutes * 60)
        
        recent_cost = 0.0
        for e in self.entries:
            try:
                entry_ts = datetime.fromisoformat(e.timestamp.replace('Z', '+00:00')).timestamp()
                if entry_ts >= cutoff_dt:
                    recent_cost += e.cost
            except Exception:
                pass
        
        return (recent_cost / window_minutes) * 60 if window_minutes > 0 else 0.0

    def generate_report(self, budget_remaining: Optional[float] = None) -> CostReport:
        """Generate a cost report."""
        if not self.entries:
            return CostReport(
                total_cost=0.0,
                total_input_tokens=0,
                total_output_tokens=0,
                by_model={},
                by_task_type={},
                rounds=0,
            )

        total_cost = sum(e.cost_usd for e in self.entries)
        total_input = sum(e.input_tokens for e in self.entries)
        total_output = sum(e.output_tokens for e in self.entries)
        rounds = len(self.entries)

        by_model: Dict[str, float] = {}
        for e in self.entries:
            by_model[e.model] = by_model.get(e.model, 0) + e.cost_usd

        by_task_type: Dict[str, float] = {}
        for e in self.entries:
            if e.task_type:
                by_task_type[e.task_type] = by_task_type.get(e.task_type, 0) + e.cost_usd

        estimated = 0.0
        if budget_remaining and self.entries:
            avg_cost_per_round = total_cost / rounds
            avg_rounds_per_task = 10
            estimated = avg_cost_per_round * avg_rounds_per_task

        return CostReport(
            total_cost=total_cost,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            by_model=by_model,
            by_task_type=by_task_type,
            rounds=rounds,
            estimated_completion_cost=estimated,
            total_chars_saved=self.total_chars_saved,
        )

    def estimate_task_cost(
        self,
        task: str,
        model: str,
        rounds_estimate: int = 10,
    ) -> float:
        """Estimate cost for a task based on model pricing."""
        model_key = model.lower()

        for provider_models in self.PRICING.values():
            for model_name, prices in provider_models.items():
                if model_name in model_key:
                    avg_tokens_per_round = 1000
                    return (
                        (avg_tokens_per_round / 1_000_000 * prices["input"])
                        + (avg_tokens_per_round / 1_000_000 * prices["output"])
                    ) * rounds_estimate

        return 0.0

    def format_report(self, report: CostReport, budget: Optional[float] = None) -> str:
        """Format report for display."""
        lines = [
            "## Cost Summary",
            f"- Total: ${report.total_cost:.4f}",
            f"- Tokens: {report.total_input_tokens:,} in / {report.total_output_tokens:,} out",
            f"- Rounds: {report.rounds}",
            f"- Saved (internal): {report.total_chars_saved:,} chars",
            f"- Burn Rate: ${self.calculate_burn_rate():.4f}/hr",
        ]

        if budget:
            lines.append(f"- Budget remaining: ${budget:.2f}")
            if report.total_cost > 0:
                pct = (report.total_cost / budget) * 100
                lines.append(f"- Spent: {pct:.1f}%")

        if report.by_model:
            lines.append("")
            lines.append("### By Model")
            for model, cost in sorted(report.by_model.items(), key=lambda x: -x[1])[:3]:
                lines.append(f"- {model}: ${cost:.4f}")

        if report.estimated_completion_cost > 0:
            lines.append("")
            lines.append(f"_Estimated completion: ${report.estimated_completion_cost:.4f}_")

        return "\n".join(lines)

    def _load(self) -> None:
        """Load entries and stats from disk."""
        if self.storage_path.exists():
            try:
                with open(self.storage_path, "r") as f:
                    data = [json.loads(line) for line in f if line.strip()]
                    self.entries = [CostEntry(**e) for e in data]
            except Exception as e:
                log.debug(f"Failed to load cost history: {e}")
                self.entries = []
        
        if self.stats_path.exists():
            try:
                stats = json.loads(self.stats_path.read_text())
                self.total_chars_saved = stats.get("total_chars_saved", 0)
            except Exception:
                self.total_chars_saved = 0
 
    def _save_stats(self) -> None:
        """Save compression stats to disk."""
        try:
            self.stats_path.parent.mkdir(parents=True, exist_ok=True)
            self.stats_path.write_text(json.dumps({"total_chars_saved": self.total_chars_saved}))
        except Exception:
            pass

    def _save(self) -> None:
        """Save entries to disk."""
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.storage_path, "a") as f:
                if self.entries:
                    f.write(json.dumps(vars(self.entries[-1])) + "\n")
        except Exception as e:
            log.debug(f"Failed to save cost entry: {e}")


_tracker: Optional[CostTracker] = None


def get_tracker() -> CostTracker:
    """Get singleton tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = CostTracker()
    return _tracker
