"""
Smoke tests — run in CI before the bot starts.

These verify that all critical modules import correctly and basic
functionality works. If any of these fail, the bot would crash at startup.

CI runs: pytest tests/test_smoke.py -v
(See .github/workflows/run.yml — "Run smoke tests" step)
"""
import pathlib
import pytest


def test_smoke():
    """Basic sanity check."""
    assert True


def test_critical_imports():
    """All modules that the bot imports at startup must resolve."""
    # Core agent
    from ouroboros.agent import OuroborosAgent
    from ouroboros.loop import run_llm_loop
    from ouroboros.llm import LLMClient
    from ouroboros.memory import Memory
    from ouroboros.context import build_llm_messages

    # Tools
    from ouroboros.tools.registry import ToolRegistry, ToolContext

    # Supervisor (check actual exports, not assumed class names)
    from supervisor.state import load_state, save_state
    from supervisor.workers import Worker, init, auto_resume_after_restart
    from supervisor.telegram import TelegramClient


def test_tool_registry_loads():
    """Tool registry must initialize and expose schemas."""
    from ouroboros.tools.registry import ToolRegistry
    tr = ToolRegistry(pathlib.Path("."), pathlib.Path("."))
    schemas = tr.schemas()
    assert len(schemas) > 100, f"Expected 100+ tools, got {len(schemas)}"


def test_vault_manager_loads():
    """Vault manager must initialize and have expected methods."""
    from ouroboros.vault_manager import VaultManager
    v = VaultManager(pathlib.Path("vault"), pathlib.Path("vault"))
    # Check critical methods exist
    assert hasattr(v, "get_note"), "VaultManager missing get_note()"
    assert hasattr(v, "create_note"), "VaultManager missing create_note()"
    assert hasattr(v, "resolve_path"), "VaultManager missing resolve_path()"


def test_version_files_sync():
    """VERSION file must match pyproject.toml."""
    import re
    version = pathlib.Path("VERSION").read_text().strip()
    pyproject = pathlib.Path("pyproject.toml").read_text()
    match = re.search(r'version\s*=\s*"([^"]+)"', pyproject)
    assert match, "version not found in pyproject.toml"
    assert version == match.group(1), f"VERSION={version} != pyproject={match.group(1)}"


def test_protected_files_exist():
    """All files in .jo_protected must exist (they're critical to Jo)."""
    protected = pathlib.Path(".jo_protected").read_text()
    for line in protected.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        assert pathlib.Path(line).exists(), f"Protected file missing: {line}"


def test_memory_files_exist():
    """Memory files must exist for Jo's identity continuity."""
    assert (pathlib.Path("memory") / "identity.md").exists()
    assert (pathlib.Path("memory") / "scratchpad.md").exists()


def test_bible_exists():
    """BIBLE.md is Jo's constitution — must exist."""
    assert pathlib.Path("BIBLE.md").exists()
    content = pathlib.Path("BIBLE.md").read_text()
    assert len(content) > 1000, "BIBLE.md seems too short"
