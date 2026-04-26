"""
Ouroboros — LLM client.

The only module that communicates with LLM APIs (OpenRouter, NVIDIA NIM, local).
Contract: chat(), default_model(), available_models(), add_usage().

Features inspired by free-claude-code:
- Multi-provider fallback chain (OpenRouter -> NVIDIA -> Local)
- Model routing by task type (reasoning, coding, light)
- Retry with downgrading on 400 errors
- Thinking token support
- Request optimization (trivial calls handled locally)
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

DEFAULT_LIGHT_MODEL = "openrouter/free"

REASONING_PATTERNS = ("deepseek-r1", "gemma-4", "gemma-3-27b", "llama-3.1-70b", "phi-4", "nemotron", "reasoning")
CODING_PATTERNS = ("coder", "code", "starcoder", "deepseek-coder")
LIGHT_PATTERNS = ("llama-3.2", "llama-3.3", "gemma-2-2b", "gemma-2-9b", "phi-3-mini", "phi-3-small", "qwen-")

TRIVIAL_PATTERNS = (
    r"^hi$",
    r"^hello$",
    r"^hey$",
    r"^ok$",
    r"^yes$",
    r"^no$",
    r"^thanks?$",
    r"^thank you$",
    r"^how are you\??$",
    r"^what time is it\??$",
    r"^date\??$",
)


def normalize_reasoning_effort(value: str, default: str = "medium") -> str:
    allowed = {"none", "minimal", "low", "medium", "high", "xhigh"}
    v = str(value or "").strip().lower()
    return v if v in allowed else default


def reasoning_rank(value: str) -> int:
    order = {"none": 0, "minimal": 1, "low": 2, "medium": 3, "high": 4, "xhigh": 5}
    return int(order.get(str(value or "").strip().lower(), 3))


def is_trivial_request(messages: List[Dict[str, Any]]) -> bool:
    """Check if request is trivial (greeting, thanks, etc.) - can be handled locally."""
    if not messages:
        return False
    last_msg = messages[-1]
    content = last_msg.get("content", "")
    if not content or not isinstance(content, str):
        return False
    content = content.strip().lower()
    for pattern in TRIVIAL_PATTERNS:
        if re.match(pattern, content):
            return True
    return False


def get_task_type(model: str, reasoning_effort: str = "medium") -> str:
    """Determine task type based on model name and reasoning effort."""
    model_lower = model.lower()
    if reasoning_effort in ("high", "xhigh"):
        return "reasoning"
    if any(x in model_lower for x in REASONING_PATTERNS):
        return "reasoning"
    if any(x in model_lower for x in CODING_PATTERNS):
        return "coding"
    if any(x in model_lower for x in LIGHT_PATTERNS):
        return "light"
    return "general"


def get_trivial_response(content: str) -> str:
    """Generate response for trivial requests without API call."""
    content = content.strip().lower()
    responses = {
        "hi": "Hi! How can I help you today?",
        "hello": "Hello! What would you like me to help with?",
        "hey": "Hey! Ready to work on some code?",
        "ok": "Got it! What's next?",
        "yes": "Great! What would you like to do?",
        "no": "No problem. Let me know if you change your mind.",
        "thanks": "You're welcome! Anything else?",
        "thank you": "You're welcome! Happy to help.",
        "how are you?": "I'm doing well, thanks for asking! Ready to code.",
        "what time is it?": "I don't have access to the current time, but I'm always ready to help!",
        "date?": "I don't have access to the current date, but I'm ready to work on your code!",
    }
    for pattern, response in responses.items():
        if re.match(pattern, content):
            return response
    return "Got it! What would you like me to do?"


def add_usage(total: Dict[str, Any], usage: Dict[str, Any]) -> None:
    """Accumulate usage from one LLM call into a running total."""
    for k in ("prompt_tokens", "completion_tokens", "total_tokens", "cached_tokens", "cache_write_tokens"):
        total[k] = int(total.get(k) or 0) + int(usage.get(k) or 0)
    if usage.get("cost"):
        total["cost"] = float(total.get("cost") or 0) + float(usage["cost"])


def fetch_openrouter_pricing() -> Dict[str, Tuple[float, float, float]]:
    """
    Fetch current pricing from OpenRouter API.

    Returns dict of {model_id: (input_per_1m, cached_per_1m, output_per_1m)}.
    Returns empty dict on failure.
    """
    import logging

    log = logging.getLogger("ouroboros.llm")

    try:
        import requests
    except ImportError:
        log.warning("requests not installed, cannot fetch pricing")
        return {}

    try:
        url = "https://openrouter.ai/api/v1/models"
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()

        data = resp.json()
        models = data.get("data", [])

        # Prefixes we care about
        prefixes = ("anthropic/", "openai/", "google/", "meta-llama/", "x-ai/", "qwen/")

        pricing_dict = {}
        for model in models:
            model_id = model.get("id", "")
            if not model_id.startswith(prefixes):
                continue

            pricing = model.get("pricing", {})
            if not pricing or not pricing.get("prompt"):
                continue

            # OpenRouter pricing is in dollars per token (raw values)
            raw_prompt = float(pricing.get("prompt", 0))
            raw_completion = float(pricing.get("completion", 0))
            raw_cached_str = pricing.get("input_cache_read")
            raw_cached = float(raw_cached_str) if raw_cached_str else None

            # Convert to per-million tokens
            prompt_price = round(raw_prompt * 1_000_000, 4)
            completion_price = round(raw_completion * 1_000_000, 4)
            if raw_cached is not None:
                cached_price = round(raw_cached * 1_000_000, 4)
            else:
                cached_price = round(prompt_price * 0.1, 4)  # fallback: 10% of prompt

            # Sanity check: skip obviously wrong prices
            if prompt_price > 1000 or completion_price > 1000:
                log.warning(
                    f"Skipping {model_id}: prices seem wrong (prompt={prompt_price}, completion={completion_price})"
                )
                continue

            pricing_dict[model_id] = (prompt_price, cached_price, completion_price)

        log.info(f"Fetched pricing for {len(pricing_dict)} models from OpenRouter")
        return pricing_dict

    except (requests.RequestException, ValueError, KeyError) as e:
        log.warning(f"Failed to fetch OpenRouter pricing: {e}")
        return {}


class NvidiaLLMClient:
    """NVIDIA NIM API wrapper with dynamic model discovery and task routing."""

    REASONING_MODELS = [
        "deepseek-ai/deepseek-r1-distill-llama-8b",
        "google/gemma-4-31b-it",
        "meta/llama-3.1-70b-instruct",
    ]

    CODING_MODELS = [
        "deepseek-ai/deepseek-coder-33b-instruct",
        "meta/llama-3.1-8b-instruct",
        "google/gemma-3-27b-it",
    ]

    LIGHT_MODELS = [
        "meta/llama-3.2-1b-instruct",
        "meta/llama-3.2-3b-instruct",
        "google/gemma-2-2b-it",
        "phi-3-mini-instruct",
    ]

    def __init__(self):
        self._api_key = os.environ.get("NVIDIA_API_KEY", "")
        self._base_url = os.environ.get("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")
        self._default_model = os.environ.get("NVIDIA_MODEL", "meta/llama-3.1-8b-instruct")
        self._client = None
        self._cached_models: Optional[List[str]] = None
        self._last_refresh = 0.0
        self._refresh_interval = 3600.0
        self._model_failure_count: Dict[str, int] = {}
        self._current_model_index = 0

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                timeout=30.0,
                max_retries=0,
            )
        return self._client

    def _fetch_available_models(self, force: bool = False) -> List[str]:
        if self._cached_models and not force:
            age = time.time() - self._last_refresh
            if age < self._refresh_interval:
                return self._cached_models

        try:
            import requests

            resp = requests.get(
                "https://integrate.api.nvidia.com/v1/models",
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=10.0,
            )
            resp.raise_for_status()
            all_models = [m["id"] for m in resp.json().get("data", [])]

            categories = {
                "reasoning": [],
                "coding": [],
                "light": [],
                "other": [],
            }

            for m in all_models:
                m_lower = m.lower()
                if any(
                    x in m_lower
                    for x in [
                        "deepseek-r1",
                        "deepseekreasoning",
                        "r1",
                        "gemma-4",
                        "gemma-3-27b",
                        "llama-3.1-70b",
                        "phi-4",
                        "nemotron",
                    ]
                ):
                    categories["reasoning"].append(m)
                elif any(x in m_lower for x in ["coder", "code", "starcoder"]):
                    categories["coding"].append(m)
                elif any(
                    x in m_lower
                    for x in [
                        "llama-3.2-1b",
                        "llama-3.2-3b",
                        "llama-3.3-70b",
                        "llama-3.1-8b",
                        "gemma-2-2b",
                        "gemma-2-9b",
                        "gemma-3-4b",
                        "phi-3-mini",
                        "phi-3-small",
                        "phi-4-mini",
                        "mistral-nemo",
                        "qwen-",
                    ]
                ):
                    categories["light"].append(m)
                else:
                    categories["other"].append(m)

            self._cached_models = all_models
            self._model_categories = categories
            self._last_refresh = time.time()
            log.info(
                f"Fetched {len(all_models)} NVIDIA models: "
                f"{len(categories['reasoning'])} reasoning, "
                f"{len(categories['coding'])} coding, "
                f"{len(categories['light'])} light"
            )
            return all_models

        except Exception as e:
            log.warning(f"Failed to dynamically fetch NVIDIA models: {e}")
            return self._get_fallback_models()

    def _get_fallback_models(self) -> List[str]:
        env_fallback = os.environ.get("NVIDIA_FALLBACK_MODEL", "")
        fallbacks = []
        if env_fallback:
            fallbacks.append(env_fallback)
        fallbacks.extend(self.LIGHT_MODELS[:2])
        return fallbacks

    def get_models_for_task(self, task_type: str = "general") -> List[str]:
        """Return best models for a given task type."""
        self._fetch_available_models()
        categories = getattr(self, "_model_categories", {})

        if task_type == "reasoning":
            return categories.get("reasoning", [])[:5] or self.REASONING_MODELS
        if task_type == "coding":
            return categories.get("coding", [])[:3] or self.CODING_MODELS
        if task_type == "light":
            return categories.get("light", [])[:5] or self.LIGHT_MODELS
        return categories.get("light", [])[:3] or self.LIGHT_MODELS

    def select_model_for_task(self, task_type: str = "general") -> str:
        """Select the best model for a task with rotation to handle rate limits."""
        candidates = self.get_models_for_task(task_type)

        failed_threshold = 3
        available = [
            m
            for m in candidates
            if self._model_failure_count.get(m, 0) < failed_threshold
        ]
        if not available:
            available = candidates[:1]
            for m in available:
                self._model_failure_count[m] = 0

        idx = self._current_model_index % len(available)
        selected = available[idx]
        self._current_model_index += 1
        return selected

    def mark_model_success(self, model: str) -> None:
        """Mark a model as successful (reset failure count)."""
        self._model_failure_count[model] = 0

    def mark_model_failure(self, model: str) -> None:
        """Mark a model as failed (increment failure count)."""
        self._model_failure_count[model] = self._model_failure_count.get(model, 0) + 1
        if self._model_failure_count[model] >= 3:
            log.warning(f"Model {model} marked as failing (3+ failures)")

    def refresh_models(self) -> None:
        """Force refresh the model list."""
        self._fetch_available_models(force=True)

    def default_model(self) -> str:
        return self.select_model_for_task("general")

    def available_models(self) -> List[str]:
        return self.get_models_for_task("light")[:5]

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

        extra_body: Dict[str, Any] = {
            "stream": False,
        }

        if "gemma" in model.lower() and "4" in model:
            extra_body["chat_template_kwargs"] = {"enable_thinking": True}

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 1.0,
            "top_p": 0.95,
            "extra_body": extra_body,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:
            err_str = str(e)
            if "extra_forbidden" in err_str or "Extra inputs" in err_str:
                log.warning(f"Model {model} doesn't support extra_body, retrying without...")
                clean_kwargs = {k: v for k, v in kwargs.items() if k != "extra_body"}
                resp = client.chat.completions.create(**clean_kwargs)
            else:
                log.warning(f"NvidiaLLMClient chat failed: {e}")
                raise

        resp_dict = resp.model_dump()
        usage = resp_dict.get("usage") or {}
        choices = resp_dict.get("choices") or [{}]
        msg = (choices[0] if choices else {}).get("message") or {}

        usage["cost"] = 0.0

        return msg, usage


class LocalLLMClient:
    """Local Ollama/vLLM API wrapper. Compatible with OpenAI API format."""

    def __init__(self):
        self._base_url = os.environ.get("LOCAL_BASE_URL", "http://localhost:11434/v1")
        # Use OUROBOROS_MODEL as the default local model
        self._model = os.environ.get("OUROBOROS_MODEL", "nerdsking/python-coder-7b-i:Q5_K_M")
        self._api_key = os.environ.get("LOCAL_API_KEY", "EMPTY")
        self._client = None

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
            )
        return self._client

    def default_model(self) -> str:
        return self._model

    def available_models(self) -> List[str]:
        return [self._model]

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: str = "medium",
        max_tokens: int = 16384,
        tool_choice: str = "auto",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Single LLM call to local Ollama. Returns: (response_message_dict, usage_dict)."""
        client = self._get_client()

        # Use the configured local model
        normalized_model = self._model

        # Map reasoning_effort to Qwen's enable_thinking
        enable_thinking = reasoning_rank(reasoning_effort) >= 3

        extra_body: Dict[str, Any] = {
            "enable_thinking": enable_thinking,
        }

        kwargs: Dict[str, Any] = {
            "model": normalized_model,
            "messages": messages,
            "max_tokens": max_tokens,
            "extra_body": extra_body,
        }

        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        resp = client.chat.completions.create(**kwargs)
        resp_dict = resp.model_dump()

        usage = resp_dict.get("usage") or {}
        choices = resp_dict.get("choices") or [{}]
        msg = (choices[0] if choices else {}).get("message") or {}

        # Local models are free - set cost to 0
        usage["cost"] = 0.0

        return msg, usage


