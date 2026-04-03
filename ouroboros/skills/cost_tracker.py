"""
Jo — Cost Tracker.

Token cost tracking and budget management inspired by Claude Code's cost-tracker.ts.
Tracks token usage, estimates costs, and provides budget alerts.

Features:
- Per-session cost tracking
- Per-tool cost breakdown
- Budget alerts at thresholds
- Cost history and trends
- Model-based pricing
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class CostEntry:
    """A single cost tracking entry."""

    timestamp: float
    model: str
    input_tokens: int
    output_tokens: int
    cost: float
    tool_name: str = ""
    session_id: str = ""


@dataclass
class BudgetConfig:
    """Budget configuration."""

    daily_limit: float = 10.0
    session_limit: float = 5.0
    alert_thresholds: List[float] = field(default_factory=lambda: [0.25, 0.5, 0.75, 0.9])


# Model pricing (per 1M tokens)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    "claude-sonnet-4": {"input": 3.0, "output": 15.0},
    "claude-opus-4": {"input": 15.0, "output": 75.0},
    "claude-haiku-3": {"input": 0.25, "output": 1.25},
    "gpt-4o": {"input": 2.5, "output": 10.0},
    "gpt-4o-mini": {"input": 0.15, "output": 0.6},
}


class CostTracker:
    """Token cost tracking and budget management."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.cost_dir = repo_dir / ".jo_state" / "costs"
        self.cost_dir.mkdir(parents=True, exist_ok=True)
        self.entries: List[CostEntry] = []
        self.budget = BudgetConfig()
        self._load_entries()
        self._load_budget()

    def _load_entries(self) -> None:
        """Load cost entries from file."""
        entries_file = self.cost_dir / "cost_entries.json"
        if entries_file.exists():
            try:
                data = json.loads(entries_file.read_text(encoding="utf-8"))
                self.entries = [CostEntry(**e) for e in data]
            except Exception as e:
                log.debug(f"Failed to load cost entries: {e}")

    def _save_entries(self) -> None:
        """Save cost entries to file."""
        entries_file = self.cost_dir / "cost_entries.json"
        data = [
            {
                "timestamp": e.timestamp,
                "model": e.model,
                "input_tokens": e.input_tokens,
                "output_tokens": e.output_tokens,
                "cost": e.cost,
                "tool_name": e.tool_name,
                "session_id": e.session_id,
            }
            for e in self.entries
        ]
        entries_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _load_budget(self) -> None:
        """Load budget configuration."""
        budget_file = self.cost_dir / "budget.json"
        if budget_file.exists():
            try:
                data = json.loads(budget_file.read_text(encoding="utf-8"))
                self.budget = BudgetConfig(**data)
            except Exception:
                pass

    def _save_budget(self) -> None:
        """Save budget configuration."""
        budget_file = self.cost_dir / "budget.json"
        budget_file.write_text(
            json.dumps(
                {
                    "daily_limit": self.budget.daily_limit,
                    "session_limit": self.budget.session_limit,
                    "alert_thresholds": self.budget.alert_thresholds,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def record_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        tool_name: str = "",
        session_id: str = "",
    ) -> CostEntry:
        """Record token usage and calculate cost."""
        pricing = MODEL_PRICING.get(model, {"input": 3.0, "output": 15.0})
        cost = (input_tokens / 1_000_000) * pricing["input"] + (output_tokens / 1_000_000) * pricing["output"]

        entry = CostEntry(
            timestamp=time.time(),
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost=cost,
            tool_name=tool_name,
            session_id=session_id,
        )
        self.entries.append(entry)
        self._save_entries()

        # Check budget alerts
        alerts = self._check_budget_alerts()
        if alerts:
            log.warning(f"Budget alerts: {alerts}")

        return entry

    def _check_budget_alerts(self) -> List[str]:
        """Check if any budget thresholds have been crossed."""
        alerts = []
        daily_cost = self.get_daily_cost()
        session_cost = self.get_session_cost()

        if daily_cost > self.budget.daily_limit:
            alerts.append(f"⚠️ Daily budget exceeded: ${daily_cost:.2f} / ${self.budget.daily_limit:.2f}")

        if session_cost > self.budget.session_limit:
            alerts.append(f"⚠️ Session budget exceeded: ${session_cost:.2f} / ${self.budget.session_limit:.2f}")

        # Check thresholds
        for threshold in self.budget.alert_thresholds:
            limit_cost = self.budget.daily_limit * threshold
            if daily_cost >= limit_cost and daily_cost < limit_cost + 0.01:
                alerts.append(f"📊 Budget alert: {threshold:.0%} of daily limit reached (${daily_cost:.2f})")

        return alerts

    def get_daily_cost(self) -> float:
        """Get total cost for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        return sum(e.cost for e in self.entries if e.timestamp >= today_start)

    def get_session_cost(self, session_id: str = "") -> float:
        """Get total cost for current session."""
        if session_id:
            return sum(e.cost for e in self.entries if e.session_id == session_id)
        # Get last hour as approximation for current session
        hour_ago = time.time() - 3600
        return sum(e.cost for e in self.entries if e.timestamp >= hour_ago)

    def get_cost_by_tool(self) -> Dict[str, float]:
        """Get cost breakdown by tool."""
        costs: Dict[str, float] = {}
        for entry in self.entries:
            tool = entry.tool_name or "direct_api"
            costs[tool] = costs.get(tool, 0) + entry.cost
        return costs

    def get_cost_by_model(self) -> Dict[str, float]:
        """Get cost breakdown by model."""
        costs: Dict[str, float] = {}
        for entry in self.entries:
            costs[entry.model] = costs.get(entry.model, 0) + entry.cost
        return costs

    def get_total_tokens(self) -> Dict[str, int]:
        """Get total token usage."""
        input_tokens = sum(e.input_tokens for e in self.entries)
        output_tokens = sum(e.output_tokens for e in self.entries)
        return {
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        }

    def get_status(self) -> Dict[str, Any]:
        """Get cost tracker status."""
        return {
            "daily_cost": round(self.get_daily_cost(), 4),
            "session_cost": round(self.get_session_cost(), 4),
            "daily_limit": self.budget.daily_limit,
            "session_limit": self.budget.session_limit,
            "total_entries": len(self.entries),
            "cost_by_tool": {k: round(v, 4) for k, v in self.get_cost_by_tool().items()},
            "cost_by_model": {k: round(v, 4) for k, v in self.get_cost_by_model().items()},
            "total_tokens": self.get_total_tokens(),
        }

    def set_budget(self, daily_limit: float, session_limit: float) -> str:
        """Set budget limits."""
        self.budget.daily_limit = daily_limit
        self.budget.session_limit = session_limit
        self._save_budget()
        return f"Budget set: daily=${daily_limit:.2f}, session=${session_limit:.2f}"

    def reset_daily(self) -> str:
        """Reset daily cost tracking."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
        before = len(self.entries)
        self.entries = [e for e in self.entries if e.timestamp < today_start]
        self._save_entries()
        return f"Reset daily tracking. Removed {before - len(self.entries)} entries."


# Global cost tracker instance
_tracker: Optional[CostTracker] = None


def get_cost_tracker(repo_dir: Optional[pathlib.Path] = None) -> CostTracker:
    """Get or create the global cost tracker."""
    global _tracker
    if _tracker is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _tracker = CostTracker(repo_dir)
    return _tracker
