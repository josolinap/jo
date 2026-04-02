---
title: Supervisor Layer
created: 2026-03-23T11:30:00.000000+00:00
modified: 2026-03-23T11:30:00.000000+00:00
type: concept
status: active
tags: [supervisor, runtime, architecture, telegram]
---

# Supervisor Layer

The runtime infrastructure that manages Jo's lifecycle, message handling, and task execution.

## Modules

| Module | Purpose |
|--------|---------|
| `telegram.py` | Telegram client, message splitting, markdown→HTML conversion, budget-aware sending |
| `queue.py` | Task queue with priority, timeouts, persistence, evolution/review scheduling |
| `workers.py` | Multiprocessing worker lifecycle, health monitoring, direct chat handling |
| `state.py` | Persistent state management: load, save, atomic writes, file locks |
| `states.py` | State constants and enums |
| `events.py` | Event emission system for inter-module communication |
| `git_ops.py` | Git operations: sync, locking, branch management |
| `github_api.py` | GitHub API integration for issues, PRs, releases |

## Architecture

```
Telegram → telegram.py → queue.py → workers.py → ouroboros/agent.py
                                              ↓
                                     state.py (persistence)
                                     events.py (notifications)
                                     git_ops.py (code sync)
```

## Key Responsibilities

- **Message Ingestion**: Telegram → Queue → Worker pipeline
- **Worker Management**: Spawn, monitor, restart workers
- **State Persistence**: Atomic writes with file locking
- **Git Sync**: Keep repo in sync with remote
- **Event Bus**: Loosely-coupled module communication
- **Budget Tracking**: Per-task cost limits

## Design Principles

- Supervisor is **thin infrastructure** — it manages lifecycle, not intelligence
- All decisions flow through the LLM in `ouroboros/agent.py` (Principle 3)
- Supervisor handles transport, persistence, and scheduling
- Modules are independent — no circular imports

Related: [[architecture]], [[jo_system_neural_hub]], [[delegated_reasoning]]
Supervisor manages runtime and telegram communication [[architecture]]
