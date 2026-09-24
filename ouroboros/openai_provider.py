"""OpenAI-native LLM provider for Jo.

This provider intentionally preserves Jo's existing chat/tool contract so the
Ouroboros loop does not need to be rewritten during the hybrid migration.

Environment:
    OPENAI_API_KEY       Required for cloud calls.
    OPENAI_BASE_URL      Optional OpenAI-compatible base URL.
    OPENAI_MODEL         Main model, default gpt-5.6-sol.
    OPENAI_MODEL_CODE    Coding model, default main model.
    OPENAI_MODEL_LIGHT   Low-cost/background model, default gpt-5.6-luna.
    OPENAI_TIMEOUT_SEC   Request timeout, default 90.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional, Tuple


class OpenAILLMClient:
    """OpenAI API adapter compatible with Jo's existing LLM client contract."""

    DEFAULT_MAIN_MODEL = "gpt-5.6-sol"
    DEFAULT_LIGHT_MODEL = "gpt-5.6-luna"

    # Current public list pricing (USD / 1M tokens). Environment overrides are
    # intentionally supported because model pricing can change over time.
    MODEL_PRICING = {
        "gpt-5.6-sol": (4.0, 20.0),
        "gpt-5.6-terra": (2.0, 12.0),
        "gpt-5.6-luna": (0.20, 1.20),
    }

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None) -> None:
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self._base_url = base_url or os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        try:
            self._timeout = float(os.environ.get("OPENAI_TIMEOUT_SEC", "90"))
        except (TypeError, ValueError):
            self._timeout = 90.0

        self._client: Any = None
        self._model_failures: Dict[str, int] = {}

    def _get_client(self) -> Any:
        if self._client is None:
            if not self._api_key.strip():
                raise ValueError("OPENAI_API_KEY is missing or empty")
            from openai import OpenAI

            self._client = OpenAI(
                api_key=self._api_key,
                base_url=self._base_url,
                timeout=self._timeout,
                max_retries=0,
            )
        return self._client

    @staticmethod
    def _normalize_effort(value: str) -> str:
        allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
        effort = str(value or "medium").strip().lower()
        return effort if effort in allowed else "medium"

    def _pricing(self, model: str) -> Tuple[float, float]:
        configured = os.environ.get("OPENAI_PRICING_OVERRIDE", "")
        if configured:
            try:
                in_price, out_price = [float(v.strip()) for v in configured.split(",", 1)]
                return in_price, out_price
            except (TypeError, ValueError):
                pass

        model_id = model.lower().strip()
        if model_id in self.MODEL_PRICING:
            return self.MODEL_PRICING[model_id]

        for known, prices in self.MODEL_PRICING.items():
            if model_id.startswith(known):
                return prices

        return 0.0, 0.0

    def _estimate_cost(self, usage: Dict[str, Any], model: str) -> float:
        prompt_tokens = int(usage.get("prompt_tokens") or 0)
        completion_tokens = int(
            usage.get("completion_tokens")
            or usage.get("output_tokens")
            or 0
        )
        input_price, output_price = self._pricing(model)
        return round(
            (prompt_tokens / 1_000_000.0) * input_price
            + (completion_tokens / 1_000_000.0) * output_price,
            8,
        )

    def select_model_for_task(self, task_type: str = "general") -> str:
        if task_type == "light":
            return os.environ.get("OPENAI_MODEL_LIGHT", self.DEFAULT_LIGHT_MODEL)
        if task_type == "reasoning":
            return os.environ.get(
                "OPENAI_MODEL_REASONING",
                os.environ.get("OPENAI_MODEL", self.DEFAULT_MAIN_MODEL),
            )
        if task_type == "coding":
            return os.environ.get(
                "OPENAI_MODEL_CODE",
                os.environ.get("OPENAI_MODEL", self.DEFAULT_MAIN_MODEL),
            )
        return os.environ.get("OPENAI_MODEL", self.DEFAULT_MAIN_MODEL)

    def default_model(self) -> str:
        return self.select_model_for_task("general")

    def available_models(self) -> List[str]:
        models = [
            self.default_model(),
            os.environ.get("OPENAI_MODEL_CODE", ""),
            os.environ.get("OPENAI_MODEL_LIGHT", self.DEFAULT_LIGHT_MODEL),
            os.environ.get("OPENAI_MODEL_REASONING", ""),
        ]
        return list(dict.fromkeys(m for m in models if m))

    def mark_model_success(self, model: str) -> None:
        self._model_failures[model] = 0

    def mark_model_failure(self, model: str) -> None:
        self._model_failures[model] = self._model_failures.get(model, 0) + 1

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: str = "medium",
        max_tokens: int = 16384,
        tool_choice: str = "auto",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        client = self._get_client()
        effort = self._normalize_effort(reasoning_effort)

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_completion_tokens": max_tokens,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        # GPT-5.x reasoning models expose reasoning_effort. Avoid sending
        # temperature unless explicitly configured for a non-reasoning model.
        kwargs["reasoning_effort"] = effort
        temperature = os.environ.get("OPENAI_TEMPERATURE", "").strip()
        if temperature and not model.lower().startswith("gpt-5"):
            try:
                kwargs["temperature"] = float(temperature)
            except ValueError:
                pass

        last_error: Optional[Exception] = None
        for attempt in range(2):
            try:
                response = client.chat.completions.create(**kwargs)
                payload = response.model_dump()
                choices = payload.get("choices") or []
                message = (choices[0] if choices else {}).get("message") or {}
                usage = payload.get("usage") or {}
                usage["cost"] = self._estimate_cost(usage, model)
                usage["provider"] = "openai"
                usage["model"] = model
                self.mark_model_success(model)

                if not message.get("content") and not message.get("tool_calls"):
                    raise ValueError("OpenAI returned an empty message")

                return message, usage
            except TypeError as exc:
                # Older OpenAI SDKs may reject max_completion_tokens or
                # reasoning_effort. Retry once with the compatible form.
                last_error = exc
                if "max_completion_tokens" in str(exc):
                    kwargs["max_tokens"] = kwargs.pop("max_completion_tokens")
                elif "reasoning_effort" in str(exc):
                    kwargs.pop("reasoning_effort", None)
                else:
                    raise
            except Exception as exc:
                last_error = exc
                self.mark_model_failure(model)
                if attempt == 0 and ("429" in str(exc) or "rate" in str(exc).lower()):
                    time.sleep(2.0)
                    continue
                raise

        raise RuntimeError(f"OpenAI request failed: {last_error}")
