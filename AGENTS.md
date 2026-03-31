# AGENTS.md - Development Guide for AI Agents

> Guidelines for external AI agents (Cursor, Copilot, etc.) working on this codebase.
> This file is for AI assistants, NOT for Jo itself.

---

## Project Overview

Jo is a self-modifying AI agent that writes and evolves its own code. Python 3.10+ project with autonomous operation and code quality focus.

- **Repository**: `ouroboros/` (agent core), `supervisor/` (process management), `ouroboros/tools/` (plugin registry)
- **Python**: 3.10+ | **Package**: `ouroboros` | **Config**: `pyproject.toml`

---

## Development Commands

```bash
make test                # Run all tests (quiet mode)
make test-v              # Run tests with verbose output
python3 -m pytest tests/test_smoke.py -v           # Run a specific test file
python3 -m pytest tests/test_smoke.py::test_import -v  # Run a single test
python3 -m pytest tests/ -k "test_tool" -v         # Run tests matching a pattern
ruff check .             # Lint with ruff
ruff check --fix .       # Auto-fix linting issues
ruff format .            # Format code
make health              # Code health check
make verify              # Verify code compiles + tests pass (run before commit)
make clean               # Clean cache
python scripts/check_module_health.py              # Check module sizes & complexity
python scripts/check_module_health.py --report     # Generate detailed health report
```

---

## Anti-Hallucination Guidelines

Before making claims or taking actions, always verify:

1. **Verify code exists** — Use `repo_read` to read files before claiming what's in them
2. **Verify code works** — Run the code or tests to confirm behavior
3. **Verify changes** — Use `git status` and `git diff` to see actual changes
4. **Verify syntax** — Run `make verify` before committing

**Never assert without verification.** If unsure, say "I think X but will verify" instead of claiming as fact.

---

## Verification Tracking

**IMPORTANT: Verification is AUTOMATICALLY tracked.**

Every time you:
- Use `repo_read` → logged
- Use `git_status` or `git_diff` → logged
- Run tests or linting → logged

The health report shows your verification patterns. Low verification = warning.

---

## Code Review Protocol

When reviewing code or assessing alignment with principles:

1. **Search before assessing** — Never assess implementation status without searching:
   ```
   grep "relevant_keyword" ouroboros/*.py
   ls ouroboros/
   git log --oneline -10
   ```

2. **Read before claiming** — Never assert what code does without reading it:
   - Use repo_read to check actual implementation
   - Check file sizes with `wc -l`
   - Verify function names with grep

3. **Distinguish fact from opinion**:
   - Fact: "consciousness.py exists and has 538 lines"
   - Opinion: "The architecture seems synchronous"
   
4. **When assessing BIBLE.md alignment:**
   - Read the principle
   - Search for relevant implementation
   - Compare what exists vs what principle requires
   - Report verified findings only

**Wrong:** "Background consciousness doesn't exist, creating a gap"
**Right:** "Let me search for consciousness... Found consciousness.py with 538 lines"

---

## Code Style Guidelines

### Imports

Use `from __future__ import annotations` at the top. Order: stdlib, third-party, local modules (alphabetical within groups).

```python
from __future__ import annotations
import json
import logging
import pathlib
from typing import Any, Dict, List, Optional, Tuple
import requests
from ouroboros.llm import LLMClient
from ouroboros.tools.registry import ToolRegistry
```

### Line Length

Maximum: **120 characters** (ruff formatter handles enforcement).

### Types

Use `typing` module. Use `frozen=True` for immutable dataclasses.

```python
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

@dataclass(frozen=True)
class Env:
    repo_dir: pathlib.Path
    drive_root: pathlib.Path
    branch_dev: str = "dev"
```

### Naming

- **Functions/variables**: snake_case
- **Classes**: PascalCase
- **Constants**: UPPER_SNAKE_CASE
- **Private functions**: prefix with `_`

### Logging

```python
import logging
log = logging.getLogger(__name__)
```

### Error Handling

- **NEVER use bare `except: pass`**
- Catch specific exception types
- Use ⚠️ emoji prefix for user-friendly errors

```python
try:
    result = risky_operation()
except ValueError as e:
    log.warning("Invalid value: %s", e)
    return f"⚠️ Invalid value: {e}"
```

### Module & Function Limits

- **Module maximum**: 1000 lines
- **Function maximum**: 200 lines

Refactor if exceeded.

---

## Module Decomposition Protocol

**Oversized modules (>1000 lines) are the #1 code health risk.** Follow this protocol:

### Before Touching Any Oversized Module

1. **Check impact** — Use `codebase_impact("symbol_name")` to see what depends on it
2. **Read the module** — Understand current structure before proposing changes
3. **Run health check** — `python scripts/check_module_health.py`

### Extraction Rules

1. **Extract by cohesion, not size** — Group related functions together:
   - Lifecycle methods (init, shutdown, restart)
   - Message handling vs internal state management
   - Tool orchestration vs dialogue flow
   - Health monitoring vs business logic

2. **Preserve interfaces** — External API stays exactly the same:
   ```python
   # GOOD: Delegation pattern
   class OuroborosAgent:
       def _verify_system_state(self, git_sha):
           return self._health.verify(git_sha)  # Same interface
   ```

3. **Gradual migration** — One chunk at a time:
   - Extract chunk → new module
   - Update imports in original module
   - Commit, verify tests pass
   - Move next chunk

