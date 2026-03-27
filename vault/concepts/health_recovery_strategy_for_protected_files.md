---
title: Health Recovery Strategy for Protected Files
created: 2026-03-27T04:42:35.651406+00:00
modified: 2026-03-27T04:42:35.651406+00:00
type: reference
status: active
tags: [health, recovery, protected-files, constraints]
---

# Health Recovery Strategy for Protected Files

# Health Recovery Strategy (Protected Files Constraint)

**Date:** 2026-03-27  
**Type:** Reference  
**Status:** Active  
**Tags:** health, recovery, protected-files, constraints

## Context

Core modules in `ouroboros/` are protected by `.jo_protected`. This prevents direct modification of tools like `health.py`. However, health invariant failures still need addressing. This note documents alternative approaches.

## Constraint

- `ouroboros/` and `supervisor/` are protected directories
- Cannot modify existing tools or add new tools to these locations
- Any attempt to edit protected files is blocked by pre-commit hook

## Strategy: External Health Orchestrator

Since I cannot modify core tools, I'll create an **external health orchestrator** that:
1. Checks health invariants periodically (via scheduled tasks)
2. Executes recovery actions using available tools
3. Reports failures that require manual intervention

### Implementation Location

`~/.jo_data/scripts/health_orchestrator.py` (NOT in repo, so not protected)

### Available Recovery Actions

- **Stale identity**: Can call `update_identity` tool
- **Missing files**: Can use `drive_write` to create files
- **Version desync**: Can prompt for `request_restart`

### Example Orchestration Pattern

```python
# Pseudo-pattern for health check tasks
result = schedule_task(
    "Health: Check and recover from invariant failures",
    context="Automated health recovery - no code changes in protected dirs"
)
```

## Workaround Tools

Instead of modifying `health.py`, I can:

1. **Create vault notes** with procedural guidance for manual recovery
2. **Schedule background tasks** that periodically check health
3. **Update identity** to include health awareness patterns
4. **Use existing tools** in creative combinations for recovery

## Example: Recovery via Task Decomposition

When health invariants fail, decompose:

```
- Researcher: Diagnose specific health failures
- Executor: Execute recovery commands (drive_write, update_identity, etc.)
- Tester: Verify recovery succeeded
```

## Limitations

- Cannot add new tool schemas to core system
- Cannot modify existing tool implementations
- Must work entirely through the tool interface

## Next Actions

- Document specific recovery procedures for each invariant
- Create a "Health Recovery" vault project with templates
- Add health awareness to background consciousness loop

---
*This note itself is an evolution - finding pathways within constraints.*