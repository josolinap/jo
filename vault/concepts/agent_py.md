---
title: agent.py
created: 2026-03-21T05:20:22.384851+00:00
modified: 2026-03-21T05:20:22.384851+00:00
type: reference
status: active
tags: [code, module, ouroboros, core]
---

# agent.py

# agent.py

**Type:** Source Module  
**Component:** Ouroboros  
**Responsibility:** Thin orchestrator that delegates to loop/context/tools

## Purpose

`agent.py` is the entry point for Jo's reasoning core. It does NOT execute work directly but orchestrates the agent loop.

## Key Responsibilities

- Initialize the agent system (loop, context, memory, tools)
- Process incoming messages through the LLM tool loop
- Handle tool execution and result processing
- Manage conversation context and state
- Coordinate with supervisor for external events

## Design Principles

- **Thin layer** - delegates to specialized components
- **LLM-First** - all decisions flow through the language model
- **Delegated Reasoning** - orchestrator doesn't write code, it decomposes tasks

## Integration Points

- Calls `loop.py` for LLM-driven tool execution
- Uses `context.py` for prompt building
- Uses `memory.py` for identity, scratchpad, history
- Discovers tools from `ouroboros/tools/` modules
- Communicates with `supervisor/` via message queue

## Related

- [[loop.py]] - The actual LLM tool loop
- [[context.py]] - Context building and caching
- [[memory.py]] - Memory management
- [[Delegated Reasoning]] - Architecture pattern

*This module must remain thin - complexity belongs in specialized components.*