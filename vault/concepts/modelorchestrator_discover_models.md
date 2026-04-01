---
title: ModelOrchestrator.discover_models
created: 2026-04-01T16:40:46.918308+00:00
modified: 2026-04-01T16:40:46.918308+00:00
type: concept
status: draft
tags: [code, llm, model, discovery]
---

# ModelOrchestrator.discover_models

# ModelOrchestrator.discover_models

**Type**: method
**Module**: ouroboros.llm.models
**Purpose**: Discover available LLM models from OpenRouter and cache their metadata

## Details

Queries OpenRouter API to get list of available models, their capabilities, pricing, and context windows. Caches results to avoid repeated API calls. Used during initialization and model selection.

## Related
- [[llm-orchestration]]
- [[model-discovery]]
- [[openrouter-api]]
