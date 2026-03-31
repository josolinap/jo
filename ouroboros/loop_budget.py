"""Budget and setup functions for LLM loops.

Extracted from loop.py (Principle 5: Minimalism).
Handles: budget checks, cost estimation, setup, context enrichment.
"""

from __future__ import annotations

import logging
import os
import pathlib
import queue
import threading
from typing import Any, Callable, Dict, List, Optional, Tuple

from ouroboros.llm import LLMClient, normalize_reasoning_effort
from ouroboros.tools.registry import ToolRegistry
from ouroboros.utils import estimate_tokens
from ouroboros.context import auto_summarize_if_needed
from ouroboros.tool_executor import _StatefulToolExecutor
from ouroboros.traceability import get_traceability_layer

log = logging.getLogger(__name__)

# Feature flags
USE_CONTEXT_ENRICHMENT = os.environ.get("OUROBOROS_ENRICH_CONTEXT", "1") == "1"
USE_TASK_GRAPH = os.environ.get("OUROBOROS_TASK_GRAPH", "0") == "1"

# Pricing from OpenRouter API
_MODEL_PRICING_STATIC = {
    "anthropic/claude-opus-4.6": (5.0, 0.5, 25.0),
    "anthropic/claude-opus-4": (15.0, 1.5, 75.0),
    "anthropic/claude-sonnet-4": (3.0, 0.30, 15.0),
    "anthropic/claude-sonnet-4.6": (3.0, 0.30, 15.0),
    "anthropic/claude-sonnet-4.5": (3.0, 0.30, 15.0),
    "openai/o3": (2.0, 0.50, 8.0),
    "openai/o3-pro": (20.0, 1.0, 80.0),
    "openai/o4-mini": (1.10, 0.275, 4.40),
    "openai/gpt-4.1": (2.0, 0.50, 8.0),
    "openai/gpt-5.2": (1.75, 0.175, 14.0),
    "openai/gpt-5.2-codex": (1.75, 0.175, 14.0),
    "google/gemini-2.5-pro-preview": (1.25, 0.125, 10.0),
    "google/gemini-3-pro-preview": (2.0, 0.20, 12.0),
    "x-ai/grok-3-mini": (0.30, 0.03, 0.50),
    "qwen/qwen3.5-plus-02-15": (0.40, 0.04, 2.40),
}

_pricing_fetched = False
_cached_pricing = None
_pricing_lock = threading.Lock()


def _get_pricing() -> Dict[str, Tuple[float, float, float]]:
    """Get model pricing with lazy loading and fallback to static data."""
    global _pricing_fetched, _cached_pricing

    if _pricing_fetched:
        return _cached_pricing or _MODEL_PRICING_STATIC

    with _pricing_lock:
        if _pricing_fetched:
            return _cached_pricing or _MODEL_PRICING_STATIC

        _pricing_fetched = True
        _cached_pricing = dict(_MODEL_PRICING_STATIC)

        try:
            from ouroboros.llm import fetch_openrouter_pricing

            _live = fetch_openrouter_pricing()
            if _live and len(_live) > 5:
                _cached_pricing.update(_live)
        except Exception as e:
            log.warning("Failed to sync pricing from OpenRouter: %s", e)
            _pricing_fetched = False

        return _cached_pricing


def _estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0, cache_write_tokens: int = 0
) -> float:
    """Estimate cost from token counts using known pricing."""
    model_pricing = _get_pricing()
    pricing = model_pricing.get(model)
    if not pricing:
        best_match = None
        best_length = 0
        for key, val in model_pricing.items():
            if model and model.startswith(key):
                if len(key) > best_length:
                    best_match = val
                    best_length = len(key)
        pricing = best_match
    if not pricing:
        return 0.0
    input_price, cached_price, output_price = pricing
    regular_input = max(0, prompt_tokens - cached_tokens)
    cost = (
        regular_input * input_price / 1_000_000
        + cached_tokens * cached_price / 1_000_000
        + completion_tokens * output_price / 1_000_000
    )
    return round(cost, 6)


def _get_budget_status(
    budget_remaining_usd: Optional[float], accumulated_usage: Dict[str, Any]
) -> Tuple[Optional[float], Optional[float]]:
    """Calculate budget percentage and cost, return None if no budget."""
    if budget_remaining_usd is None:
        return None, None

    total_cost = _estimate_cost(
        accumulated_usage.get("model", ""),
        accumulated_usage.get("prompt_tokens", 0),
        accumulated_usage.get("completion_tokens", 0),
        accumulated_usage.get("cached_tokens", 0),
        accumulated_usage.get("cache_write_tokens", 0),
    )
    budget_pct = total_cost / budget_remaining_usd if budget_remaining_usd > 0 else 1.0
    return budget_pct, total_cost


def _handle_context_enrichment(
    messages: List[Dict[str, Any]],
    drive_root: Optional[pathlib.Path],
    emit_progress: Callable[[str], None],
) -> List[Dict[str, Any]]:
    """Handle auto-summarization and context enrichment if needed."""
    if drive_root is None or len(messages) == 0:
        return messages

    context_limit = int(os.environ.get("OUROBOROS_CONTEXT_LIMIT", "120000"))
    messages, summarize_info = auto_summarize_if_needed(messages, drive_root, context_limit)
    if summarize_info.get("auto_summarized"):
        emit_progress(f"[Memory] Auto-summarized: {summarize_info.get('reason', '')}")

    if USE_CONTEXT_ENRICHMENT:
        from ouroboros.context_enricher import enrich_messages

        task_text = ""
        for m in messages:
            if m.get("role") == "user":
                task_text = m.get("content", "")
                break
        if task_text:
            task_type = (
                "code"
                if any(kw in task_text.lower() for kw in ["code", "file", "function", "class", "implement"])
                else "general"
            )
            repo_dir = pathlib.Path(os.environ.get("REPO_DIR", "."))
            enriched_messages = enrich_messages(messages, task_text, task_type, repo_dir)
            if enriched_messages != messages:
                emit_progress("[Context] Enriched with additional context")
                return enriched_messages

    return messages


def _maybe_inject_self_check(
    round_idx: int,
    MAX_ROUNDS: int,
    messages: List[Dict[str, Any]],
    accumulated_usage: Dict[str, Any],
    emit_progress: Callable[[str], None],
) -> None:
    """Inject periodic self-check messages."""
    if round_idx % 10 == 0 and round_idx > 0:
        total_cost = _estimate_cost(
            accumulated_usage.get("model", ""),
            accumulated_usage.get("prompt_tokens", 0),
            accumulated_usage.get("completion_tokens", 0),
        )
        check_msg = (
            f"[SELF-CHECK] Round {round_idx}/{MAX_ROUNDS}. "
            f"Cost so far: ${total_cost:.4f}. "
            f"Are you making progress? If stuck, consider wrapping up."
        )
        messages.append({"role": "system", "content": check_msg})


def _maybe_build_task_graph(task: str) -> Optional[Any]:
    """Build task graph for complex multi-step tasks."""
    if not USE_TASK_GRAPH:
        return None

    try:
        from ouroboros.task_graph import decompose_into_graph

        graph = decompose_into_graph(task)
        if graph:
            log.info(f"[TaskGraph] Decomposed task into {len(graph.nodes)} subtasks")
            return graph
    except Exception as e:
        log.warning(f"[TaskGraph] Failed to decompose task: {e}")

    return None
