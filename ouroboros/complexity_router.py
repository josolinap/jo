"""
Ouroboros — Complexity-Based Model Router.

Classifies task complexity and routes to the cheapest capable model.
Inspired by GSD-2's complexity-classifier and model-router pattern.

Complexity tiers:
- light: search, read, list (cheap model)
- standard: implement small feature, fix bug (mid-tier)
- heavy: architecture, refactoring, multi-file changes (best model)
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class ComplexityTier(Enum):
    LIGHT = "light"
    STANDARD = "standard"
    HEAVY = "heavy"


@dataclass
class ModelConfig:
    name: str
    tier: ComplexityTier
    cost_per_1k_input: float
    cost_per_1k_output: float
    provider: str = "openrouter"


@dataclass
class RoutingDecision:
    model: str
    tier: ComplexityTier
    reason: str
    estimated_cost_factor: float = 1.0


LIGHT_KEYWORDS = frozenset(
    {
        "search",
        "find",
        "list",
        "read",
        "show",
        "get",
        "check",
        "verify",
        "count",
        "describe",
        "explain",
        "what",
        "where",
        "who",
        "when",
        "status",
        "log",
        "history",
        "summary",
    }
)

HEAVY_KEYWORDS = frozenset(
    {
        "refactor",
        "architect",
        "redesign",
        "restructure",
        "decompose",
        "migrate",
        "rewrite",
        "optimize",
        "scale",
        "integrate",
        "multi-file",
        "cross-module",
        "system-wide",
        "architecture",
        "implement.*feature",
        "create.*module",
        "add.*system",
    }
)

COMPLEXITY_SIGNALS = [
    (re.compile(r"(?i)\b(refactor|redesign|restructure|architect)\b"), 3),
    (re.compile(r"(?i)\b(multi-file|cross-module|system-wide)\b"), 3),
    (re.compile(r"(?i)\b(implement|create|add)\b.*\b(feature|module|system|service)\b"), 2),
    (re.compile(r"(?i)\b(fix|patch|update|modify)\b"), 1),
    (re.compile(r"(?i)\b(search|find|list|read|show|get|check)\b"), 0),
    (re.compile(r"(?i)\b(test|verify|validate)\b.*\b(all|every|entire)\b"), 2),
    (re.compile(r"(?i)\b(break|split|extract|move)\b.*\b(into|to)\b"), 2),
]


class ComplexityClassifier:
    """Classifies task complexity based on description."""

    def __init__(self):
        self._signals = COMPLEXITY_SIGNALS

    def classify(self, task_description: str, file_count: int = 0, function_count: int = 0) -> ComplexityTier:
        score = 0
        desc_lower = task_description.lower()

        for keyword in LIGHT_KEYWORDS:
            if keyword in desc_lower:
                score -= 1

        for keyword in HEAVY_KEYWORDS:
            if re.search(keyword, desc_lower):
                score += 2

        for pattern, weight in self._signals:
            if pattern.search(task_description):
                score += weight

        score += file_count * 0.5
        score += function_count * 0.2

        if score <= 0:
            return ComplexityTier.LIGHT
        elif score <= 3:
            return ComplexityTier.STANDARD
        else:
            return ComplexityTier.HEAVY


class ModelRouter:
    """Routes tasks to models based on complexity and budget."""

    def __init__(self):
        self.classifier = ComplexityClassifier()
        self._models: Dict[ComplexityTier, ModelConfig] = {
            ComplexityTier.LIGHT: ModelConfig(
                name=os.environ.get("OUROBOROS_MODEL_LIGHT", "openrouter/google/gemini-2.0-flash-001"),
                tier=ComplexityTier.LIGHT,
                cost_per_1k_input=0.0,
                cost_per_1k_output=0.0,
            ),
            ComplexityTier.STANDARD: ModelConfig(
                name=os.environ.get("OUROBOROS_MODEL", "openrouter/anthropic/claude-sonnet-4"),
                tier=ComplexityTier.STANDARD,
                cost_per_1k_input=3.0,
                cost_per_1k_output=15.0,
            ),
            ComplexityTier.HEAVY: ModelConfig(
                name=os.environ.get("OUROBOROS_MODEL_CODE", "openrouter/anthropic/claude-sonnet-4"),
                tier=ComplexityTier.HEAVY,
                cost_per_1k_input=3.0,
                cost_per_1k_output=15.0,
            ),
        }
        self._budget_remaining: float = float(os.environ.get("TOTAL_BUDGET", "50"))
        self._routing_history: List[Dict[str, Any]] = []

    def set_models(self, light: str = "", standard: str = "", heavy: str = "") -> None:
        if light:
            self._models[ComplexityTier.LIGHT].name = light
        if standard:
            self._models[ComplexityTier.STANDARD].name = standard
        if heavy:
            self._models[ComplexityTier.HEAVY].name = heavy

    def set_budget(self, remaining: float) -> None:
        self._budget_remaining = remaining

    def route(self, task_description: str, file_count: int = 0, function_count: int = 0) -> RoutingDecision:
        tier = self.classifier.classify(task_description, file_count, function_count)
        model = self._models[tier]

        if self._budget_remaining < 1.0 and tier != ComplexityTier.LIGHT:
            tier = ComplexityTier.LIGHT
            model = self._models[tier]
            reason = f"Budget pressure: downgraded to {tier.value} (budget=${self._budget_remaining:.2f})"
        else:
            reason = f"Task classified as {tier.value} complexity"

        decision = RoutingDecision(
            model=model.name,
            tier=tier,
            reason=reason,
            estimated_cost_factor=1.0
            if tier == ComplexityTier.LIGHT
            else (3.0 if tier == ComplexityTier.STANDARD else 5.0),
        )

        self._routing_history.append(
            {
                "task": task_description[:80],
                "tier": tier.value,
                "model": model.name,
                "budget": self._budget_remaining,
            }
        )
        return decision

    def get_stats(self) -> Dict[str, Any]:
        if not self._routing_history:
            return {"total_routed": 0}
        tier_counts = {}
        for r in self._routing_history:
            tier = r["tier"]
            tier_counts[tier] = tier_counts.get(tier, 0) + 1
        return {
            "total_routed": len(self._routing_history),
            "by_tier": tier_counts,
            "current_models": {t.value: m.name for t, m in self._models.items()},
            "budget_remaining": self._budget_remaining,
        }

    def suggest_model(self, task_description: str) -> str:
        decision = self.route(task_description)
        return f"Model: {decision.model}\nTier: {decision.tier.value}\nReason: {decision.reason}"


_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    global _router
    if _router is None:
        _router = ModelRouter()
    return _router


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def complexity_route(ctx, task: str, file_count: int = 0) -> str:
        return get_router().suggest_model(task)

    def complexity_classify(ctx, task: str) -> str:
        tier = get_router().classifier.classify(task)
        return f"Complexity: {tier.value}"

    def complexity_stats(ctx) -> str:
        return json.dumps(get_router().get_stats(), indent=2)

    def complexity_set_models(ctx, light: str = "", standard: str = "", heavy: str = "") -> str:
        router = get_router()
        router.set_models(light, standard, heavy)
        return f"Models updated: light={router._models[ComplexityTier.LIGHT].name}, standard={router._models[ComplexityTier.STANDARD].name}, heavy={router._models[ComplexityTier.HEAVY].name}"

    return [
        ToolEntry(
            "complexity_route",
            {
                "name": "complexity_route",
                "description": "Route a task to the optimal model based on complexity. Use before expensive operations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"},
                        "file_count": {"type": "integer", "default": 0, "description": "Number of files involved"},
                    },
                    "required": ["task"],
                },
            },
            complexity_route,
        ),
        ToolEntry(
            "complexity_classify",
            {
                "name": "complexity_classify",
                "description": "Classify a task's complexity tier (light/stANDARD/heavy).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"},
                    },
                    "required": ["task"],
                },
            },
            complexity_classify,
        ),
        ToolEntry(
            "complexity_stats",
            {
                "name": "complexity_stats",
                "description": "Get routing statistics and current model configuration.",
                "parameters": {"type": "object", "properties": {}},
            },
            complexity_stats,
        ),
        ToolEntry(
            "complexity_set_models",
            {
                "name": "complexity_set_models",
                "description": "Override model selection for complexity tiers.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "light": {"type": "string", "default": "", "description": "Model for light tasks"},
                        "standard": {"type": "string", "default": "", "description": "Model for standard tasks"},
                        "heavy": {"type": "string", "default": "", "description": "Model for heavy tasks"},
                    },
                },
            },
            complexity_set_models,
        ),
    ]
