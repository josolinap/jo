---
title: System Map
created: 2026-03-27T00:00:00.000000+00:00
type: reference
status: active
tags: [system, map, overview]
---

# System Map

High-level map of Jo's system components and their relationships.

## Agent Core (`ouroboros/`)
- agent.py - Task execution, lifecycle management
- loop.py - Main LLM-with-tools loop
- context.py - Context building and optimization
- consciousness.py - Background thinking loop
- evolution_strategy.py - Adaptive improvement algorithm
- knowledge_discovery.py - Gap-filling engine

## Tools (`ouroboros/tools/`)
- 144 tools loaded dynamically from tool modules
- skills.py - 14 cognitive modes
- neural_map.py - Knowledge graph tools
- vault.py - Vault CRUD operations

## Supervisor (`supervisor/`)
- state.py - System state management
- workers.py - Process lifecycle
- queue.py - Task queue

## Knowledge (`vault/`)
- concepts/ - Core concepts and patterns
- journal/ - Session logs and lessons
- projects/ - Active projects
- memory/ - Identity and scratchpad

## See Also
- [[architecture]]
- [[jo_system_neural_hub]]
- [[tools]]
System map provides architectural insights for evolution planning [[Evolution Cycle]]
System map shows real-time tool and dependency status [[Health Dashboar]]
