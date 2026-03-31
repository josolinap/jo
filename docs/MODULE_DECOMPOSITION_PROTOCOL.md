# Module Decomposition Protocol

> A systematic approach to preventing and resolving oversized modules in the Ouroboros codebase.

---

## Problem Statement

Oversized modules (>1000 lines) create:
- **Cognitive overload** — hard to understand, navigate, and modify
- **Merge conflicts** — multiple agents editing the same file
- **Testing difficulty** — tightly coupled code resists unit testing
- **Blast radius** — changes in one area risk breaking unrelated functionality

**Current violations (2026-03-31):**

| Module | Lines | Severity |
|--------|-------|----------|
| `ouroboros/loop.py` | 1240 | CRITICAL |
| `ouroboros/codebase_graph.py` | 1161 | CRITICAL |
| `ouroboros/agent.py` | 1032 | CRITICAL |
| `ouroboros/tools/neural_map.py` | 1018 | CRITICAL |

---

## Core Principles

### 1. Impact-First Refactoring

Before touching any oversized file, analyze what depends on it:

```python
# Use codebase_impact to see blast radius
from ouroboros.codebase_graph import get_graph

graph = get_graph()
dependents = graph.get_dependents("file:ouroboros/agent.py")
# Returns: ["file:supervisor/workers.py", "file:ouroboros/tools/control.py", ...]
```

**Rule:** Never decompose a module without first mapping its dependents.

### 2. Extract by Cohesion, Not Size

Don't split files randomly. Look for natural boundaries:

| Cohesion Type | Example | Target Module |
|---------------|---------|---------------|
| **Lifecycle** | init, shutdown, restart | `agent_lifecycle.py` |
| **Message handling** | inject, emit, progress | `agent_messaging.py` |
| **State persistence** | load, save, archive | `agent_state.py` |
| **Health monitoring** | checks, verification | `agent_health.py` |
| **Tool orchestration** | routing, execution | `tool_executor.py` |
| **Dialogue flow** | context building | `context.py` |

### 3. Interface Preservation

The external API stays **exactly the same**. Move code to new modules but keep the same imports/function signatures.

```python
# BEFORE: agent.py contains everything
class OuroborosAgent:
    def _check_uncommitted_changes(self): ...
    def _check_version_sync(self): ...
    def _check_budget(self): ...
    def _verify_system_state(self): ...
    def _emit_progress(self): ...
    def _emit_typing_start(self): ...

# AFTER: agent.py becomes thin orchestrator
from ouroboros.agent_health import SystemVerifier
from ouroboros.agent_messaging import MessageEmitter

class OuroborosAgent:
    def __init__(self, env):
        self._health = SystemVerifier(env)
        self._messenger = MessageEmitter(self._event_queue)
    
    # Delegation, not implementation
    def _verify_system_state(self, git_sha):
        return self._health.verify(git_sha)
```

### 4. Gradual Migration

Move one cohesive chunk at a time:
1. Extract chunk → new module
2. Update imports in original module
3. Commit, verify tests pass
4. Move next chunk
5. Repeat until target reached

**Never do massive rewrites.** Each step should be independently deployable.

### 5. Guardrails

Automated detection flags violations:
- Pre-commit hook checks line counts
- Health system reports violations in invariants
- Evolution cycles must include simplification every 2-3 cycles

---

## Decomposition Workflow

### Step 1: Analyze the Module

```bash
# Count lines
wc -l ouroboros/agent.py

# Find function boundaries
grep -n "def \|class " ouroboros/agent.py

# Find imports used
grep -n "^from \|^import " ouroboros/agent.py

# Find what imports this module
grep -r "from ouroboros.agent import\|from ouroboros import agent" --include="*.py"
```

### Step 2: Identify Cohesive Clusters

Group functions by responsibility:

```
agent.py (1190 lines)
├── Lifecycle (lines 79-141)
│   ├── __init__
│   ├── _start_hot_reload_manager
│   └── _log_worker_boot_once
├── Health Checks (lines 167-421)
│   ├── _verify_restart
│   ├── _check_uncommitted_changes
│   ├── _check_version_sync
│   ├── _check_budget
│   └── _verify_system_state
├── Task Execution (lines 427-749)
│   ├── _prepare_task_context
│   ├── handle_task
│   └── _auto_update_scratchpad_after_task
├── Event Emission (lines 774-1180)
│   ├── _emit_task_results
│   ├── _emit_progress
│   ├── _emit_typing_start
│   └── _emit_task_heartbeat
└── Evolution History (lines 997-1070)
    ├── _update_evolution_history
    └── _try_archive_stable_evolution
```

