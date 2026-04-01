---
title: ModelInfo
created: 2026-04-01T16:40:40.225055+00:00
modified: 2026-04-01T16:40:40.225055+00:00
type: concept
status: draft
tags: [code, llm, model, metadata]
---

# ModelInfo

# ModelInfo

**Type**: dataclass
**Module**: ouroboros.llm
**Purpose**: Store metadata about LLM models including name, provider, price, context window, and capabilities

## Fields
- name: Model identifier (e.g., "anthropic/claude-sonnet-4")
- provider: Model provider
- price_per_million: Token pricing
- context_window: Maximum context length
- capabilities: Model capabilities

## Related
- [[llm-orchestration]]
- [[model-routing]]
- [[model-selection]]
LLM model metadata storage [[llm-orchestration]]
