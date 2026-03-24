---
title: Temporal Tool Learning
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [learning, tools, routing, ruvector]
---

# Temporal Tool Learning

Tracks which tool sequences succeed for which task types, and reinforces patterns that work.

## Three-Speed Learning (from RuVector)

- **Instant** (<1ms): session-local pattern boost when a tool is called
- **Session** (~10ms): reinforce successful sequences during active work
- **Long-term** (~100ms): persist learned patterns across sessions via JSONL

## How It Works

1. Record tool calls as they happen: `record_tool_call("code_edit")`
2. When task completes, record outcome: `record_sequence_outcome(success=True, task_type="code")`
3. Pattern scores update: success count, failure count, recency decay
4. On next task, `suggest_tools("code", candidates)` returns best-ordered tools

## Scoring

```
score = (success_count / total) * 0.7 + recency_bonus * 0.3
```

Recency decays over 1 week. Tools used < 2 times are neutral (0.5).

## Module

`ouroboros/temporal_learning.py`

## Integration

- Used by [[tool_router]] for semantic tool ordering
- Persisted to `.jo_data/tool_patterns.json`
- Feeds into episodic memory for outcome correlation

## Design Decisions

- Minimum 2 uses before scoring (prevents one-shot bias)
- Recency decay at 1 week prevents stale patterns from dominating
- Per-task-type scoring (code tools != research tools)

Related: [[tool_router]], [[episodic_memory]], [[principle_8__iterations]], [[tools]]