### Step 3: Create Target Modules

```python
# ouroboros/agent_health.py
"""System health verification for agent startup."""
from __future__ import annotations
import json
import os
import re
import subprocess
from typing import Any, Dict, Tuple
import pathlib
import logging

log = logging.getLogger(__name__)

class SystemVerifier:
    """Handles all startup health checks."""
    
    def __init__(self, env):
        self.env = env
    
    def verify(self, git_sha: str) -> None:
        """Run all startup checks."""
        checks = {}
        issues = 0
        
        checks["uncommitted_changes"], n = self._check_uncommitted_changes()
        issues += n
        checks["version_sync"], n = self._check_version_sync()
        issues += n
        checks["budget"], n = self._check_budget()
        issues += n
        
        # ... rest of verification logic
    
    def _check_uncommitted_changes(self) -> Tuple[dict, int]:
        # ... moved from agent.py
        pass
    
    def _check_version_sync(self) -> Tuple[dict, int]:
        # ... moved from agent.py
        pass
    
    def _check_budget(self) -> Tuple[dict, int]:
        # ... moved from agent.py
        pass
```

### Step 4: Update Original Module

```python
# ouroboros/agent.py (after decomposition)
from ouroboros.agent_health import SystemVerifier
from ouroboros.agent_messaging import MessageEmitter
from ouroboros.agent_state import EvolutionHistory

class OuroborosAgent:
    def __init__(self, env: Env, event_queue: Any = None):
        self.env = env
        # ... existing init ...
        
        # Delegated subsystems
        self._health = SystemVerifier(env)
        self._messenger = MessageEmitter(event_queue)
        self._evolution = EvolutionHistory(env)
    
    def _verify_system_state(self, git_sha: str) -> None:
        """Delegate to health subsystem."""
        self._health.verify(git_sha)
    
    def _emit_progress(self, text: str) -> None:
        """Delegate to messaging subsystem."""
        self._messenger.emit_progress(text, self._current_chat_id)
```

### Step 5: Verify and Commit

```bash
# Run tests
python -m pytest tests/ -q

# Check imports
python -c "from ouroboros.agent import OuroborosAgent"

# Verify line count
wc -l ouroboros/agent.py ouroboros/agent_health.py ouroboros/agent_messaging.py

# Commit
git add ouroboros/agent.py ouroboros/agent_health.py ouroboros/agent_messaging.py
git commit -m "refactor(agent): extract health checks and messaging to submodules"
```

---

## Agent.py Decomposition Plan

### Target Structure

```
ouroboros/
├── agent.py              (~400 lines) Thin orchestrator
├── agent_health.py       (~250 lines) System verification
├── agent_messaging.py    (~200 lines) Event emission
├── agent_state.py        (~150 lines) Evolution history
└── agent_context.py      (~190 lines) Task context preparation
```

### Migration Order

1. **agent_health.py** — Extract `_verify_restart`, `_check_*`, `_verify_system_state`
2. **agent_messaging.py** — Extract `_emit_*` methods
3. **agent_state.py** — Extract `_update_evolution_history`, `_try_archive_stable_evolution`
4. **agent_context.py** — Extract `_prepare_task_context`, `_build_review_context`

Each step: extract → update imports → commit → verify → next step.

---

## Automated Prevention

### Pre-commit Hook

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: module-size-check
        name: Check module size
        entry: python scripts/check_module_size.py
        language: python
        files: '\.py$'
```

### Health Invariants Integration

Add to `ouroboros/health_invariants.py`:

```python
# Module size check
try:
    import os
    violations = []
    for root, dirs, files in os.walk(str(env.repo_dir / "ouroboros")):
        for f in files:
            if f.endswith(".py"):
                path = os.path.join(root, f)
                lines = sum(1 for _ in open(path, encoding="utf-8"))
                if lines > 1000:
                    violations.append(f"{os.path.relpath(path, env.repo_dir)}: {lines} lines")
    if violations:
        checks.append(f"CRITICAL: MODULE SIZE: {len(violations)} modules exceed 1000 lines: {', '.join(violations)}")
    else:
        checks.append("OK: all modules under 1000 lines")
except Exception:
    log.debug("Health check failed: module size", exc_info=True)
