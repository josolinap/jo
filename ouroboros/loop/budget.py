"""Budget and cost management module for LLM loops.

This module provides functions for estimating costs, checking budget limits,
and handling budget exceeded scenarios. Extracted from ouroboros/loop.py.
"""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, Tuple

from ouroboros.utils import utc_now_iso, append_jsonl

log = logging.getLogger(__name__)

# Pricing from OpenRouter API (2026-02-17). Update periodically via /api/v1/models.
_MODEL_PRICING_STATIC: Dict[str, Tuple[float, float, float]] = {
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
    """Estimate cost from token counts using known pricing. Returns 0 if model unknown."""
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
    budget_remaining_usd: float,
    accumulated_usage: float,
    llm_trace: dict,
    emit_progress: callable,
    task_type: str,
    round_idx: int,
) -> str:
    """Get budget status and emit warnings if needed."""
    # Estimate cost for next round (conservative estimate)
    # We don't know tokens yet, so we check remaining budget
    if budget_remaining_usd <= 0:
        return "exceeded"
    
    # Log budget status to trace
    llm_trace.setdefault("budget", {})
    llm_trace["budget"]["remaining_usd"] = budget_remaining_usd
    llm_trace["budget"]["accumulated_usage"] = accumulated_usage
    
    # Warning thresholds
    total_budget = budget_remaining_usd + accumulated_usage if accumulated_usage else budget_remaining_usd
    if total_budget > 0:
        remaining_pct = (budget_remaining_usd / total_budget) * 100
        if remaining_pct < 20:
            emit_progress(f"💰 Budget warning: {remaining_pct:.0f}% remaining (${budget_remaining_usd:.4f})")
    
    return "ok"


def _handle_budget_exceeded(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost: float,
    budget_remaining_usd: float,
    accumulated_usage: float,
    task_id: str,
    messages: list,
    emit_progress: callable,
) -> str:
    """Handle budget exceeded - return a message to end the task."""
    log.error(
        "Budget exceeded: remaining=%.4f, estimated_cost=%.6f, model=%s",
        budget_remaining_usd,
        estimated_cost,
        model,
    )
    emit_progress("💸 Budget exceeded - cannot continue")
    
    # Return a final message to the user
    return (
        f"Task stopped due to budget constraints.\n"
        f"Estimated cost: ${estimated_cost:.6f}\n"
        f"Remaining budget: ${budget_remaining_usd:.4f}\n"
        f"Accumulated usage: ${accumulated_usage:.4f}"
    )


