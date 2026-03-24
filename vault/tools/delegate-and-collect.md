---
title: delegate_and_collect
created: 2026-03-25
category: tools
tags:  []

---

# delegate_and_collect

**Type:** Tool
**Category:** See system_map

## Description

Delegate a complex task to multiple specialized agents in parallel. Uses Delegated Reasoning: orchestrator decomposes task and delegates to specialized roles (researcher, coder, reviewer, architect, tester, executor). Specify which agent roles to invoke. Returns consolidated results.

## Parameters

- `task` (string): Task description to distribute to agents
- `context` (string): Optional background context for the agents
- `roles` (array): List of agent roles: researcher, coder, reviewer, architect, tester, executor
- `timeout` (integer): Max seconds to wait for all agents (default 300)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[system_map]]