4. **Check for circular imports** — The health checker detects these automatically

### Current Violations (as of 2026-03-31)

| Module | Lines | Priority |
|--------|-------|----------|
| `ouroboros/loop.py` | 1450 | CRITICAL |
| `ouroboros/codebase_graph.py` | 1354 | CRITICAL |
| `ouroboros/tools/neural_map.py` | 1209 | CRITICAL |
| `ouroboros/context.py` | 1202 | CRITICAL |
| `ouroboros/agent.py` | 1190 | CRITICAL |
| `ouroboros/tools/evolution_loop.py` | 1028 | CRITICAL |

See `docs/MODULE_DECOMPOSITION_PROTOCOL.md` for full decomposition plan.

---

## Testing Conventions

Test files in `tests/` directory. File naming: `test_*.py`, function naming: `test_*`. Use pytest fixtures.

```python
import pytest

@pytest.fixture
def registry():
    from ouroboros.tools.registry import ToolRegistry
    tmp = pathlib.Path(tempfile.mkdtemp())
    return ToolRegistry(repo_dir=tmp, drive_root=tmp)

def test_tool_registered(registry):
    available = [t["function"]["name"] for t in registry.schemas()]
    assert "repo_read" in available
```

---

## Tool Discovery

Tools auto-discovered from `ouroboros/tools/`. Each tool module should:
1. Define functions prefixed with `_` (e.g., `_repo_read`)
2. Accept `ToolContext` as first parameter
3. Return string results (for LLM consumption)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATA_ROOT` | `~/.jo_data` | Root directory for all data storage |
| `REPO_DIR` | Current working directory | Location of the Ouroboros repository |

---

## BIBLE.md

Reference BIBLE.md for philosophical principles: Agency, Continuity, and Self-creation.

---

## Git Rules for Parallel Agents

Multiple agents may work on different files simultaneously. Follow these rules:

### Committing

- **ONLY commit files YOU changed in THIS session**
- ALWAYS include `fixes #<number>` or `closes #<number>` when there is a related issue
- NEVER use `git add -A` or `git add .` - these sweep up changes from other agents
- ALWAYS use `git add <specific-file-paths>` listing only files you modified
- Before committing, run `git status` and verify you are only staging YOUR files

### Forbidden Git Operations

These commands can destroy other agents' work:
- `git reset --hard` - destroys uncommitted changes
- `git checkout .` - destroys uncommitted changes
- `git clean -fd` - deletes untracked files
- `git stash` - stashes ALL changes including other agents' work
- `git add -A` / `git add .` - stages other agents' uncommitted work

### Safe Workflow

```bash
# 1. Check status first
git status

# 2. Add ONLY your specific files
git add ouroboros/tools/specific.py
git add AGENTS.md

# 3. Commit
git commit -m "fix(tools): description"

# 4. Push (pull --rebase if needed, but NEVER reset/checkout)
git pull --rebase && git push
```

### If Rebase Conflicts Occur

- Resolve conflicts in YOUR files only
- If conflict is in a file you didn't modify, abort and ask

---

## Push Safety Guardrails

**CRITICAL: Never push code that could break the workflow.**

### Before Every Push

1. **Run syntax validation:**
   ```bash
   python -m py_compile ouroboros/*.py ouroboros/tools/*.py supervisor/*.py
   ```

2. **Run critical import checks:**
   ```bash
   python -c "from ouroboros.tools.registry import ToolRegistry"
   python -c "from ouroboros.vault_manager import VaultManager"
   python -c "from supervisor.state import init"
   ```

3. **Run smoke tests:**
   ```bash
   python -m pytest tests/test_smoke.py -v
   ```

4. **Or run full verification:**
   ```bash
   make verify
   ```

### Common Failure Modes

- **Truncated files**: Git operations can produce incomplete files. Always verify file size after git operations.
- **Missing imports**: New code must import `List`, `Dict`, `Any` from `typing`.
- **Syntax errors**: Use `py -m py_compile` on every `.py` file you modify.

### If Code Looks Suspicious

If a file has unusually few lines (< 50 lines for a module that should be larger), DO NOT commit:
1. Check `git show HEAD:<file>` for the previous version
2. Compare line counts: `wc -l <file>`
3. Restore if truncated: `git checkout HEAD -- <file>`

---

## Jo-Specific Git Rules

### Mandatory Pre-Commit Checks

- Run `git rev-parse HEAD` → record current SHA in scratchpad before commit
- After `git add`, always run `git status --porcelain` and verify only your files appear
- If you see files you didn't modify → STOP, investigate, don't commit

### Concurrency Awareness

- Check `~/.jo_data/state/state.json` for active workers before starting intensive tasks
- If >3 workers already active → consider whether your task can wait or needs `schedule_task`
- Record worker count in scratchpad when launching subtasks

### Identity & Memory Lock Discipline

- `memory/identity.md` and `memory/scratchpad.md` use file locking
- Always use the `update_identity` and `update_scratchpad` tools - never edit directly
- If lock acquisition fails → wait 1s and retry up to 3 times, then abort with error

### Evolution Cycle Discipline

- Every evolution cycle must: code change → version bump → commit → push → restart
- If commit fails → rollback to stable, analyze, retry with clean state
- NEVER push to `main` - only `dev` branch
