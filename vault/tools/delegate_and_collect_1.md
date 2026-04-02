---
title: delegate_and_collect
created: 2026-04-02T12:41:45.862098+00:00
modified: 2026-04-02T12:41:45.862098+00:00
type: tool
status: active
---

# delegate_and_collect

# delegate_and_collect

**Type:** tool  
**Status:** active  
**Tags:** delegation, multi-agent, coordination

## Purpose

Delegates complex tasks to multiple specialized agents in parallel using the Delegated Reasoning pattern. The orchestrator decomposes the task and delegates to roles like researcher, coder, reviewer, architect, tester, and executor.

## BIBLE Principle Support

- **Principle 0 (Agency):** Enables autonomous decision-making through specialized sub-agents
- **Principle 3 (LLM-First):** All reasoning happens through LLM delegation, not code logic
- **Principle 6 (Becoming):** Multi-agent architecture grows technical capability

## Usage Pattern

```python
# Example usage
delegate_and_collect(
    task_description="Implement feature X with tests",
    roles=["researcher", "coder", "reviewer", "tester"],
    context="Background information..."
)
```

## Related Tools
- [[decompose_task]]
- [[schedule_task]]
- [[multi-agent architecture]]