class LLMClient:
    """LLM client with provider support (OpenRouter, NVIDIA NIM, or local vLLM)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://openrouter.ai/api/v1",
    ):
        provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()

        if provider == "local":
            self._impl = LocalLLMClient()
            self._is_local = True
            self._is_nvidia = False
            self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
            self._base_url = base_url
            self._client = None
        elif provider == "nvidia":
            self._impl = NvidiaLLMClient()
            self._is_local = True
            self._is_nvidia = True
            self._api_key = api_key or os.environ.get("NVIDIA_API_KEY", "")
            self._base_url = base_url
            self._client = None
        else:
            self._api_key = api_key or os.environ.get("OPENROUTER_API_KEY", "")
            self._base_url = base_url
            self._client = None
            self._is_local = False
            self._is_nvidia = False

    def _get_client(self):
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(
                base_url=self._base_url,
                api_key=self._api_key,
                default_headers={
                    "HTTP-Referer": "https://github.com/josolinap/jo",
                    "X-Title": "Jo",
                },
            )
        return self._client

    def _fetch_generation_cost(self, generation_id: str) -> Optional[float]:
        """Fetch cost from OpenRouter Generation API as fallback."""
        try:
            import requests

            url = f"{self._base_url.rstrip('/')}/generation?id={generation_id}"
            resp = requests.get(url, headers={"Authorization": f"Bearer {self._api_key}"}, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("data") or {}
                cost = data.get("total_cost") or data.get("usage", {}).get("cost")
                if cost is not None:
                    return float(cost)
            # Generation might not be ready yet — retry once after short delay
            time.sleep(0.5)
            resp = requests.get(url, headers={"Authorization": f"Bearer {self._api_key}"}, timeout=5)
            if resp.status_code == 200:
                data = resp.json().get("data") or {}
                cost = data.get("total_cost") or data.get("usage", {}).get("cost")
                if cost is not None:
                    return float(cost)
        except Exception:
            log.debug("Failed to fetch generation cost from OpenRouter", exc_info=True)
            pass
        return None

    def chat(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: str = "medium",
        max_tokens: int = 16384,
        tool_choice: str = "auto",
        _skip_trivial: bool = False,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Single LLM call with multi-provider fallback chain.
        
        Provider chain: OpenRouter -> NVIDIA NIM -> Local Ollama
        """
        # Handle trivial requests locally to save API quota
        if not _skip_trivial and is_trivial_request(messages):
            content = messages[-1].get("content", "")
            response = get_trivial_response(content)
            return {"content": response}, {"cost": 0.0, "prompt_tokens": 0, "completion_tokens": 3, "total_tokens": 3}

        # 1. Designated NVIDIA provider
        if getattr(self, "_is_nvidia", False):
            return self._impl.chat(messages, model, tools, reasoning_effort, max_tokens, tool_choice)

        # 2. Local provider check
        if getattr(self, "_is_local", False):
            model_lower = model.lower()
            is_cloud = (
                ":free" in model
                or ":preview" in model
                or any(
                    x in model_lower
                    for x in [
                        "google",
                        "anthropic",
                        "openai",
                        "meta-llama",
                        "x-ai",
                        "cohere",
                        "mistral",
                        "fireworks",
                        "nvidia",
                        "arcee",
                        "z-ai",
                    ]
                )
                or (("/" in model) and not any(x in model_lower for x in ["nerdsking", "qwen2.5", "qwen3"]))
            )

            if not is_cloud:
                return self._impl.chat(messages, model, tools, reasoning_effort, max_tokens, tool_choice)

        # 3. OpenRouter execution with fallback chain
        for provider_attempt in range(3):
            try:
                if not self._api_key or not self._api_key.strip():
                    raise ValueError("OPENROUTER_API_KEY is missing or empty")

                msg, usage = self._chat_openrouter(messages, model, tools, reasoning_effort, max_tokens, tool_choice)

                tool_calls = msg.get("tool_calls") or []
                content = msg.get("content")
                if not tool_calls and (not content or not content.strip()):
                    raise ValueError("OpenRouter returned an empty response")

                return msg, usage

            except Exception as e:
                err_str = str(e)
                is_rate_limited = "429" in err_str or "rate_limit" in err_str.lower()
                is_auth_error = "401" in err_str or "403" in err_str or "authentication" in err_str.lower()
                is_missing_key = "missing" in err_str.lower() or "empty" in err_str.lower()
                
                # Don't retry auth errors or missing key - fall back to next provider
                if is_auth_error or is_missing_key or provider_attempt >= 2:
                    pass  # Continue to fallback
                elif is_rate_limited:
                    log.warning(f"OpenRouter rate limited, waiting before retry...")
                    time.sleep(5 * (provider_attempt + 1))
                    continue
                else:
                    pass  # Continue to fallback

                # Fallback to NVIDIA NIM
                nvidia_key = os.environ.get("NVIDIA_API_KEY", "")
                if nvidia_key and provider_attempt < 2:
                    log.warning(f"OpenRouter failed ({e}), falling back to NVIDIA NIM")
                    try:
                        nvidia_client = NvidiaLLMClient()
                        nvidia_client._fetch_available_models()

                        task_type = get_task_type(model, reasoning_effort)
                        
                        candidates = []
                        env_fallback = os.environ.get("NVIDIA_FALLBACK_MODEL", "")
                        if env_fallback:
                            candidates.append(env_fallback)
                        
                        task_models = nvidia_client.get_models_for_task(task_type)
                        for m in task_models:
                            if m not in candidates:
                                candidates.append(m)
                        
                        candidates = candidates[:5]
                        last_err = None
                        for candidate in candidates:
                            try:
                                log.info(f"Att NVIDIA fallback: {candidate}")
                                msg, usage = nvidia_client.chat(messages, candidate, tools, reasoning_effort, max_tokens, tool_choice)
                                nvidia_client.mark_model_success(candidate)
                                return msg, usage
                            except Exception as try_err:
                                log.warning(f"NVIDIA {candidate} failed: {try_err}")
                                nvidia_client.mark_model_failure(candidate)
                                last_err = try_err

                        if last_err:
                            log.warning(f"All NVIDIA candidates failed, continuing...")

                    except Exception as nvidia_err:
                        log.warning(f"NVIDIA fallback failed: {nvidia_err}")

                # Fallback to local Ollama
                local_key = os.environ.get("LOCAL_API_KEY", "")
                if local_key or os.environ.get("LOCAL_BASE_URL"):
                    log.warning(f"Trying local Ollama...")
                    try:
                        local_client = LocalLLMClient()
                        return local_client.chat(messages, model, tools, reasoning_effort, max_tokens, tool_choice)
                    except Exception as local_err:
                        log.warning(f"Local Ollama failed: {local_err}")

                # All providers failed
                raise

        raise ValueError("All providers exhausted")

    def _chat_openrouter(
        self,
        messages: List[Dict[str, Any]],
        model: str,
        tools: Optional[List[Dict[str, Any]]] = None,
        reasoning_effort: str = "medium",
        max_tokens: int = 16384,
        tool_choice: str = "auto",
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """OpenRouter implementation."""
        client = self._get_client()
        effort = normalize_reasoning_effort(reasoning_effort)

        extra_body: Dict[str, Any] = {
            "reasoning": {"effort": effort, "exclude": True},
        }

        # Pin Anthropic models to Anthropic provider for prompt caching
        if model.startswith("anthropic/"):
            extra_body["provider"] = {
                "order": ["Anthropic"],
                "allow_fallbacks": False,
                "require_parameters": True,
            }

        kwargs: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "extra_body": extra_body,
        }
        if tools:
            # Add cache_control to last tool for Anthropic prompt caching
            # This caches all tool schemas (they never change between calls)
            tools_with_cache = [t for t in tools]  # shallow copy
            if tools_with_cache:
                last_tool = {**tools_with_cache[-1]}  # copy last tool
                last_tool["cache_control"] = {"type": "ephemeral", "ttl": "1h"}
                tools_with_cache[-1] = last_tool
            kwargs["tools"] = tools_with_cache
            kwargs["tool_choice"] = tool_choice

        resp = client.chat.completions.create(**kwargs)
        resp_dict = resp.model_dump()
        usage = resp_dict.get("usage") or {}
        choices = resp_dict.get("choices") or [{}]
        msg = (choices[0] if choices else {}).get("message") or {}

        # Extract cached_tokens from prompt_tokens_details if available
        if not usage.get("cached_tokens"):
            prompt_details = usage.get("prompt_tokens_details") or {}
            if isinstance(prompt_details, dict) and prompt_details.get("cached_tokens"):
                usage["cached_tokens"] = int(prompt_details["cached_tokens"])

        # Extract cache_write_tokens from prompt_tokens_details if available
        # OpenRouter: "cache_write_tokens"
        # Native Anthropic: "cache_creation_tokens" or "cache_creation_input_tokens"
        if not usage.get("cache_write_tokens"):
            prompt_details_for_write = usage.get("prompt_tokens_details") or {}
            if isinstance(prompt_details_for_write, dict):
                cache_write = (
                    prompt_details_for_write.get("cache_write_tokens")
                    or prompt_details_for_write.get("cache_creation_tokens")
                    or prompt_details_for_write.get("cache_creation_input_tokens")
                )
                if cache_write:
                    usage["cache_write_tokens"] = int(cache_write)

        # Ensure cost is present in usage (OpenRouter includes it, but fallback if missing)
        if not usage.get("cost"):
            gen_id = resp_dict.get("id") or ""
            if gen_id:
                cost = self._fetch_generation_cost(gen_id)
                if cost is not None:
                    usage["cost"] = cost

        return msg, usage

    def vision_query(
        self,
        prompt: str,
        images: List[Dict[str, Any]],
        model: str = "",
        max_tokens: int = 1024,
        reasoning_effort: str = "low",
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Send a vision query to an LLM. Lightweight — no tools, no loop.

        Args:
            prompt: Text instruction for the model
            images: List of image dicts. Each dict must have either:
                - {"url": "https://..."} — for URL images
                - {"base64": "<b64>", "mime": "image/png"} — for base64 images
            model: VLM-capable model ID (uses default_model if empty)
            max_tokens: Max response tokens
            reasoning_effort: Effort level

        Returns:
            (text_response, usage_dict)
        """
        if not model:
            model = self.default_model()
        # Build multipart content
        content: List[Dict[str, Any]] = [{"type": "text", "text": prompt}]
        for img in images:
            if "url" in img:
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": img["url"]},
                    }
                )
            elif "base64" in img:
                mime = img.get("mime", "image/png")
                content.append(
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime};base64,{img['base64']}"},
                    }
                )
            else:
                log.warning("vision_query: skipping image with unknown format: %s", list(img.keys()))

        messages = [{"role": "user", "content": content}]
        response_msg, usage = self.chat(
            messages=messages,
            model=model,
            tools=None,
            reasoning_effort=reasoning_effort,
            max_tokens=max_tokens,
        )
        text = response_msg.get("content") or ""
        return text, usage

    def default_model(self) -> str:
        """Return the single default model from env. LLM switches via tool if needed."""
        if self._is_local:
            return self._impl.default_model()
        return os.environ.get("OUROBOROS_MODEL", "openrouter/free")

    def available_models(self) -> List[str]:
        """Return list of available models from env (for switch_model tool schema)."""
        if self._is_local:
            return self._impl.available_models()

        main = os.environ.get("OUROBOROS_MODEL", "openrouter/free")
        code = os.environ.get("OUROBOROS_MODEL_CODE", "")
        light = os.environ.get("OUROBOROS_MODEL_LIGHT", "")
        models = [main]
        if code and code != main:
            models.append(code)
        if light and light != main and light != code:
            models.append(light)
        return models
