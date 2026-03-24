"""Model Manager — dynamic discovery, health monitoring, and fallback orchestration.

This module provides:
- Continuous health monitoring of configured models
- Dynamic discovery of new available models from OpenRouter
- Automatic fallback chain adaptation when models fail
- Credit/resource exhaustion detection
- Graceful degradation and recovery

Integrates with LLMClient to provide resilient model selection.
"""

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ModelHealth:
    """Health status for a single model."""

    model_id: str
    status: str  # "healthy", "rate_limited", "error", "exhausted"
    last_check: float
    consecutive_failures: int = 0
    last_error: Optional[str] = None
    estimated_credits_remaining: Optional[float] = None  # For free models with daily limits


@dataclass
class ModelDiscovery:
    """Results from model discovery."""

    models: List[Dict[str, Any]]
    providers: List[str]
    last_update: float


class ModelManager:
    """Manages model health, discovery, and fallback chains dynamically."""

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.health: Dict[str, ModelHealth] = {}
        self.discovery: Optional[ModelDiscovery] = None
        self.config = self._load_config()
        self.health_check_interval = int(os.environ.get("MODEL_HEALTH_INTERVAL", "60"))
        self.max_consecutive_failures = int(os.environ.get("MAX_MODEL_FAILURES", "3"))
        self.discovery_interval = int(os.environ.get("MODEL_DISCOVERY_INTERVAL", "3600"))  # 1 hour

    def _load_config(self) -> Dict:
        """Load model configuration from environment."""
        return {
            "primary": os.environ.get("OUROBOROS_MODEL", "openrouter/free"),
            "fallbacks": os.environ.get("OUROBOROS_MODEL_FALLBACK_LIST", "").split(",")
            if os.environ.get("OUROBOROS_MODEL_FALLBACK_LIST")
            else [],
            "preferred_free": os.environ.get("PREFERRED_FREE_MODELS", "").split(",")
            if os.environ.get("PREFERRED_FREE_MODELS")
            else [],
            "max_fallbacks": int(os.environ.get("MAX_MODEL_FALLBACKS", "5")),
        }

    def get_best_available_model(self, task_type: str = "general", _retry_count: int = 0) -> str:
        """Select the best available model based on health and task requirements."""
        candidates = self._build_candidate_list(task_type)

        for model_id in candidates:
            health = self.health.get(model_id)
            if health is None:
                # First time seeing this model, assume healthy but schedule check
                self._mark_model_used(model_id)
                return model_id
            if health.status in ("healthy", "rate_limited"):
                # rate_limited might still work with lower rate limit
                return model_id

        # No healthy models found — try to discover new ones (max 1 retry)
        if _retry_count < 1:
            log.warning("No healthy models in current pool, attempting discovery")
            new_models = self.discover_models()
            if new_models:
                return self.get_best_available_model(task_type, _retry_count=_retry_count + 1)

        # As last resort, try local model if available
        local_model = os.environ.get("OUROBOROS_MODEL", "")
        if "nerdsking" in local_model.lower():
            log.info("Falling back to local model as last resort")
            return local_model

        raise RuntimeError("No available models (all exhausted or offline)")

    def _build_candidate_list(self, task_type: str) -> List[str]:
        """Build ordered list of model candidates."""
        candidates = []

        # 1. Primary model (if healthy)
        primary = self.config["primary"]
        if primary:
            candidates.append(primary)

        # 2. Configured fallbacks in order
        for fb in self.config["fallbacks"]:
            if fb and fb not in candidates:
                candidates.append(fb)

        # 3. Preferred free models (not yet tried)
        for pref in self.config["preferred_free"]:
            if pref and pref not in candidates:
                candidates.append(pref)

        # 4. Any other models we know are healthy from discovery
        if self.discovery:
            for model_info in self.discovery.models:
                model_id = model_info.get("id")
                if model_id and model_id not in candidates:
                    health = self.health.get(model_id, ModelHealth(model_id, "unknown", time.time()))
                    if health.status == "healthy":
                        candidates.append(model_id)

        log.debug(f"Candidate model list: {candidates[:10]}")
        return candidates[: self.config["max_fallbacks"]]

    def _mark_model_used(self, model_id: str):
        """Record that a model was used (initialize health if needed)."""
        if model_id not in self.health:
            self.health[model_id] = ModelHealth(model_id, "healthy", time.time())

    def record_result(self, model_id: str, success: bool, error: Optional[str] = None):
        """Update health based on call result."""
        health = self.health.get(model_id)
        if health is None:
            health = ModelHealth(model_id, "healthy", time.time())
            self.health[model_id] = health

        if success:
            health.consecutive_failures = 0
            health.status = "healthy"
            health.last_error = None
        else:
            health.consecutive_failures += 1
            health.last_error = error

            if health.consecutive_failures >= self.max_consecutive_failures:
                # Mark as exhausted after repeated failures
                health.status = "exhausted"
                log.warning(f"Model {model_id} marked exhausted after {health.consecutive_failures} failures")
            elif "rate limit" in (error or "").lower():
                health.status = "rate_limited"

        health.last_check = time.time()

    def discover_models(self, force: bool = False) -> List[Dict]:
        """Query OpenRouter for available models and filter for free ones."""
        # Periodic cleanup of stale health entries
        self.cleanup_stale_health()

        if self.discovery and not force:
            # Use cached discovery if recent
            if time.time() - self.discovery.last_update < self.discovery_interval:
                return self.discovery.models

        try:
            import requests
        except ImportError as e:
            log.warning("requests not installed, cannot discover models: %s", e)
            return []

        try:
            url = "https://openrouter.ai/api/v1/models"
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            models = data.get("data", [])

            # Filter for free models and those with reasonable pricing
            free_models = []
            for model in models:
                model_id = model.get("id", "")
                pricing = model.get("pricing", {})
                if not pricing:
                    continue

                # Consider a model "free" if prompt price is 0 or very low (< 0.01 per 1M)
                prompt_price = float(pricing.get("prompt", 0)) * 1_000_000
                completion_price = float(pricing.get("completion", 0)) * 1_000_000

                if prompt_price < 0.01 and completion_price < 0.01:
                    model["_effective_price"] = (prompt_price, completion_price)
                    free_models.append(model)

            # Sort by some heuristic (context length, capabilities)
            free_models.sort(
                key=lambda m: (m.get("context_length", 0), -float(m.get("pricing", {}).get("prompt", 0))), reverse=True
            )

            self.discovery = ModelDiscovery(
                models=free_models,
                providers=list(set(m.get("provider", "unknown") for m in free_models)),
                last_update=time.time(),
            )

            log.info(f"Discovered {len(free_models)} free/low-cost models")
            return free_models

        except Exception as e:
            log.error(f"Model discovery failed: {e}")
            return []

    def get_fallback_chain(self, failed_model: str) -> List[str]:
        """Generate an intelligent fallback chain when a model fails."""
        fallbacks = []

        # 1. Try configured fallbacks that aren't the failed model
        for fb in self.config["fallbacks"]:
            if fb and fb != failed_model and fb not in fallbacks:
                fallbacks.append(fb)

        # 2. Try other preferred free models
        for pref in self.config["preferred_free"]:
            if pref and pref != failed_model and pref not in fallbacks:
                fallbacks.append(pref)

        # 3. Discover new models if we haven't recently
        if len(fallbacks) < 3:
            discovered = self.discover_models(force=False)
            for model_info in discovered:
                model_id = model_info.get("id")
                if model_id and model_id != failed_model and model_id not in fallbacks:
                    fallbacks.append(model_id)
                    if len(fallbacks) >= self.config["max_fallbacks"]:
                        break

        # 4. As absolute last resort, local model
        local_model = os.environ.get("OUROBOROS_MODEL", "")
        if local_model and "nerdsking" in local_model.lower() and local_model not in fallbacks:
            fallbacks.append(local_model)

        log.info(f"Generated fallback chain for {failed_model}: {fallbacks[:5]}")
        return fallbacks[: self.config["max_fallbacks"]]

    def should_retry_model(self, model_id: str) -> bool:
        """Decide if we should retry a model that recently failed."""
        health = self.health.get(model_id)
        if not health:
            return True

        if health.status == "exhausted":
            return False

        # For rate limited models, wait a bit before retry
        if health.status == "rate_limited":
            time_since = time.time() - health.last_check
            return time_since > 60  # Wait at least 60s before retrying rate-limited model

        return True

    def reset_model_health(self, model_id: str):
        """Reset health status for a model (e.g., after credits replenish)."""
        if model_id in self.health:
            self.health[model_id] = ModelHealth(model_id, "healthy", time.time())
            log.info(f"Reset health for model {model_id}")

    def cleanup_stale_health(self, max_age_hours: float = 24) -> int:
        """Remove health entries for models not used in max_age_hours."""
        cutoff = time.time() - (max_age_hours * 3600)
        stale = [mid for mid, h in self.health.items() if h.last_check < cutoff and h.status == "healthy"]
        for mid in stale:
            del self.health[mid]
        if stale:
            log.debug("Cleaned up %d stale health entries", len(stale))
        return len(stale)

    def get_health_report(self) -> Dict:
        """Generate a health report for monitoring."""
        report = {
            "timestamp": time.time(),
            "discovery_available": self.discovery is not None,
            "discovery_model_count": len(self.discovery.models) if self.discovery else 0,
            "health_summary": {
                "healthy": sum(1 for h in self.health.values() if h.status == "healthy"),
                "rate_limited": sum(1 for h in self.health.values() if h.status == "rate_limited"),
                "exhausted": sum(1 for h in self.health.values() if h.status == "exhausted"),
                "total": len(self.health),
            },
            "top_models": [
                {
                    "model": m.model_id,
                    "status": m.status,
                    "failures": m.consecutive_failures,
                    "last_error": m.last_error,
                }
                for m in sorted(self.health.values(), key=lambda x: x.consecutive_failures, reverse=True)[:10]
            ],
        }
        return report
