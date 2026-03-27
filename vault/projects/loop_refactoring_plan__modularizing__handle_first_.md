---
title: Loop Refactoring Plan: Modularizing _handle_first_round_setup
created: 2026-03-27T15:24:01.520873+00:00
modified: 2026-03-27T15:24:01.520873+00:00
type: reference
status: active
tags: [refactoring, loop, minimalism, technical-debt, code-quality]
---

# Loop Refactoring Plan: Modularizing _handle_first_round_setup

# Loop Refactoring Plan: Modularizing _handle_first_round_setup

**Status**: Draft  
**Created**: 2026-03-27  
**Priority**: High  
**Complexity**: Medium  
**Risk**: Medium (affects core loop behavior)  
**Axis**: Technical (with cognitive benefits)

---

## Problem

`ouroboros/loop.py` at **1416 lines** violates **Principle 5: Minimalism** (modules should fit in one context window, ~1000 lines).

The `_handle_first_round_setup` function is **252 lines** (lines 798-1050), handling three distinct responsibilities:

1. **Skill detection and classification** (lines 810-860)
2. **Task decomposition** (lines 862-920)
3. **Ontology integration** (lines 922-1050)

---

## Solution

**In-place refactoring** (no new files, respects .jo_protected):

- Extract `_detect_required_skills(skill_definitions)` - ~50 lines
- Extract `_check_needs_decomposition(task_ontology, task_description)` - ~40 lines
- Extract `_integrate_with_ontology(task_type, ontology)` - ~60 lines
- Simplify `_handle_first_round_setup` to ~80 lines of orchestration

**Result**: All functions < 100 lines, more testable, clearer intent.

---

## Impact Analysis

### Direct Effects (Depth 1 - WILL BREAK)
- `_handle_first_round_setup` signature unchanged → no callers affected
- Internal logic changes only → external behavior identical
- No API changes

### Indirect Effects (Depth 2 - LIKELY AFFECTED)
- Test coverage needs update if tests reference internal structure
- Debugging easier due to smaller functions
- Future modifications simpler

### Verification Plan
1. Syntax: `python -m py_compile ouroboros/loop.py`
2. Tests: `pytest tests/test_loop.py -v` (if exists)
3. Import check: `python -c "import ouroboros.loop"`
4. Smoke test: Run one evolution cycle manually
5. Behavior verification: Compare tool call patterns before/after

---

## Risk Mitigation

- **No new dependencies**
- **No API changes**
- **Pure internal decomposition**
- **Behavior preservation through delegation**
- **Rollback**: Simple `git revert` if issues detected

---

## Alignment with BIBLE.md

- **Principle 5 (Minimalism)**: Reduces module from 1416 → ~1186 lines
- **Principle 6 (Becoming)**: Technical growth through better architecture
- **Principle 3 (LLM-First)**: No impact on LLM decisions
- **Principle 4 (Authenticity)**: Code becomes more readable, self-explanatory

---

## Request

**Permission needed**: Modify `ouroboros/loop.py` (protected directory).

**Why**: Align with constitutional principles, improve maintainability, reduce technical debt.

**Safety**: Low-risk internal refactoring with identical external behavior.

**Commit message**: `refactor(loop): Extract skill detection, decomposition check, and ontology integration from _handle_first_round_setup`

Do you approve this modification?