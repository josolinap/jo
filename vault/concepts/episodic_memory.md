---
title: Episodic Memory
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [memory, learning, episodes, safla]
---

# Episodic Memory

Records decisions, actions taken, and their outcomes. Enables "what happened last time I did X?" queries.

## Structure

Each episode = {decision, action, outcome, context, success, tools_used, concepts_involved}

## Module

`ouroboros/episodic_memory.py`

## Key API

```python
memory = get_episodic_memory(repo_dir)

# Record
memory.record("Fix vault staleness", "Ran scan_repo", "Vault updated",
              success=True, tools_used=["codebase_impact"])

# Recall by query
episodes = memory.recall("vault", limit=5)

# Recall by tool
episodes = memory.recall_by_tool("code_edit")

# Success rate
rate = memory.get_success_rate("code")
```

## Storage

Append-only JSONL at `.jo_data/memory/episodes.jsonl`. Max 500 episodes (auto-trimmed).

## Integration

- Records after every significant task
- Feeds into temporal tool learning for pattern correlation
- Success rate used by delta evaluation

## Design Decisions

- Append-only JSONL (survives crashes, no corruption risk)
- Text matching for recall (simple, fast, no embeddings needed)
- Max 500 episodes prevents unbounded growth
- Separate from vault notes (vault = knowledge, episodes = experience)

Related: [[temporal_tool_learning]], [[delta_evaluation]], [[principle_1__continuity]], [[jo_system_neural_hub]]
