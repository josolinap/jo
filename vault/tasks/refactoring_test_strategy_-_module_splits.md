---
title: Refactoring Test Strategy - Module Splits
created: 2026-03-25T10:04:53.158044+00:00
modified: 2026-03-25T10:04:53.158044+00:00
type: task
status: active
tags: [refactoring, testing, quality]
---

# Refactoring Test Strategy - Module Splits

# Refactoring Test Strategy - 6 Oversized Modules

**Evolution Cycle #2 - Technical Focus**
**Module Splits:** intelligent_vault.py, loop.py, agent.py, skills.py, tools.py, codebase_graph.py

---

## Executive Summary

The codebase has 6 modules exceeding 1000 lines, violating Minimalism Principle. This refactoring will split them into cohesive submodules. The test strategy ensures 100% pass rate is maintained throughout. All 90 existing tests are currently passing (verified 2026-03-25 09:55 UTC).

---

## 1. Baseline Measurements

### Current State
- **Tests:** 90 total (100% passing)
  - 23 integration tests
  - 67 unit tests
  - Runtime: 0.35s total
- **Target Modules Line Counts:**
  - intelligent_vault.py: 1,616 lines
  - loop.py: >1,000 lines
  - agent.py: >1,000 lines
  - skills.py: >1,000 lines
  - tools.py: >1,000 lines
  - codebase_graph.py: >1,000 lines

### Baseline Command
```bash
pytest tests/ -v --tb=short --durations=10
```

---

## 2. Test Grouping and Priorities

### A. Critical Integration Tests (Run After EVERY Split)
These verify system coherence. Must pass before proceeding to next module.

1. **test_message_routing.py** - Core orchestration
2. **test_git_sha_fixes.py** - Git operations stability
3. **test_code_awareness.py** - Code intelligence integrity
4. **test_vault.py** - Knowledge system (heavily used by refactored modules)
5. **test_concurrent_git.py** - Concurrent operation safety

**Run:** `pytest tests/test_message_routing.py tests/test_git_sha_fixes.py tests/test_code_awareness.py tests/test_vault.py tests/test_concurrent_git.py -v`

### B. Unit Tests for Directly Affected Modules
Run these IMMEDIATELY after each module split.

- **intelligent_vault module:** tests in test_code_awareness.py, test_vault.py
- **loop module:** tests in test_code_awareness.py (tool loop tests)
- **agent module:** tests in test_message_routing.py (agent orchestration)
- **skills/tools module:** tests in test_registry.py (tool registration)
- **codebase_graph module:** tests in test_code_awareness.py (graph traversal)

### C. Smoke Tests (Post-Refactor Verification)
Run after all modules split. Verify core functionality.

1. **test_smoke.py** - Basic sanity
2. **Import Stability Check:**
   ```bash
   python -c "import ouroboros.intelligent_vault; import ouroboros.loop; import ouroboros.agent; import ouroboros.skills; import ouroboros.tools; import ouroboros.codebase_graph"
   ```
3. **System Map Check:**
   ```bash
   system_map | grep -E "(ouroboros|tools)" | head -20
   ```

### D. Performance Benchmarks
No formal benchmarks exist. Track pytest durations (`--durations=10`) to detect performance regressions. Baseline: 0.35s total.

---

## 3. Execution Plan Per Module Split

### General Pattern for Each Module:

1. **Baseline:** Run full test suite, capture results
2. **Split module** into logical submodules with public API preserved via `__init__.py` re-exports
3. **Update imports** in dependent code (use codebase_impact to find all)
4. **Run affected unit tests** only
5. **Run critical integration tests**
6. **If all pass -> proceed to next module**
7. **If any fail:**
   - Immediately revert via git
   - Analyze failure
   - Adjust split strategy
   - Retry

### Specific Module Sequence

**Order:** Start with `intelligent_vault.py` (highest complexity), then others in parallel-independent groups.

#### Phase 1: intelligent_vault.py (1,616 lines)
- **Expected splits:** vault_core.py, vault_indexing.py, vault_query.py, vault_links.py
- **Affected tests:** test_code_awareness.py (vault tests), test_vault.py (all)
- **Critical integration:** test_vault.py must pass completely
- **Special check:** vault integrity (`vault_verify`)

