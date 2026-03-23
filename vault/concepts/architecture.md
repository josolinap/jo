---
title: architecture
created: 2026-03-20T11:59:03.614229+00:00
modified: 2026-03-23T09:01:00.000000+00:00
type: concept
status: active
tags: [architecture, system-design]
---

# architecture

# System Architecture

## Core Components

### Ouroboros (Agent Core)
- `agent.py` — Orchestrator (thin, delegates to loop/context/tools)
- `loop.py` — LLM tool loop with concurrent execution
- `context.py` — LLM context building and prompt caching
- `llm.py` — LLM client (OpenRouter integration)
- `memory.py` — Scratchpad, identity, chat history management
- `tool_executor.py` — Tool execution with stateful lifecycle

### Pipeline & Task Graph (new)
- `pipeline.py` — Multi-phase execution pipeline (plan → implement → verify)
- `task_graph.py` — DAG-based task decomposition and execution
- `eval.py` — Task evaluation framework
- `synthesis.py` — Semantic response synthesis
- `normalizer.py` — Code output normalization

### Code Intelligence (new)
- `codebase_graph.py` — Knowledge graph: nodes, edges, confidence scoring, impact analysis
- `context_enricher.py` — Pre-fetches relevant context before LLM calls
- `extraction.py` — Structured information extraction with source grounding
- `traceability.py` — Decision → action → result traceability

### Vault & Knowledge
- `vault_manager.py` — Obsidian-style vault with wikilinks, integrity, graph export
- `vault_parser.py` — Wikilink parser, frontmatter, block references
- `vault.py` — Thin re-export of vault_manager

### Cost & Health
- `cost_tracker.py` — Per-call cost tracking
- `health_auto_fix.py` — Auto-detect and fix common issues
- `hot_reload.py` — Detect changed files, notify model of changes
- `response_analyzer.py` — Response quality analysis

### Consciousness & Awareness
- `consciousness.py` — Background autonomous reasoning
- `awareness.py` — System state scanning (git, env, health)
- `spice.py` — Proactive message injection ("spice")

### Supervisor (Runtime)
- Telegram bot, message queue, workers
- Git operations and state management
- Event system and health monitoring

### Tools System (138 tools)
- Auto-discovery via `get_tools()` in modules
- Plugin architecture in `ouroboros/tools/`
- Schema-based tool definitions
- New: `codebase_impact` (blast radius), `symbol_context` (360-degree view)
- Confidence scoring on all graph relationships

## Design Principles

1. **LLM-First**: All decisions flow through LLM; code is transport
2. **Delegated Reasoning**: Orchestrator decomposes; specialized agents execute
3. **Minimalism**: Each module fits in one context window (~1000 lines)
4. **Self-Contained**: The entire system must be readable in one session
5. **Confidence**: Code intelligence carries confidence scores (0.0-1.0) on relationships

## Key Flows

- **Message Processing**: Telegram → Queue → Worker → Agent Loop → Tools → Response
- **Evolution Cycle**: Assessment → Selection → Implementation → Review → Commit → Restart
- **Memory Hierarchy**: Identity (manifesto) → Scratchpad (working) → Vault (persistent knowledge)
- **Pipeline**: Plan → Decompose → Execute → Verify → Synthesize
- **Impact Analysis**: Edit → Blast radius → Depth grouping → Confidence filtering

## Code Intelligence (GitNexus-inspired)

The codebase graph system provides:
- **AST-based parsing** of Python files (nodes: file/class/function/import)
- **Confidence scoring** on all edges (imports=0.85, AST calls=0.9, heuristic=0.3)
- **Blast radius analysis** with depth grouping (d1=WILL BREAK, d2=AFFECTED, d3=TESTING)
- **360-degree symbol context** — callers, callees, cluster membership
- **Louvain community detection** for functional clustering (with DFS fallback)

## Invariants
- VERSION sync: VERSION == git tag == README changelog
- Tool registry must be complete and functional
- Health checks: verification, budget, duplicate processing, identity freshness
- Code graph confidence: AST-resolved > heuristic

*This architecture enables agency through simplicity and coherence.*
Architecture embodies [[Principle 3: LLM-First]]
Structure follows [[Principle 5: Minimalism]]
Code intelligence inspired by [[GitNexus Analysis]]