```

### Evolution Cycle Discipline

Track "net complexity growth" in health report:
- Every 2-3 evolution cycles must include a simplification
- If net lines added > 500 without extraction → block evolution
- Reward decompositions: track modules reduced per cycle

---

## Workspace Management

### Current Structure Issues

```
ouroboros/
├── agent.py (1190 lines) ← VIOLATION
├── loop.py (1240 lines) ← VIOLATION  
├── codebase_graph.py (1161 lines) ← VIOLATION
├── tools/
│   ├── neural_map.py (1018 lines) ← VIOLATION
│   └── ... (42 more files, flat structure)
└── ... (50+ more files, flat structure)
```

**Problems:**
- Flat structure → hard to find related files
- Mixed concerns → agent logic, tools, utilities all together
- No clear layering → everything imports everything

### Recommended Structure

```
ouroboros/
├── __init__.py
├── core/                    # Core agent functionality
│   ├── __init__.py
│   ├── agent.py            # Thin orchestrator
│   ├── agent_health.py     # Health checks
│   ├── agent_messaging.py  # Event emission
│   ├── agent_state.py      # State management
│   ├── agent_context.py    # Context building
│   ├── loop.py             # LLM loop coordinator
│   └── loop/               # Loop submodules
│       ├── __init__.py
│       ├── budget.py
│       ├── context.py
│       └── execution.py
├── intelligence/            # AI/ML capabilities
│   ├── __init__.py
│   ├── codebase_graph.py   # Knowledge graph
│   ├── consciousness.py    # Self-awareness
│   ├── episodic_memory.py  # Experience tracking
│   ├── hybrid_memory.py    # Memory systems
│   ├── temporal_learning.py
│   └── knowledge_decay.py
├── tools/                   # Tool registry and implementations
│   ├── __init__.py
│   ├── registry.py         # Tool registration
│   ├── core.py             # Core tools
│   ├── browser.py          # Web automation
│   ├── git.py              # Git operations
│   ├── shell.py            # Shell execution
│   ├── web_research.py     # Research tools
│   └── neural/             # Neural/ML tools
│       ├── __init__.py
│       ├── neural_map.py
│       └── evolution_loop.py
├── health/                  # Health monitoring
│   ├── __init__.py
│   ├── invariants.py       # Health checks
│   ├── drift_detector.py   # Drift detection
│   ├── auto_fix.py         # Auto-remediation
│   └── predictor.py        # Predictive health
├── vault/                   # Vault/knowledge management
│   ├── __init__.py
│   ├── vault.py
│   ├── vault_engine.py
│   ├── vault_manager.py
│   ├── vault_models.py
│   ├── vault_parser.py
│   └── vault_search.py
├── evolution/               # Evolution/improvement
│   ├── __init__.py
│   ├── evolution_fingerprint.py
│   ├── evolution_proposal.py
│   ├── evolution_strategy.py
│   ├── delta_eval.py
│   ├── proof_gate.py
│   └── checkpoint.py
├── llm/                     # LLM integration
│   ├── __init__.py
│   ├── llm.py
│   ├── dspy_integration.py
│   └── response_analyzer.py
├── context/                 # Context management
│   ├── __init__.py
│   ├── context.py
│   ├── context_cache.py
│   ├── context_enricher.py
│   └── extraction.py
├── memory/                  # Memory systems
│   ├── __init__.py
│   ├── memory.py
│   ├── memory_consolidator.py
│   ├── experience_indexer.py
│   └── knowledge_discovery.py
├── pipeline/                # Pipeline orchestration
│   ├── __init__.py
│   ├── pipeline.py
│   ├── synthesis.py
│   └── eval.py
├── utils/                   # Shared utilities
│   ├── __init__.py
│   ├── utils.py
│   ├── normalizer.py
│   └── config_manager.py
└── legacy/                  # Deprecated/migration
    └── ...
