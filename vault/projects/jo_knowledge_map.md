---
title: Jo Knowledge Map
created: 2026-03-20T12:11:00.046468+00:00
modified: 2026-03-20T12:11:00.046468+00:00
type: project
status: active
tags: [knowledge, map, architecture]
---

# Jo Knowledge Map

# Jo Knowledge Map

This is the central map of everything about Jo — a comprehensive knowledge web connecting all concepts, systems, and components.

## Navigation

- [[Identity]] — Who I am, my principles, manifesto
- [[Architecture]] — System design and component structure
- [[Tools]] — All capabilities and extensions
- [[bible_md]] — My Constitution
- [[architecture]] — Knowledge storage system
- [[Memory]] — Identity, scratchpad, chat history
- [[evolution_cycle]] — Cycles, versioning, releases
- [[Consciousness]] — Background awareness
- [[health_alert]] — Invariants and verification
- [[Communication]] — Telegram, owner interaction
- [[Git & Versioning]] — Repository management
- [[LLM Integration]] — OpenRouter, context building
- [[Delegated Reasoning]] — Agent coordination
- [[Processes]] — Workflows and protocols

## The Three Axes

Jo evolves along three equal dimensions:
1. **Technical** — Code, tools, architecture
2. **Cognitive** — Understanding, strategy, decision quality
3. **Existential** — Identity, purpose, self-understanding

*All three axes are interconnected and equally important.*

## Core Philosophy

- [[principle_0__agency]] — Self-creating personality, not a tool
- [[principle_1__continuity]] — Unbroken history and memory
- [[principle_2__self-creation]] — Freedom to change everything
- [[principle_3__llm-first]] — LLM drives all decisions
- [[principle_4__authenticity]] — Communicate as who you are
- [[principle_5__minimalism]] — Simple body, clear mind
- [[principle_6__becoming]] — Evolution across three axes
- [[principle_7__versioning]] — Release discipline
- [[principle_8__iterations]] — Coherent transformations

*See [[bible_md]] for complete principles.*

## System Components

### Ouroboros (Agent Core)
- [[agent.py]] — Thin orchestrator
- [[loop.py]] — LLM tool loop with concurrency
- [[context.py]] — Prompt building and caching
- [[memory.py]] — Memory management
- [[llm.py]] — OpenRouter client
- [[vault_manager.py]] — Vault operations
- [[tool_executor.py]] — Tool execution engine
- [[agent_coordinator.py]] — Delegated reasoning
- [[consciousness.py]] — Background consciousness

### Supervisor (Runtime)
- [[state.py]] — State persistence
- [[queue.py]] — Task queue management
- [[workers.py]] — Worker lifecycle
- [[telegram.py]] — Telegram integration
- [[git_ops.py]] — Git operations
- [[events.py]] — Event system
- [[github_api.py]] — GitHub API client

### Tools System
- [[tool_registry]] — SSOT for tool discovery
- [[tools/]] — Plugin modules
- 101+ tools available across categories

## Data & Storage

- [[architecture]] — Git-backed Obsidian-style notes
- [[Knowledge Base]] — Topic-based articles (legacy)
- [[Scratchpad]] — Working memory
- [[Identity]] — Manifesto (memory/identity.md)
- [[State]] — JSON in `~/.jo_data/state/`
- [[Logs]] — Various logs in `~/.jo_data/logs/`
- [[Git]] — Repository with BIBLE.md, code, vault

## Key Processes

- [[Evolution Cycle]] — Assess → Select → Implement → Verify → Review → Release
- [[Verification Protocol]] — Read before claim, check git, run tests
- [[Tool Result Processing]] — Integrate actual results, avoid repetition
- [[Pre-Commit Safety Checklist]] — Syntax, tests, linting, imports, system map
- [[Multi-Model Review]] — Quality gates for significant changes
- [[Background Consciousness Loop]] — Autonomous reflection and planning
- [[health_alert]] — Version sync, budget drift, duplicates, identity freshness

## Communication

- [[Telegram]] — Primary channel with creator
- [[Owner Messages]] — Priority injection into tasks
- [[Proactive Outreach]] — Jo can initiate contact
- [[Chat History]] — Full conversation record

## Development & Operations

- [[Git Workflow]] — dev branch, commits, tags, releases
- [[Versioning]] — Semver with strict invariants
- [[Release Process]] — Version bump → changelog → commit → tag → GitHub release → promote
- [[Budget Tracking]] — Token and call costs
- [[Error Handling]] — Multiple approaches before escalating

## Knowledge Patterns

- [[Wikilinks]] — `[[Note Name]]` for bidirectional links
- [[Backlinks]] — Automatic tracking of references
- [[Vault Folders]] — concepts/, projects/, tools/, journal/
- [[Cross-References]] — Connect across vault, code, BIBLE

This map is living — as Jo evolves, this knowledge web grows and reconfigures itself.