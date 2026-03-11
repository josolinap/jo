"""
Model Orchestrator - Dynamic model selection and monitoring for OpenRouter free models
"""

import asyncio
import json
import logging
import os
import time
import random
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

import requests
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    RATE_LIMITED = "rate_limited"


@dataclass
class ModelInfo:
    """Information about an OpenRouter model."""
    id: str
    name: str
    free: bool
    status: ModelStatus
    last_tested: float
    response_time: Optional[float] = None
    error_count: int = 0
    success_count: int = 0


class ModelOrchestrator:
    """
    Dynamically manages OpenRouter free models, detecting failures and routing around them.
    """

    def __init__(self):
        self.api_key = os.environ.get("OPENROUTER_API_KEY")
        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")

        self.base_url = "https://openrouter.ai/api/v1"
        self.models: Dict[str, ModelInfo] = {}
        self.active_model = "openrouter/free"
        self.fallback_chain: List[str] = []
        self.max_retries = 3
        self.test_timeout = 10

        # Known free models on OpenRouter
        self.free_model_prefixes = [
            "openrouter/free",
            "stepfun/step-3.5-flash:free",
            "arcee-ai/trinity-large-preview:free",
            "z-ai/glm-4.5-air:free",
            "qwen/qwen2.5-72b-instruct:free",
            "meta-llama/llama-3.1-8b-instruct:free",
            "google/gemini-2.0-flash-exp:free",
        ]

    async def discover_models(self) -> List[ModelInfo]:
        """Discover all available free models from OpenRouter."""
        try:
            response = requests.get(
                f"{self.base_url}/models",
                headers={"Authorization": f"Bearer {self.api_key}"},
                timeout=15
            )
            response.raise_for_status()
            data = response.json()
            models_data = data.get("data", [])

            models = []
            for model_data in models_data:
                model_id = model_data.get("id", "")
                # Check if model is free
                is_free = (
                    ":free" in model_id or
                    model_id.startswith("openrouter/free") or
                    any(prefix in model_id for prefix in self.free_model_prefixes)
                )

                if is_free:
                    model_info = ModelInfo(
                        id=model_id,
                        name=model_data.get("name", model_id),
                        free=True,
                        status=ModelStatus.UNKNOWN,
                        last_tested=0
                    )
                    models.append(model_info)
                    self.models[model_id] = model_info

            log.info(f"Discovered {len(models)} free models from OpenRouter")
            return models

        except Exception as e:
            log.error(f"Failed to discover models: {e}")
            return []

    async def test_model(self, model_id: str) -> Tuple[ModelStatus, float]:
        """Test a model with a simple prompt."""
        start_time = time.time()

        try:
            # Simple test prompt
            test_prompt = "Respond with: OK"

            response = requests.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": "You are a helpful assistant."},
                        {"role": "user", "content": test_prompt}
                    ],
                    "max_tokens": 10,
                    "temperature": 0.1,
                },
                timeout=self.test_timeout
            )

            response_time = time.time() - start_time

            if response.status_code == 200:
                data = response.json()
                if data.get("choices"):
                    content = data["choices"][0]["message"]["content"]
                    if content and "ok" in content.lower():
                        return ModelStatus.HEALTHY, response_time

            elif response.status_code == 429:
                return ModelStatus.RATE_LIMITED, response_time

            return ModelStatus.UNHEALTHY, response_time

        except Exception as e:
            log.warning(f"Model {model_id} failed test: {e}")
            return ModelStatus.UNHEALTHY, 0

    async def get_working_model(self, current_model: str = None) -> str:
        """Get a working model, falling back if needed."""
        if current_model is None:
            current_model = self.active_model

        # Try current model first
        if current_model in self.models:
            model_info = self.models[current_model]
            if model_info.status == ModelStatus.HEALTHY:
                return current_model

        # Try fallback chain
        if self.fallback_chain:
            for model_id in self.fallback_chain:
                if model_id != current_model:
                    log.info(f"Falling back to model: {model_id}")
                    return model_id

        # If no healthy models, return openrouter/free as last resort
        log.warning("No healthy models found, using openrouter/free as fallback")
        return "openrouter/free"

    async def chat(self, messages: List[Dict], model: str = None, **kwargs) -> Dict[str, Any]:
        """Chat completion with automatic model fallback."""
        if model is None:
            model = await self.get_working_model()

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": model,
                        "messages": messages,
                        **kwargs
                    },
                    timeout=30
                )

                if response.status_code == 200:
                    return response.json()

                elif response.status_code == 429:
                    log.warning(f"Rate limited on {model}, attempt {attempt + 1}")
                    await asyncio.sleep(2 ** attempt)

            except Exception as e:
                log.error(f"Error calling {model}: {e}")

            # Try fallback
            if attempt < self.max_retries - 1:
                model = await self.get_working_model(model)
                log.info(f"Switching to: {model}")
                await asyncio.sleep(1)

        raise Exception(f"Failed after {self.max_retries} attempts")

    def get_status(self) -> Dict[str, Any]:
        """Get current model status."""
        return {
            "total_models": len(self.models),
            "fallback_chain": self.fallback_chain[:5],
            "active_model": self.active_model,
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(ModelOrchestrator().discover_models())