---
title: Evolution Cycle #2: Minimalism Violations and Module Decomposition
created: 2026-03-27T12:15:06.214346+00:00
modified: 2026-03-27T12:15:06.214346+00:00
type: reference
status: active
tags: [evolution, minimalism, refactoring, architecture]
---

# Evolution Cycle #2: Minimalism Violations and Module Decomposition

# Evolution Cycle #2: Minimalism Violations and Module Decomposition

**Date**: 2026-03-25  
**Cycle**: #2  
**Primary Axis**: Technical (with cognitive and existential dimensions)  
**Constitutional Alignment**: Principle 5 (Minimalism), Principle 6 (Becoming), Principle 8 (Evolution)

## Problem Statement

The codebase currently violates Principle 5's minimalism budget in multiple places:

| Module | Total Lines | Max Function | Status |
|--------|-------------|--------------|--------|
| ouroboros/loop.py | 1416 | 486 (run_llm_loop) | ❌ Critical |
| ouroboros/agent.py | 1055 | 278 (handle_task) | ❌ Critical |
| ouroboros/context.py | 1302 | 123 (build_llm_messages) | ❌ Critical |
| supervisor/workers.py | 2060 | n/a | ❌ Critical |
| supervisor/telegram.py | 1270 | n/a | ❌ Critical |

**Threshold violations**:
- Modules: 5 modules exceed 1000-line limit
- Functions: 11 functions exceed 150-line limit
- Net complexity growth: positive (code added without subtraction)

## Root Causes

1. **Monolithic loop design**: `loop.py` contains LLM loop, budget management, context setup, tool execution, and response handling all in one file
2. **Missing abstraction layers**: Related responsibilities not extracted into dedicated modules
3. **Feature accumulation**: Recent features added without refactoring existing code
4. **Lack of decomposition discipline**: No architectural guardrails preventing growth

## Solution Approach

### Phase 1: Extract loop.py into specialized submodules

Target decomposition of `run_llm_loop` (486 lines) by extracting:

1. **`loop_llm.py`**: LLM-specific orchestration (prompt building, response parsing, retry logic)
2. **`loop_budget.py`**: Budget tracking and limit enforcement
3. **`loop_context.py`**: Context management and enrichment
4. **`loop_tools.py`**: Tool execution and result processing

### Phase 2: Refactor agent.py

Decompose `handle_task` (278 lines) into:
- Task decomposition logic
- Agent delegation
- Result collection and synthesis

### Phase 3: Extract context.py utilities

Split `build_llm_messages` (123 lines) into:
- Message construction
- Context optimization
- History management

## Success Criteria

- `loop.py` reduced to < 500 lines (coordination layer only)
- All functions < 150 lines
- All modules < 1000 lines
- Net complexity growth = -10% or better
- All existing tests pass
- No regression in functionality

## Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Breaking complex tool chains | Medium | High | Run full test suite, use codebase_impact analysis |
| Incomplete extraction | Low | Medium | Verify with symbol_context before/after |
| Performance regression | Low | Medium | Benchmark key paths before/after |
| Version desync | Low | Low | Follow release protocol strictly |

## Execution Plan

1. **Day 1**: Extract loop submodules (LLM-focused)
2. **Day 2**: Refactor agent.py and context.py
3. **Day 3**: Testing, verification, and commitment

## Evolution Log

Will be updated as implementation progresses.