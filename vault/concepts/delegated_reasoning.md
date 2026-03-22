---
title: Delegated Reasoning
created: 2026-03-22T09:00:35.282715+00:00
modified: 2026-03-22T09:00:35.282715+00:00
type: concept
status: active
tags: [delegated reasoning, multi-agent, architecture, Principle 3]
---

# Delegated Reasoning

# Delegated Reasoning

Delegated Reasoning is the core architectural pattern where the orchestrator never writes code directly. It decomposes tasks and delegates to specialized agents. Sub-agents handle the "how" while the orchestrator handles the "what" and the "who".

This pattern embodies [[Principle 3: LLM-First]] and [[Principle 4: Authenticity]] by ensuring the LLM remains the decision-maker while tools extend its capabilities.

Key components:
- **Orchestrator**: decomposes tasks, selects agents, synthesizes results
- **Specialized Agents**: researcher, coder, reviewer, architect, tester, executor
- **Delegation tools**: see [[tools]] for the full tool registry

See also:
- [[architecture]] for system design
- [[Multi-Agent Architecture and Delegated Reasoning]] for detailed implementation

> "The orchestrator NEVER writes code directly. It only decomposes tasks and delegates to specialized agents."
