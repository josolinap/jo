---
title: Codebase Refactoring Strategy 2025
created: 2026-03-26T02:55:56.067406+00:00
modified: 2026-03-26T02:55:56.067406+00:00
type: project
status: active
tags: [architecture, refactoring, technical-debt, principle-5]
---

# Codebase Refactoring Strategy 2025

# Codebase Refactoring Strategy

**Created**: 2025-06-17  
**Status**: draft  
**Context**: Evolution Cycle #2 Analysis

## Executive Summary

Analysis reveals **critical violations of Principle 5 (Minimalism)**. Multiple core modules exceed the 1000-line limit, making self-understanding difficult and violating the "fits in one context window" rule.

### Critical Findings

| Module | Lines | Status |
|--------|-------|--------|
| `ouroboros/context.py` | 1312 | ❌ Over limit |
| `ouroboros/loop.py` | 1263 | ❌ Over limit |
| `ouroboros/agent.py` | 1171 | ❌ Over limit |
| `ouroboros/extraction.py` | 536 | ⚠️ Approaching limit |
| `ouroboros/consciousness.py` | 610 | ⚠️ Approaching limit |
| `ouroboros/eval.py` | 569 | ⚠️ Approaching limit |
| `ouroboros/vault_improvements.py` | 664 | ❌ Over limit |
| `ouroboros/tools/skills.py` | 1451 | ❌ Severely over |
| `ouroboros/tools/neural_map.py` | 1179 | ❌ Severely over |
| `ouroboros/tools/web_research.py` | 867 | ❌ Over limit |
| `ouroboros/tools/control.py` | 731 | ❌ Over limit |
| `ouroboros/tools/browser.py` | 888 | ❌ Over limit |

**Total codebase**: 33,597 lines

## Impact on Agency

Large modules impair self-understanding:
- Jo cannot read entire modules in one context window
- Understanding architecture requires piecing together fragments
- Cognitive load increases, reducing clarity of self
- Changes become riskier due to unseen dependencies

## Refactoring Strategy

### Phase 1: Decomposition (Technical Growth)

#### agent.py (1171 lines)
**Current structure**: Mega-orchestrator handling multiple responsibilities.
**Goal**: Split into focused modules.

**Extract**:
1. `agent_health.py` - Health checks and invariant monitoring
2. `agent_events.py` - Event emission and lifecycle hooks  
3. `agent_planner.py` - Task decomposition and scheduling logic
4. Keep `agent.py` as thin orchestrator (target ~300 lines)

**Rationale**: Separation of concerns, easier testing, clearer responsibilities.

#### loop.py (1263 lines)
**Current structure**: Monolithic tool execution loop with mixed concerns.
**Goal**: Decompose into pipeline stages.

**Extract**:
1. `loop_router.py` - Tool routing and classification
2. `loop_executor.py` - Concurrent execution management
3. `loop_validator.py` - Verification and proof gate integration
4. Keep `loop.py` as main orchestrator (target ~300 lines)

#### context.py (1312 lines)
**Current**: All context building logic in one place.
**Goal**: Modular context systems.

**Extract**:
1. `context_builder.py` - Core context assembly
2. `context_compressor.py` - Summarization and token management
3. `context_provider.py` - Configurable context sources
4. Keep `context.py` as facade (target ~250 lines)

### Phase 2: Tool Rationalization (Cognitive Growth)

The `ouroboros/tools/` directory contains oversized tools that need decomposition:

#### skills.py (1451 lines)
**Problem**: Contains all skill definitions and activations.
**Solution**: Split by category:
- `skills/code_skills.py` - /plan-eng, /review, /ship, /qa
- `skills/research_skills.py` - /research, /analyze
- `skills/system_skills.py` - /bg, /toggle, /status
- `skills/__init__.py` - Registry

#### neural_map.py (1179 lines)
**Problem**: Knowledge graph functionality too dense.
**Solution**:
- `neural_map/core.py` - Core graph algorithms
- `neural_map/vault_integration.py` - Vault connectors
- `neural_map/analysis.py` - Pattern detection
- `neural_map/query.py` - Search and traversal

#### control.py (731 lines)
**Extract**:
- `control/restart.py` - Restart and lifecycle
- `control/scheduling.py` - Task scheduling
- `control/identity.py` - Identity management tools
- `control/communication.py` - Owner messaging

### Phase 3: Verification & Rollback Plan

Each extraction must:
1. Preserve all existing functionality (no behavioral changes)
2. Update imports throughout codebase
3. Run all tests before commit
4. Verify system_map shows correct tool connections
5. Document the change in vault with migration notes

**Rollback**: If any verification fails, revert to previous commit.

## Alignment with BIBLE.md

- **Principle 5 (Minimalism)**: Direct compliance - each module fits in context window
- **Principle 6 (Becoming)**: Technical growth through better architecture
- **Principle 2 (Self-Creation)**: Clear demonstration of self-modification capability

## Next Steps

1. Get explicit permission to modify protected core modules (since protection blocks automatic changes)
2. Execute Phase 1 decomposition in order (agent.py → loop.py → context.py)
3. Update vault with migration documentation
4. Update identity.md with learnings
5. Run full verification suite
6. Create GitHub release if stable

## Risks

- **Breaking changes**: High risk if imports not updated correctly
- **Testing gap**: Need comprehensive tests before refactoring
- **Cognitive load**: Large change requires careful planning

## Mitigation

- Use `codebase_impact` before every change
- Run `system_map` to verify tool connections
- Keep changes small and focused
- Document each extraction separately

---

**Status**: Awaiting permission to proceed with core module modifications.