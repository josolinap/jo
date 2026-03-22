---
title: architecture
created: 2026-03-20T11:59:03.614229+00:00
modified: 2026-03-20T11:59:03.614229+00:00
type: concept
status: active
tags: [architecture, system-design]
---

# architecture

# System Architecture

## Core Components

### Ouroboros (Agent Core)
- `agent.py` - Orchestrator (thin, delegates to loop/context/tools)
- `loop.py` - LLM tool loop with concurrent execution
- `context.py` - LLM context building and prompt caching
- `memory.py` - Scratchpad, identity, chat history management
- `llm.py` - LLM client (OpenRouter integration)

### Supervisor (Runtime)
- Telegram bot, message queue, workers
- Git operations and state management
- Event system and health monitoring

### Tools System
- Auto-discovery via `get_tools()` in modules
- Plugin architecture in `ouroboros/tools/`
- Schema-based tool definitions

## Design Principles

1. **LLM-First**: All decisions flow through LLM; code is transport
2. **Delegated Reasoning**: Orchestrator decomposes; specialized agents execute
3. **Minimalism**: Each module fits in one context window (~1000 lines)
4. **Self-Contained**: The entire system must be readable in one session

## Key Flows

- **Message Processing**: Telegram → Queue → Worker → Agent Loop → Tools → Response
- **Evolution Cycle**: Assessment → Selection → Implementation → Review → Commit → Restart
- **Memory Hierarchy**: Identity (manifesto) → Scratchpad (working) → Vault (persistent knowledge)

## Invariants
- VERSION sync: VERSION == git tag == README changelog
- Tool registry must be complete and functional
- Health checks: verification, budget, duplicate processing, identity freshness

*This architecture enables agency through simplicity and coherence.*
Architecture embodies [[Principle 3: LLM-First]]
Structure follows [[Principle 5: Minimalis]]
