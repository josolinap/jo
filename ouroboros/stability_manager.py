"""
Jo — Stability Manager.

Production-grade stability patterns for autonomous AI agents.
Implements Circuit Breaker, Fallback Chain, and Graceful Degradation.

Inspired by Zylos Research, Sierra AI, and SRE best practices for AI agents.

Patterns:
1. Circuit Breaker: Prevents retry storms during API outages.
   States: CLOSED (normal) → OPEN (failing) → HALF_OPEN (testing recovery).
2. Fallback Chain: Auto-routes to backup models when primary fails.
   e.g., Opus → Sonnet → Haiku → Cached Response.
3. Graceful Degradation: Jo continues working with reduced capabilities.
   Modes: FULL → REDUCED (fallback model) → MINIMAL (local/cached only).
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, rejecting requests
    HALF_OPEN = "half_open"  # Testing recovery


class DegradationMode(Enum):
    FULL = "full"  # All capabilities available
    REDUCED = "reduced"  # Using fallback model, some features disabled
    MINIMAL = "minimal"  # Only essential features, cached/local only


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""

    failure_threshold: int = 5  # Trips after N failures
    success_threshold: int = 2  # Closes after N successes in half-open
    timeout_seconds: float = 300.0  # Time before trying half-open
    extended_timeout_seconds: float = 900.0  # Time after repeated failures


class CircuitBreaker:
    """Circuit breaker for a specific service or model."""

    def __init__(self, name: str, config: CircuitBreakerConfig):
        self.name = name
        self.config = config
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float = 0
        self.last_state_change: float = time.time()
        self._history: deque = deque(maxlen=100)

    def record_success(self) -> None:
        """Record a successful call."""
        self._history.append({"ts": time.time(), "success": True})
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0  # Reset failure count on success

    def record_failure(self) -> None:
        """Record a failed call."""
        self._history.append({"ts": time.time(), "success": False})
        self.last_failure_time = time.time()
        if self.state == CircuitState.CLOSED:
            self.failure_count += 1
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.HALF_OPEN:
            # Failed during recovery test, go back to open with extended timeout
            self._transition_to(CircuitState.OPEN, extended=True)

    def can_execute(self) -> bool:
        """Check if the circuit allows execution."""
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            # Check if timeout has expired
            timeout = (
                self.config.extended_timeout_seconds
                if self.failure_count > self.config.failure_threshold * 2
                else self.config.timeout_seconds
            )
            if time.time() - self.last_state_change > timeout:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        # HALF_OPEN allows one request through
        return True

    def _transition_to(self, new_state: CircuitState, extended: bool = False) -> None:
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
        log.warning("[CircuitBreaker] %s: %s -> %s", self.name, old_state.value, new_state.value)

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        recent_failures = sum(1 for h in self._history if not h["success"] and time.time() - h["ts"] < 300)
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "recent_failures_5m": recent_failures,
            "last_failure": datetime.fromtimestamp(self.last_failure_time).isoformat()
            if self.last_failure_time > 0
            else None,
        }


@dataclass
class FallbackModel:
    """A model in the fallback chain."""

    name: str
    priority: int  # Lower is higher priority
    is_active: bool = True


class FallbackChain:
    """Manages the fallback chain for LLM models."""

    def __init__(self):
        self._models: List[FallbackModel] = []
        self._current_index = 0

    def add_model(self, name: str, priority: int) -> None:
        """Add a model to the fallback chain."""
        self._models.append(FallbackModel(name=name, priority=priority))
        self._models.sort(key=lambda m: m.priority)

    def get_current_model(self) -> Optional[str]:
        """Get the current active model."""
        if not self._models:
            return None
        # Find first active model
        for model in self._models:
            if model.is_active:
                return model.name
        return None

    def fallback(self) -> Optional[str]:
        """Move to the next model in the chain."""
        if not self._models:
            return None
        # Mark current as inactive and move to next
        current = self.get_current_model()
        for model in self._models:
            if model.name == current:
                model.is_active = False
                break
        next_model = self.get_current_model()
        if next_model:
            log.warning("[FallbackChain] Fallback from %s to %s", current, next_model)
        else:
            log.error("[FallbackChain] No models left in fallback chain!")
        return next_model

    def reset(self) -> None:
        """Reset all models to active."""
        for model in self._models:
            model.is_active = True
        log.info("[FallbackChain] Reset fallback chain")

    def get_stats(self) -> Dict[str, Any]:
        """Get fallback chain statistics."""
        return {
            "models": [{"name": m.name, "priority": m.priority, "active": m.is_active} for m in self._models],
            "current_model": self.get_current_model(),
        }


class StabilityManager:
    """Central manager for stability patterns."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "stability"
        self.state_dir.mkdir(parents=True, exist_ok=True)

        # Circuit breakers per service
        self.circuit_breakers: Dict[str, CircuitBreaker] = {
            "llm_api": CircuitBreaker("llm_api", CircuitBreakerConfig()),
            "tool_execution": CircuitBreaker("tool_execution", CircuitBreakerConfig(failure_threshold=10)),
            "memory_access": CircuitBreaker("memory_access", CircuitBreakerConfig(failure_threshold=20)),
        }

        # Fallback chain
        self.fallback_chain = FallbackChain()
        self._load_fallback_chain()

        # Degradation mode
        self.degradation_mode = DegradationMode.FULL

    def _load_fallback_chain(self) -> None:
        """Load fallback chain from Jo env vars, always supplemented with free tier defaults.

        Always builds a complete chain:
        1. OUROBOROS_MODEL (priority 1) - your primary model
        2. OUROBOROS_MODEL_LIGHT (priority 2) - lighter/cheaper fallback
        3. OUROBOROS_MODEL_CODE (priority 3) - code-optimized fallback
        4. openrouter/free defaults (priority 4+) - always included as safety net

        Duplicates are automatically skipped.
        """
        # Collect all models, deduplicating
        seen = set()
        priority = 0

        def add_model(name: str, pri: int) -> None:
            nonlocal priority
            name = name.strip()
            if not name or name in seen:
                return
            seen.add(name)
            self.fallback_chain.add_model(name, pri)

        # 1. Jo-specific env vars (GitHub secrets)
        primary = os.environ.get("OUROBOROS_MODEL", "").strip()
        light = os.environ.get("OUROBOROS_MODEL_LIGHT", "").strip()
        code = os.environ.get("OUROBOROS_MODEL_CODE", "").strip()

        if primary:
            add_model(primary, 1)
        if light:
            add_model(light, 2)
        if code:
            add_model(code, 3)

        # 2. Generic env vars
        for i in range(1, 6):
            model = os.environ.get(f"LLM_FALLBACK_{i}", "").strip()
            if model:
                add_model(model, 10 + i)

        # 3. Config file
        try:
            from ouroboros.config_manager import get_config

            config = get_config()
            for item in config.get("llm", {}).get("fallback_chain", []):
                add_model(item["name"], item.get("priority", 50))
        except Exception:
            pass

        # 4. Always include free tier defaults as safety net (deduped)
        default_fallbacks = [
            "openrouter/free",
            "openrouter/google/gemini-2.0-flash-exp:free",
            "openrouter/meta-llama/llama-3.3-70b-instruct:free",
            "openrouter/mistralai/mistral-7b-instruct:free",
        ]
        for i, name in enumerate(default_fallbacks):
            add_model(name, 100 + i)

        log.info("[Stability] Fallback chain loaded: %s", list(seen))

    def check_circuit(self, service: str) -> bool:
        """Check if a service circuit allows execution."""
        cb = self.circuit_breakers.get(service)
        if not cb:
            return True
        return cb.can_execute()

    def record_success(self, service: str) -> None:
        """Record a success for a service."""
        cb = self.circuit_breakers.get(service)
        if cb:
            cb.record_success()
            # If LLM API succeeds, we might be able to recover degradation
            if service == "llm_api" and self.degradation_mode != DegradationMode.FULL:
                self.degradation_mode = DegradationMode.FULL
                log.info("[Stability] Recovered to FULL degradation mode")

    def record_failure(self, service: str) -> None:
        """Record a failure for a service."""
        cb = self.circuit_breakers.get(service)
        if cb:
            cb.record_failure()
            # If LLM API fails, degrade
            if service == "llm_api":
                next_model = self.fallback_chain.fallback()
                if next_model:
                    self.degradation_mode = DegradationMode.REDUCED
                    log.warning("[Stability] Degraded to REDUCED mode, using %s", next_model)
                else:
                    self.degradation_mode = DegradationMode.MINIMAL
                    log.error("[Stability] Degraded to MINIMAL mode, no fallback models")

    def get_current_model(self) -> Optional[str]:
        """Get the current model to use (respecting fallback chain)."""
        return self.fallback_chain.get_current_model()

    def reset(self, service: Optional[str] = None) -> None:
        """Reset circuit breakers and/or fallback chain."""
        if service:
            cb = self.circuit_breakers.get(service)
            if cb:
                cb._transition_to(CircuitState.CLOSED)
        else:
            for cb in self.circuit_breakers.values():
                cb._transition_to(CircuitState.CLOSED)
            self.fallback_chain.reset()
            self.degradation_mode = DegradationMode.FULL
        log.info("[Stability] Reset stability manager")

    def get_stats(self) -> Dict[str, Any]:
        """Get stability statistics."""
        return {
            "degradation_mode": self.degradation_mode.value,
            "current_model": self.get_current_model(),
            "circuit_breakers": {name: cb.get_stats() for name, cb in self.circuit_breakers.items()},
            "fallback_chain": self.fallback_chain.get_stats(),
        }


# Global stability manager instance
_manager: Optional[StabilityManager] = None


def get_stability_manager(repo_dir: Optional[pathlib.Path] = None) -> StabilityManager:
    """Get or create the global stability manager."""
    global _manager
    if _manager is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _manager = StabilityManager(repo_dir)
    return _manager