```

### Migration Strategy

**Phase 1: Core Extraction (Week 1)**
1. Create `ouroboros/core/` directory
2. Move `agent.py` → `core/agent.py`
3. Extract health/messaging/state to `core/`
4. Update all imports

**Phase 2: Intelligence Layer (Week 2)**
1. Create `ouroboros/intelligence/`
2. Move cognitive modules
3. Update imports

**Phase 3: Tools Restructuring (Week 3)**
1. Create `ouroboros/tools/neural/`
2. Move neural/ML tools
3. Flatten tool registration

**Phase 4: Health & Vault (Week 4)**
1. Create `ouroboros/health/`
2. Create `ouroboros/vault/`
3. Move related modules

**Phase 5: Evolution & LLM (Week 5)**
1. Create `ouroboros/evolution/`
2. Create `ouroboros/llm/`
3. Move related modules

### Import Compatibility

Maintain backward compatibility during migration:

```python
# ouroboros/agent.py (transition period)
"""Backward compatibility shim."""
from ouroboros.core.agent import OuroborosAgent, Env, make_agent
from ouroboros.core.agent_health import SystemVerifier
from ouroboros.core.agent_messaging import MessageEmitter

__all__ = ["OuroborosAgent", "Env", "make_agent", "SystemVerifier", "MessageEmitter"]
```

---

## Complexity Metrics

### Line Count Limits

| Module Type | Soft Limit | Hard Limit |
|-------------|------------|------------|
| Core modules | 500 lines | 800 lines |
| Tool modules | 400 lines | 600 lines |
| Utility modules | 300 lines | 500 lines |
| Test modules | No limit | No limit |

### Cyclomatic Complexity

Use `radon` for complexity analysis:

```bash
# Install
pip install radon

# Check complexity
radon cc ouroboros/ -a -nc

# Check maintainability
radon mi ouroboros/ -nc
```

**Thresholds:**
- A (1-5): Simple, low risk
- B (6-10): Moderate complexity
- C (11-20): Complex, consider refactoring
- D (21-30): Very complex, should refactor
- E (31-40): Alarming, must refactor
- F (41+): Unmaintainable, immediate action

### Pre-commit Integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/PyCQA/flake8
    rev: 7.0.0
    hooks:
      - id: flake8
        args: [--max-complexity=15, --max-line-length=120]
  
  - repo: local
    hooks:
      - id: module-size
        name: Module size check
        entry: python -c "
          import sys, os
          for f in sys.argv[1:]:
              if f.endswith('.py'):
                  lines = sum(1 for _ in open(f, encoding='utf-8'))
                  if lines > 1000:
                      print(f'ERROR: {f} has {lines} lines (max 1000)')
                      sys.exit(1)
          "
        language: python
        files: '\.py$'
```

---

## Anti-Patterns

### ❌ Don't: Random Splitting

```python
# BAD: Splitting by line count alone
# agent_part1.py (lines 1-500)
# agent_part2.py (lines 501-1000)
```

### ✅ Do: Cohesion-Based Extraction

```python
# GOOD: Splitting by responsibility
# agent_health.py (all health-related code)
# agent_messaging.py (all event emission code)
```

### ❌ Don't: Break Interfaces

```python
# BAD: Changing public API
# Before: agent.verify_system_state()
# After: health.verifier.verify()  # Breaks callers
```

### ✅ Do: Preserve Interfaces

```python
# GOOD: Delegation pattern
class OuroborosAgent:
    def verify_system_state(self, git_sha):
        return self._health.verify(git_sha)  # Same interface
```

### ❌ Don't: Massive Rewrites

```python
# BAD: Rewrite everything at once
# Delete agent.py, create 10 new files, update 50 imports
```

### ✅ Do: Incremental Migration

```python
# GOOD: One chunk at a time
# 1. Extract health → commit → verify
# 2. Extract messaging → commit → verify
# 3. Extract state → commit → verify
```

---

## Verification Checklist

Before committing a decomposition:

- [ ] All tests pass: `python -m pytest tests/ -q`
- [ ] Imports work: `python -c "from ouroboros.agent import OuroborosAgent"`
- [ ] Line counts reduced: `wc -l ouroboros/agent.py`
- [ ] No circular imports: `python -m py_compile ouroboros/*.py`
- [ ] Backward compatibility: existing callers still work
- [ ] Health invariants updated: new module sizes reported
- [ ] Documentation updated: AGENTS.md, docstrings

---

## References

- **Principle 5: Minimalism** — Constitution requires modules under 1000 lines
- **AGENTS.md** — Development guidelines for this codebase
- **BIBLE.md** — Philosophical principles (Agency, Continuity, Self-creation)
- **Claude Code Multi-File Refactoring** — Agentic refactoring patterns
- **Python Project Structure** — Best practices for large projects
- **Radon** — Complexity metrics tool
- **Pre-commit** — Automated quality gates
