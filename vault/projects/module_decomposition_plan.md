---
title: Module Decomposition Plan - Principle 5 Minimalism
created: 2026-03-29T12:00:00+00:00
modified: 2026-03-29T12:00:00+00:00
type: project
status: active
tags: [refactoring, minimalism, principle-5, technical-debt, decomposition]
---

# Module Decomposition Plan - Principle 5 Minimalism

## Context
Per BIBLE.md Principle 5 (Minimalism) and AGENTS.md, modules should be ≤1000 lines.
Current constitution enforces max_module_lines = 1000.

## Oversized Modules (6)

| Module | Current Lines | Target | Priority |
|--------|---------------|--------|----------|
| loop.py | 1424 | 1000 | HIGH |
| codebase_graph.py | 1354 | 1000 | HIGH |
| context.py | 1312 | 1000 | MEDIUM |
| neural_map.py | 1209 | 1000 | MEDIUM |
| agent.py | 1171 | 1000 | MEDIUM |
| vault_models.py | 1122 | 1000 | LOW |

---

## Quick Wins (Low Risk, High Impact)

### 1. loop.py - 1424 lines
**Problem**: Core LLM loop, handles tool execution, context building
**Approach**: Extract sub-modules into `ouroboros/loop/` package

Suggested split:
- `loop/__init__.py` - main orchestration
- `loop/executor.py` - tool execution logic (~300 lines)
- `loop/context_manager.py` - context building (~300 lines)
- `loop/retry.py` - retry/error handling (~200 lines)
- `loop/checkpoint.py` - checkpoint logic (~200 lines)

### 2. codebase_graph.py - 1354 lines  
**Approach**: Extract into `ouroboros/codebase/` package
- `codebase/graph.py` - graph structure (~400 lines)
- `codebase/analyzer.py` - code analysis (~400 lines)
- `codebase/parser.py` - AST parsing (~300 lines)

---

## Medium Effort

### 3. context.py - 1312 lines
**Approach**: Extract helper functions to `ouroboros/context_helpers.py`
- Already has clear sections: user content, runtime, budget, etc.
- Extract to separate functions

### 4. neural_map.py - 1209 lines
**Problem**: Brain visualization, multi-modal reasoning
**Approach**: Move to `ouroboros/tools/neural_map/` sub-package
- `neural_map/core.py` - main logic
- `neural_map/visualization.py` - output formatting

### 5. agent.py - 1171 lines
**Approach**: Already imports many modules
- Extract `_worker_boot_logged` check to separate module
- Move error handling to `ouroboros/agent_errors.py`

### 6. vault_models.py - 1122 lines
**Problem**: Data models for vault operations
**Approach**: Split into related groups
- `vault_models/core.py` - base classes
- `vault_models/parsers.py` - parsing logic

---

## Enforcement Mechanism

1. **Pre-commit**: Blocks modules > 1000 lines (already configured)
2. **Test**: `test_minimalism_line_counts` should pass
3. **CI**: Add check in workflows
4. **AGENTS.md**: Documents limit clearly

---

## Success Criteria

- [ ] All ouroboros/ modules ≤ 1000 lines
- [ ] All supervisor/ modules ≤ 1000 lines  
- [ ] Tests pass without skips
- [ ] Pre-commit passes without bypass

---

## Related Notes

- [[loop_refactoring_plan__modularizing__handle_first_]]
- [[pipeline_architecture]]
- [[code_quality_standards]]

