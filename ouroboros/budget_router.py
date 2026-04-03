"""
Jo — Budget-Aware Model Routing.

Inspired by Claude Code's auto-mode classifier and the awesome-agentic-patterns
catalogue. Routes tasks to appropriate models based on complexity and budget.

Problem: Jo uses the same model for all tasks, wasting budget on simple queries
and under-powering complex ones.

Solution: Classify task complexity, check remaining budget, and route to
the appropriate model tier:
- FAST (haiku): Simple lookups, status checks, formatting
- BALANCED (sonnet): Most coding tasks, debugging, refactoring
- DEEP (opus): Complex architecture, strategic planning, security review

Budget awareness: If daily budget is >80% consumed, downgrade non-critical tasks.
"""

from __future__ import annotations

import logging
import pathlib
from enum import Enum
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


class ModelTier(Enum):
    FAST = "fast"  # Claude Haiku - simple tasks
    BALANCED = "balanced"  # Claude Sonnet - most tasks
    DEEP = "deep"  # Claude Opus - complex tasks


# Task complexity keywords
COMPLEXITY_KEYWORDS = {
    "architect": 3,
    "design": 3,
    "refactor": 2,
    "implement": 2,
    "security": 3,
    "review": 2,
    "migrate": 3,
    "optimize": 2,
    "debug": 2,
    "fix": 1,
    "read": 1,
    "search": 1,
    "list": 1,
    "status": 1,
    "check": 1,
    "explain": 2,
    "analyze": 2,
    "plan": 3,
    "create": 2,
    "build": 2,
    "test": 1,
    "commit": 1,
    "push": 1,
}


class BudgetAwareRouter:
    """Routes tasks to models based on complexity and budget."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._default_model = "anthropic/claude-sonnet-4"
        self._model_map = {
            ModelTier.FAST: "anthropic/claude-haiku-3",
            ModelTier.BALANCED: "anthropic/claude-sonnet-4",
            ModelTier.DEEP: "anthropic/claude-opus-4",
        }

    def classify_complexity(self, task_text: str) -> int:
        """Classify task complexity (1-3)."""
        text_lower = task_text.lower()
        max_score = 1

        for keyword, score in COMPLEXITY_KEYWORDS.items():
            if keyword in text_lower:
                max_score = max(max_score, score)

        # Length-based heuristic
        if len(task_text) > 500:
            max_score = max(max_score, 2)
        if len(task_text) > 1000:
            max_score = max(max_score, 3)

        return max_score

    def get_remaining_budget_ratio(self) -> float:
        """Get remaining daily budget as ratio (0.0-1.0)."""
        try:
            from ouroboros.skills.cost_tracker import get_cost_tracker

            tracker = get_cost_tracker(self.repo_dir)
            daily_cost = tracker.get_daily_cost()
            daily_limit = tracker.budget.daily_limit
            if daily_limit <= 0:
                return 1.0
            return max(0.0, 1.0 - (daily_cost / daily_limit))
        except Exception:
            return 1.0

    def route(self, task_text: str, force_tier: Optional[ModelTier] = None) -> Dict[str, Any]:
        """Route a task to the appropriate model.

        Returns dict with:
        - model: str - The model to use
        - tier: str - The model tier
        - reason: str - Why this model was chosen
        - budget_warning: bool - Whether budget is constrained
        """
        if force_tier:
            tier = force_tier
            reason = f"Force-routed to {tier.value} tier"
        else:
            complexity = self.classify_complexity(task_text)
            tier = {1: ModelTier.FAST, 2: ModelTier.BALANCED, 3: ModelTier.DEEP}.get(complexity, ModelTier.BALANCED)
            reason = f"Complexity {complexity}/3 -> {tier.value} tier"

        # Budget awareness: downgrade if budget is tight
        budget_ratio = self.get_remaining_budget_ratio()
        budget_warning = False

        if budget_ratio < 0.2 and tier != ModelTier.FAST:
            # Critical: only use fast model
            tier = ModelTier.FAST
            reason += " (BUDGET CRITICAL: downgraded to fast)"
            budget_warning = True
        elif budget_ratio < 0.5 and tier == ModelTier.DEEP:
            # Warning: downgrade deep to balanced
            tier = ModelTier.BALANCED
            reason += " (BUDGET WARNING: downgraded to balanced)"
            budget_warning = True

        model = self._model_map.get(tier, self._default_model)

        return {
            "model": model,
            "tier": tier.value,
            "reason": reason,
            "budget_warning": budget_warning,
            "budget_remaining_pct": round(budget_ratio * 100, 1),
            "complexity": self.classify_complexity(task_text),
        }

    def get_stats(self) -> Dict[str, Any]:
        """Get router statistics."""
        return {
            "default_model": self._default_model,
            "model_map": {k.value: v for k, v in self._model_map.items()},
            "current_budget_ratio": round(self.get_remaining_budget_ratio() * 100, 1),
            "complexity_keywords": list(COMPLEXITY_KEYWORDS.keys()),
        }


# Global router instance
_router: Optional[BudgetAwareRouter] = None


def get_budget_router(repo_dir: Optional[pathlib.Path] = None) -> BudgetAwareRouter:
    """Get or create the global budget-aware router."""
    global _router
    if _router is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _router = BudgetAwareRouter(repo_dir)
    return _router
