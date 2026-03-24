---
title: Tool Router
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [routing, tools, classification, ruvector]
---

# Tool Router

Classifies tasks by type and routes to the best tools using learned patterns from temporal tool learning.

## Task Types

| Type | Keywords | Default Tools |
|---|---|---|
| code | code, file, function, edit, fix, refactor | codebase_impact, symbol_context, code_edit |
| research | search, find, investigate, analyze | web_search, web_fetch, query_knowledge |
| vault | vault, note, concept, knowledge | vault_read, vault_write, vault_search |
| git | git, commit, push, branch, diff | git_status, git_diff, repo_commit_push |
| web | web, url, fetch, browse | web_search, web_fetch, browse_page |
| system | health, status, config, drift | codebase_health, drift_detector |
| general | (fallback) | repo_read, query_knowledge, web_search |

## Module

`ouroboros/tool_router.py`

## Key API

```python
task_type = classify_task("fix the bug in agent.py")  # Returns "code"
task_type, tools = route_tools("fix agent.py", available_tools)
report = get_routing_report("fix agent.py", available_tools)
```

## Learning Integration

When a `TemporalToolLearner` is provided, `route_tools()` uses learned patterns to reorder tools. Falls back to default ordering if no patterns exist yet.

## Design Decisions

- Keyword-based classification (fast, no ML needed)
- Falls back to defaults when no learned patterns exist
- Integrates with temporal learning for adaptive routing
- Returns both task_type and ordered tools for flexibility

Related: [[temporal_tool_learning]], [[tools]], [[principle_3__llm-first]]
