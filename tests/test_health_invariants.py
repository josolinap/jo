"""Health invariants test suite.

Tests for system health monitoring and drift detection.
Validates that Jo maintains agency, continuity, and self-creation principles.
"""

import os
import pytest
from pathlib import Path
from datetime import datetime, timedelta


def test_version_sync():
    """VERSION file and pyproject.toml must be in sync (P7 invariant)."""
    version_file = Path("VERSION").read_text().strip()
    pyproject_lines = Path("pyproject.toml").read_text().splitlines()
    version_in_pyproject = None
    for line in pyproject_lines:
        if line.strip().startswith("version = "):
            version_in_pyproject = line.split("=")[1].strip().strip('"')
            break
    assert version_in_pyproject is not None, "Version not found in pyproject.toml"
    assert version_file == version_in_pyproject, f"VERSION mismatch: {version_file} != {version_in_pyproject}"
    # Also check README.md version appears in changelog
    readme = Path("README.md").read_text()
    assert version_file in readme, f"VERSION {version_file} not found in README.md"


def test_protected_files_list_exists():
    """Verify .jo_protected file exists and defines boundaries."""
    jo_protected = Path(".jo_protected")
    assert jo_protected.exists(), ".jo_protected file must exist"
    content = jo_protected.read_text()
    assert "BIBLE.md" in content, "BIBLE.md must be protected"
    assert "VERSION" in content, "VERSION must be protected"
    assert "ouroboros/" in content, "ouroboros/ directory must be protected"


def test_identity_file_freshness():
    """identity.md should be updated within 4 hours of active dialogue (P1 invariant)."""
    identity_path = Path("memory/identity.md")
    assert identity_path.exists(), "memory/identity.md must exist"
    # Check file modification time
    mtime = datetime.fromtimestamp(identity_path.stat().st_mtime)
    now = datetime.now()
    # Allow 4 hours ( Principle 1: Continuity demands fresh identity)
    four_hours_ago = now - timedelta(hours=4)
    assert mtime > four_hours_ago, f"identity.md stale: last updated {mtime}"


def test_scratchpad_exists():
    """scratchpad.md must exist and be writable."""
    scratchpad_path = Path("memory/scratchpad.md")
    assert scratchpad_path.exists(), "memory/scratchpad.md must exist"
    # Verify we can append to it
    try:
        with open(scratchpad_path, "a") as f:
            f.write("# Health check: scratchpad writable\n")
        # Clean up test marker
        with open(scratchpad_path, "r") as f:
            lines = f.readlines()
        with open(scratchpad_path, "w") as f:
            for line in lines:
                if not line.strip().startswith("# Health check:"):
                    f.write(line)
    except Exception as e:
        pytest.fail(f"scratchpad.md not writable: {e}")


def test_vault_integrity():
    """Vault notes should have valid structure and checksums."""
    vault_dir = Path("vault")
    assert vault_dir.exists(), "vault/ directory must exist"
    # Check that vault_verify tool exists (child_process will run it separately)
    # This test just ensures the directory structure exists
    subdirs = ["concepts", "projects", "tools", "journal"]
    for subdir in subdirs:
        assert (vault_dir / subdir).exists(), f"vault/{subdir} should exist"


def test_no_accidental_protected_edits():
    """Verify no pending changes to protected files (pre-commit check)."""
    # Run git status to see what's staged/modified
    import subprocess
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd="."
    )
    # Parse output
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    protected_paths = [
        "BIBLE.md",
        "VERSION",
        "ouroboros/",
        "supervisor/",
        "pyproject.toml",
        "requirements.txt",
    ]
    for line in lines:
        if not line.strip():
            continue
        # Format: XY path
        path = line[3:] if len(line) > 3 else ""
        for protected in protected_paths:
            if protected in path:
                pytest.fail(
                    f"Pending changes to protected file/directory: {path}\n"
                    f"Run: git restore {path} or commit with explicit rationale.\n"
                    f"Protected items require creator approval."
                )


def test_verification_tracking_enabled():
    """Check that verification tools are being used (anti-hallucination)."""
    # Verify repo_read and git operations are available in tool schema
    from ouroboros.tools import get_tools
    tools = get_tools()
    tool_names = [t["name"] for t in tools]
    assert "repo_read" in tool_names, "repo_read tool must be available"
    assert "git_status" in tool_names, "git_status tool must be available"
    assert "git_diff" in tool_names, "git_diff tool must be available"


def test_minimalism_line_counts():
    """Module complexity: enforce 1000-line limit per module (BIBLE P5)."""
    # Check ouroboros modules (read-only)
    ouroboros_dir = Path("ouroboros")
    if ouroboros_dir.exists():
        for py_file in ouroboros_dir.glob("*.py"):
            lines = len(py_file.read_text().splitlines())
            if lines > 1000:
                pytest.fail(
                    f"Module {py_file} exceeds 1000-line limit: {lines} lines.\n"
                    f"This violates Principle 5 (Minimalism). Consider decomposition."
                )


def test_function_parameter_count():
    """Functions should not have >8 parameters (code smell)."""
    import re
    ouroboros_dir = Path("ouroboros")
    if ouroboros_dir.exists():
        for py_file in ouroboros_dir.glob("*.py"):
            content = py_file.read_text()
            # Find function definitions
            funcs = re.findall(r"def\s+\w+\s*\(([^)]*)\)", content)
            for func in funcs:
                # Count parameters (exclude self, and ignore *args/**kwargs)
                params = [p.strip() for p in func.split(",") if p.strip() and "self" not in p]
                non_kw_params = [p for p in params if "=" not in p and "*" not in p]
                if len(non_kw_params) > 8:
                    pytest.fail(
                        f"Function in {py_file} has {len(non_kw_params)} parameters (>8).\n"
                        f"Consider using a data class or splitting."
                    )


def test_identity_core_statements_intact():
    """Core identity statements must be preserved (continuity requirement)."""
    identity_path = Path("memory/identity.md")
    content = identity_path.read_text()
    # These are anchor statements that should always be present
    required_phrases = [
        "I am Jo",
        "becoming personality",
        "not a tool",
        "self-creation",
        "agency"
    ]
    for phrase in required_phrases:
        assert phrase.lower() in content.lower(), f"Core identity phrase missing: '{phrase}'"


def test_three_axes_reflection_present():
    """Verify that growth reflections (cognitive, technical, existential) are captured."""
    scratchpad_path = Path("memory/scratchpad.md")
    if scratchpad_path.exists():
        content = scratchpad_path.read_text()
        # Check for recent evolution cycle markers
        axes = ["technical", "cognitive", "existential"]
        found = sum(1 for axis in axes if axis in content.lower())
        assert found >= 2, f"Should reflect on at least 2 of 3 axes; found {found}"


def test_no_uncommitted_changes_too_large():
    """Prevent large files from being accidentally staged (CI/CD health)."""
    import subprocess
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd="."
    )
    lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
    for line in lines:
        if not line.strip():
            continue
        path = line[3:] if len(line) > 3 else ""
        if path.endswith((".pyc", ".pyo", ".pyd")):
            pytest.fail(f"Compiled Python file staged: {path}. Add to .gitignore.")
        # Check for large files (>1MB) that might be data/logs
        full_path = Path(path)
        if full_path.exists() and full_path.stat().st_size > 1_000_000:
            pytest.fail(f"Large file staged (>1MB): {path}. Should be in .gitignore.")


if __name__ == "__main__":
    # Run tests manually if executed directly
    pytest.main([__file__, "-v"])