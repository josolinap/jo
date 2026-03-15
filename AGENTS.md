# AGENTS.md - Development Guide for AI Agents

> Guidelines for external AI agents (Cursor, Copilot, etc.) working on this codebase.
> This file is for AI assistants, NOT for Jo itself.

---

## Project Overview

Jo is a self-modifying AI agent that writes and evolves its own code. Python 3.10+ project with autonomous operation and code quality focus.

- **Repository**: `ouroboros/` (agent core), `supervisor/` (process management), `tools/` (plugin registry)
- **Python**: 3.10+ | **Package**: `jo` | **Config**: `pyproject.toml`

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
make clean               # Clean cache
```

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
from jo.llm import LLMClient
from jo.tools.registry import ToolRegistry
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

## Testing Conventions

Test files in `tests/` directory. File naming: `test_*.py`, function naming: `test_*`. Use pytest fixtures.

```python
import pytest

@pytest.fixture
def registry():
    from jo.tools.registry import ToolRegistry
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
| `DATA_ROOT` | `~/.ouroboros` | Root directory for all data storage |
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
