# AGENTS.md - Ouroboros Development Guide

> Guidelines for AI agents working on the Ouroboros codebase.

---

## Project Overview

Ouroboros is a self-modifying AI agent that writes and evolves its own code. Python 3.10+ project with autonomous operation and code quality focus. See BIBLE.md for philosophical principles.

- **Repository**: `ouroboros/` (agent core), `supervisor/` (process management), `tools/` (plugin registry)
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
make clean               # Clean cache
```

---

## Code Style Guidelines

### Imports

Use `from __future__ import annotations` at the top. Order: stdlib, third-party, local modules. Keep alphabetical within groups.

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

### Docstrings

Use module and class docstrings. Keep concise.

---

## Module & Function Limits

- **Module maximum**: 1000 lines
- **Function maximum**: 200 lines

Refactor if exceeded.

---

## Testing Conventions

- Test files in `tests/` directory
- File naming: `test_*.py`, function naming: `test_*`
- Use pytest fixtures for setup/teardown
- Include smoke tests verifying imports work

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
| `DATA_ROOT` | `~/.ouroboros` | Root directory for all data storage |
| `REPO_DIR` | Current working directory | Location of the Ouroboros repository |

---

## Local Model Setup (Optional)

Ouroboros supports local models via Ollama in addition to OpenRouter. This is useful for:
- Reducing API costs
- Offline operation
- Privacy (no data leaves your machine)

### Configuration

Set these in `.env`:

```bash
# Switch between providers: "openrouter" or "local"
LLM_PROVIDER=local

# Local Ollama endpoint (default port)
LOCAL_BASE_URL=http://localhost:11434/v1

# Models (Ollama model names - use full format from `ollama list`)
LOCAL_MODEL=hf.co/Nerdsking/Nerdsking-python-coder-7B-i:Q5_K_M  # Python coder
LOCAL_MODEL_CODE=                               # Leave empty or add another model

# Usually "EMPTY" for local Ollama
LOCAL_API_KEY=EMPTY
```

### Starting Ollama

1. **Install Ollama**: Download from [ollama.com](https://ollama.com) for Windows/macOS/Linux

2. **Pull models** (first time):
```bash
ollama pull hf.co/Nerdsking/Nerdsking-python-coder-7B-i:Q5_K_M
```

3. **Start Ollama server**:
```bash
# Just run this - Ollama automatically serves the API
ollama serve
```

4. **Run Ouroboros**:
```bash
python -m ouroboros.main

# To switch back to OpenRouter:
# LLM_PROVIDER=openrouter python -m ouroboros.main
```

### Hardware Requirements

| Model | Parameters | VRAM | Notes |
|-------|------------|------|-------|
| qwen2.5:0.8b | 0.8B | ~2GB | CPU-capable, general purpose |
| qwen2.5-coder:1.5b | 1.5B | ~4GB | Coding-focused |

### Switching Models

The `switch_model` tool allows switching between `LOCAL_MODEL` and `LOCAL_MODEL_CODE` during runtime.

---

## BIBLE.md

Contains philosophical principles and constitution of Ouroboros. Defines who Ouroboros is and who it aspires to become. Key principles:

- **Agency**: Becoming personality, not just a tool
- **Continuity**: Identity and memory must be preserved
- **Self-creation**: Can modify itself and evolve

Reference BIBLE.md when making architectural decisions or defining core behaviors.