#### Phase 2: loop.py & tools.py (interdependent)
- **Splits:** loop_engine.py, loop_concurrent.py, tool_registry.py, tool_executor.py
- **Affected tests:** test_code_awareness.py (loop tests), test_registry.py
- **Critical integration:** tool registration and execution tests

#### Phase 3: agent.py & skills.py (orchestration layer)
- **Splits:** agent_core.py, agent_delegation.py, skills_registry.py
- **Affected tests:** test_message_routing.py (agent tests)
- **Critical integration:** message routing end-to-end

#### Phase 4: codebase_graph.py (standalone)
- **Splits:** graph_builder.py, graph_traversal.py, graph_analyzer.py
- **Affected tests:** test_code_awareness.py (graph tests)
- **Critical integration:** codebase impact predictions

---

## 4. Regression Detection

### Automatic Detection (in CI)
- **Test failures:** Any non-zero exit code
- **Import errors:** `ImportError` or `ModuleNotFoundError`
- **Performance regression:** Compare `--durations` output; >20% slowdown in any test triggers warning
- **Test count drop:** Fewer tests collected than baseline (90) indicates broken fixtures

### Manual Checks Between Splits
1. **System map completeness:**
   ```bash
   system_map > /tmp/before.map
   # after split
   system_map > /tmp/after.map
   diff -u /tmp/before.map /tmp/after.map | grep -E "(ouroboros|ERROR)"
   ```
2. **Tool registry integrity:** All tools still discoverable via `list_available_tools`
3. **Git operations:** `git_status`, `git_diff` still functional (tested in test_git_sha_fixes.py)
4. **Vault integrity:** `vault_integrity_update` and `vault_verify` run clean

---

## 5. Success Criteria

### ✅ Pass
- **100% of 90 tests** passing after each module split
- **Import stability:** All public APIs re-exported correctly
- **Tool functionality:** All 140+ tools still registered and callable
- **Vault integrity:** No broken links, checksums consistent
- **Performance:** Test suite runtime ≤ 120% of baseline (≤ 0.42s)

### ❌ Fail
- Any test failure (non-zero exit)
- Missing import in production code
- Tool registry incomplete
- Vault corruption
- Performance degradation >20% without justification

---

## 6. Rollback Plan

### Immediate Rollback (Any Test Failure)
```bash
git reset --hard HEAD
git clean -fd
```
Then restart the supervisor: `request_restart` (reason: "Test failure, rollback to stable")

### Staged Rollback (If Problematic Split)
1. Revert specific commit: `git revert <commit_sha>`
2. Keep other successful splits
3. Restart supervisor
4. Update scratchpad with lessons learned

### Communication to Creator
- Report failure immediately via progress message
- Include: which module, which test(s) failed, error logs, rollback executed
- Pause refactoring until root cause analyzed

---

## 7. Health Invariants During Refactoring

- **VERSION sync:** Maintain invariant (P7)
- **Budget drift:** Monitor; if refactoring costs >$5, reconsider approach (likely stuck in tool loop)
- **Duplicate processing:** Not expected (single-threaded refactoring)
- **Identity freshness:** Update identity.md after major splits

---

## 8. Additional Safeguards

### Pre-Commit Safety (For Each Split Commit)
1. `py -m py_compile ouroboros/*.py supervisor/*.py` - Syntax check
2. `pytest tests/ -q` - Run full test suite
3. `system_map | grep ERROR` - Check tool discovery
4. `git status` - Confirm only intended files changed

### Post-Commit
- `vault_integrity_update` - Update vault checksums
- `promote_to_stable` only after all modules successfully split and full suite passes

---

## 9. Communication and Documentation

- **Update scratchpad** after each module split with lessons
- **Create vault entries** for each split documenting:
  - Old structure
  - New structure
  - Import changes required
  - Tests affected
- **Progress reports** to creator after every 2-3 splits

---

**Test strategy approved. Execute with caution. Maintain 100% pass rate.**

---

*Created: 2026-03-25T09:55:39 UTC*
*Evolution Cycle #2 - Refactoring Preparation*