def _check_budget_limits(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    budget_remaining_usd: float,
    accumulated_usage: float,
    emit_progress: callable,
    llm_trace: dict,
    task_type: str,
    round_idx: int,
    task_id: str,
    messages: list,
) -> str | None:
    """Check budget and return None if OK, or final message if exceeded."""
    estimated_cost = _estimate_cost(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    
    # Check if this would exceed budget
    new_remaining = budget_remaining_usd - estimated_cost
    if new_remaining <= 0:
        return _handle_budget_exceeded(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_cost=estimated_cost,
            budget_remaining_usd=budget_remaining_usd,
            accumulated_usage=accumulated_usage,
            task_id=task_id,
            messages=messages,
            emit_progress=emit_progress,
        )
    
    # Update trace
    llm_trace.setdefault("budget", {})
    llm_trace["budget"].update({
        "estimated_cost": estimated_cost,
        "remaining_after": new_remaining,
        "round": round_idx,
    })
    
    # Warning if < 20% left
    total_budget = budget_remaining_usd + accumulated_usage if accumulated_usage else budget_remaining_usd
    if total_budget > 0:
        remaining_pct = (new_remaining / total_budget) * 100
        if remaining_pct < 20:
            emit_progress(f"💰 {remaining_pct:.0f}% budget remaining (${new_remaining:.4f})")
    
    return None

import logging
import threading
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Static model pricing data (per 1K tokens)
# Format: {model_name: {prompt: float, completion: float, cached: float, cache_write: float}}
_MODEL_PRICING_STATIC: Dict[str, Dict[str, float]] = {
    # OpenAI models
    "gpt-4": {"prompt": 0.03, "completion": 0.06},
    "gpt-4-turbo": {"prompt": 0.01, "completion": 0.03},
    "gpt-4o": {"prompt": 0.005, "completion": 0.015},
    "gpt-4o-mini": {"prompt": 0.00015, "completion": 0.0006},
    "gpt-3.5-turbo": {"prompt": 0.001, "completion": 0.002},
    # Anthropic models (with cache support)
    "claude-3-opus": {"prompt": 0.015, "completion": 0.075, "cached": 0.0015, "cache_write": 0.0015},
    "claude-3-sonnet": {"prompt": 0.003, "completion": 0.015, "cached": 0.0003, "cache_write": 0.0003},
    "claude-3-haiku": {"prompt": 0.00025, "completion": 0.00125, "cached": 0.000025, "cache_write": 0.000025},
    # Default fallback (should be overridden by dynamic fetch if implemented)
    "default": {"prompt": 0.001, "completion": 0.002},
}

# Global caching for pricing data
_pricing_fetched = False
_cached_pricing: Dict[str, Dict[str, float]] = {}
_pricing_lock = threading.Lock()


class BudgetExceededError(Exception):
    """Raised when budget limits are exceeded."""

    def __init__(self, message: str, remaining_usd: float, estimated_cost: float, round_idx: int) -> None:
        super().__init__(message)
        self.remaining_usd = remaining_usd
        self.estimated_cost = estimated_cost
        self.round_idx = round_idx


@dataclass
class BudgetResult:
    """Result of budget check.

    Attributes:
        status: One of 'ok', 'warning', 'exceeded'
        remaining_usd: Remaining budget after estimated cost
        accumulated_usage: Total accumulated usage including estimated cost
        estimated_cost: Cost of current request
        round_idx: Current round index
    """
    status: str
    remaining_usd: float
    accumulated_usage: float
    estimated_cost: float
    round_idx: int



def _get_pricing() -> Dict[str, Dict[str, float]]:
    """Get model pricing data with caching.

    Returns:
        Dictionary mapping model names to their pricing information.
        Pricing is per 1K tokens for prompt, completion, cached, and cache_write.
    """
    global _pricing_fetched, _cached_pricing
    
    with _pricing_lock:
        if not _pricing_fetched:
            # In a real implementation, this might fetch from an external API
            # For now, we use the static data
            _cached_pricing = _MODEL_PRICING_STATIC.copy()
            _pricing_fetched = True
            logger.debug("Pricing data loaded from static configuration")
        
    return _cached_pricing



def _estimate_cost(
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
) -> float:
    """Estimate cost for a model request.

    Args:
        model: Model identifier
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        cached_tokens: Number of cached tokens (for models with caching)
        cache_write_tokens: Number of tokens written to cache

    Returns:
        Estimated cost in USD
    """
    pricing_data = _get_pricing()
    model_pricing = pricing_data.get(model, pricing_data.get("default", {}))
    
    # Get individual pricing components (default to 0 if not specified)
    prompt_rate = model_pricing.get("prompt", 0.0)
    completion_rate = model_pricing.get("completion", 0.0)
    cached_rate = model_pricing.get("cached", 0.0)
    cache_write_rate = model_pricing.get("cache_write", 0.0)
    
    # Calculate costs (rates are per 1K tokens)
    prompt_cost = (prompt_tokens / 1000.0) * prompt_rate
    completion_cost = (completion_tokens / 1000.0) * completion_rate
    cached_cost = (cached_tokens / 1000.0) * cached_rate
    cache_write_cost = (cache_write_tokens / 1000.0) * cache_write_rate
    
    total_cost = prompt_cost + completion_cost + cached_cost + cache_write_cost
    
    logger.debug(
        f"Cost estimate for {model}: prompt={prompt_tokens} tokens @ ${prompt_rate}/1K = ${prompt_cost:.6f}, "
        f"completion={completion_tokens} tokens @ ${completion_rate}/1K = ${completion_cost:.6f}, "
        f"cached={cached_tokens} tokens @ ${cached_rate}/1K = ${cached_cost:.6f}, "
        f"cache_write={cache_write_tokens} tokens @ ${cache_write_rate}/1K = ${cache_write_cost:.6f}, "
        f"total=${total_cost:.6f}"
    )
    
    return total_cost



def _get_budget_status(
    budget_remaining_usd: float, accumulated_usage: float, round_idx: int
) -> str:
    """Determine budget status based on remaining amount and usage.

    Args:
        budget_remaining_usd: Current remaining budget in USD
        accumulated_usage: Total accumulated usage in USD
        round_idx: Current round index (for logging)

    Returns:
        Status string: 'ok', 'warning', or 'exceeded'
    """
    # Calculate total budget (remaining + used)
    total_budget = budget_remaining_usd + accumulated_usage
    
    if total_budget > 0:
        remaining_percent = (budget_remaining_usd / total_budget) * 100
    else:
        remaining_percent = 0.0
    
    # Determine status
    if budget_remaining_usd <= 0:
        status = "exceeded"
    elif remaining_percent < 10.0:  # Less than 10% remaining
        status = "warning"
    else:
        status = "ok"
    
    logger.debug(
        f"Budget status at round {round_idx}: ${budget_remaining_usd:.4f} remaining "
        f"({remaining_percent:.1f}% of ${total_budget:.4f} total), status={status}"
    )
    
    return status



def _handle_budget_exceeded(
    budget_remaining_usd: float,
    accumulated_usage: float,
    round_idx: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
    estimated_cost: float,
) -> None:
    """Handle budget exceeded scenario.

    Args:
        budget_remaining_usd: Current remaining budget
        accumulated_usage: Total accumulated usage
        round_idx: Current round index
        model: Model being used
        prompt_tokens: Prompt token count
        completion_tokens: Completion token count
        cached_tokens: Cached token count
        cache_write_tokens: Cache write token count
        estimated_cost: Estimated cost of current request

    Raises:
        BudgetExceededError: Always raised to signal budget exhaustion
    """
    total_budget = budget_remaining_usd + accumulated_usage
    
    error_msg = (
        f"Budget exceeded at round {round_idx}. "
        f"Model: {model}, Estimated cost: ${estimated_cost:.6f}, "
        f"Remaining: ${budget_remaining_usd:.4f}, Accumulated: ${accumulated_usage:.4f}, "
        f"Total budget: ${total_budget:.4f}"
    )
    
    logger.error(error_msg)
    raise BudgetExceededError(error_msg, budget_remaining_usd, estimated_cost, round_idx)



def _check_budget_limits(
    budget_remaining_usd: float,
    accumulated_usage: float,
    round_idx: int,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    cached_tokens: int,
    cache_write_tokens: int,
) -> BudgetResult:
    """Check budget limits and determine if operation can proceed.

    This is the main budget check function that estimates the cost of the
    current request and determines if it would exceed the budget.

    Args:
        budget_remaining_usd: Current remaining budget in USD
        accumulated_usage: Total accumulated usage in USD
        round_idx: Current round index
        model: Model identifier
        prompt_tokens: Number of prompt tokens
        completion_tokens: Number of completion tokens
        cached_tokens: Number of cached tokens
        cache_write_tokens: Number of tokens written to cache

    Returns:
        BudgetResult object with status and updated budget values
        If status is 'exceeded', the caller should handle appropriately
    """
    # Estimate cost of current request
    estimated_cost = _estimate_cost(
        model=model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_tokens=cached_tokens,
        cache_write_tokens=cache_write_tokens,
    )
    
    # Calculate new budget state if we proceed
    new_accumulated = accumulated_usage + estimated_cost
    new_remaining = budget_remaining_usd - estimated_cost
    
    # Determine status based on new remaining budget
    status = _get_budget_status(new_remaining, new_accumulated, round_idx)
    
    result = BudgetResult(
        status=status,
        remaining_usd=new_remaining,
        accumulated_usage=new_accumulated,
        estimated_cost=estimated_cost,
        round_idx=round_idx,
    )
    
    # Log warning if approaching limit
    if status == "warning":
        logger.warning(
            f"Approaching budget limit at round {round_idx}. "
            f"Remaining: ${new_remaining:.4f}, This request: ${estimated_cost:.6f}"
        )
    
    return result
