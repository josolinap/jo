---
title: ModelStatus
created: 2026-04-01T16:40:21.356437+00:00
modified: 2026-04-01T16:40:21.356437+00:00
type: concept
status: draft
tags: [code, llm, model, status]
---

# ModelStatus

# ModelStatus

**Type**: class/enum
**Module**: ouroboros.llm (models.py)
**Purpose**: Track LLM model availability and status

## Values
- active - model available and performing well
- degraded - model available but has issues
- unavailable - model temporarily down
- deprecated - model should not be used

## Related
- [[llm-orchestration]]
- [[model-routing]]
- [[fallback-strategy]]
