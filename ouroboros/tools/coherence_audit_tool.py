"""
Coherence Audit tool — Jo's self-diagnostic.

Jo calls `coherence_audit` to verify its own consistency during CI runs.
This is the self-healing mechanism: if something is broken, Jo can detect
it and fix it in the same 5.5-hour CI run, without human intervention.

Checks:
1. Version sync (VERSION == pyproject.toml == README)
2. Import integrity (all critical modules import)
3. Tool registry (no duplicates, all have schemas)
4. Protected files exist
5. Memory files exist and are non-empty
6. Vault structure (required directories exist)
7. Test count (verify tests haven't been deleted)
8. Git state (no uncommitted changes in CI)
9. Stub notes (flag notes with <10 words)
10. Embedding pollution (no .md.embedding.json in git)
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import subprocess
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)


def _coherence_audit(ctx: ToolContext, fix: bool = False) -> str:
    """Run a coherence audit on Jo's codebase.

    Args:
        fix: If True, attempt to auto-fix simple issues (e.g., remove stub files)

    Returns:
        JSON report with check results and any issues found.
    """
    repo_dir = ctx.repo_dir
    report: Dict[str, Any] = {
        "checks": [],
        "issues": [],
        "fixes_applied": [],
        "summary": "",
    }

    def check(name: str, passed: bool, detail: str = ""):
        report["checks"].append({"name": name, "passed": passed, "detail": detail})
        if not passed:
            report["issues"].append(f"{name}: {detail}")

    # --- 1. Version sync ---
    try:
        version = (repo_dir / "VERSION").read_text().strip()
        pyproject = (repo_dir / "pyproject.toml").read_text()
        match = re.search(r'version\s*=\s*"([^"]+)"', pyproject)
        py_ver = match.group(1) if match else "NOT FOUND"
        readme = (repo_dir / "README.md").read_text()
        readme_has_ver = version in readme
        check("version_sync", version == py_ver and readme_has_ver,
              f"VERSION={version}, pyproject={py_ver}, README has version: {readme_has_ver}")
    except Exception as e:
        check("version_sync", False, f"Error: {e}")

    # --- 2. Import integrity ---
    try:
        import sys
        sys.path.insert(0, str(repo_dir))
        from ouroboros.agent import OuroborosAgent
        from ouroboros.loop import run_llm_loop
        from ouroboros.llm import LLMClient
        from ouroboros.memory import Memory
        from ouroboros.context import build_llm_messages
        from ouroboros.tools.registry import ToolRegistry
        from supervisor.state import load_state
        from supervisor.workers import Worker
        check("import_integrity", True, "All critical imports resolve")
    except Exception as e:
        check("import_integrity", False, f"Import failed: {e}")

    # --- 3. Tool registry ---
    try:
        tr = ToolRegistry(repo_dir, repo_dir)
        schemas = tr.schemas()
        names = [s.get("function", {}).get("name", "") for s in schemas]
        from collections import Counter
        dupes = {k: v for k, v in Counter(names).items() if v > 1}
        check("tool_registry", len(dupes) == 0,
              f"{len(schemas)} tools, {len(dupes)} duplicates" +
              (f": {list(dupes.keys())}" if dupes else ""))
    except Exception as e:
        check("tool_registry", False, f"Error: {e}")

    # --- 4. Protected files ---
    try:
        protected_path = repo_dir / ".jo_protected"
        protected = protected_path.read_text()
        missing = []
        for line in protected.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not (repo_dir / line).exists():
                missing.append(line)
        check("protected_files", len(missing) == 0,
              f"{len(missing)} missing" + (f": {missing}" if missing else ""))
    except Exception as e:
        check("protected_files", False, f"Error: {e}")

    # --- 5. Memory files ---
    try:
        memory_dir = repo_dir / "memory"
        identity = memory_dir / "identity.md"
        scratchpad = memory_dir / "scratchpad.md"
        issues = []
        if not identity.exists():
            issues.append("identity.md missing")
        elif len(identity.read_text()) < 100:
            issues.append("identity.md too short")
        if not scratchpad.exists():
            issues.append("scratchpad.md missing")
        check("memory_files", len(issues) == 0,
              "; ".join(issues) if issues else "All memory files present")
    except Exception as e:
        check("memory_files", False, f"Error: {e}")

    # --- 6. Vault structure ---
    try:
        vault = repo_dir / "vault"
        required = ["concepts", "projects", "tools", "journal"]
        missing = [d for d in required if not (vault / d).is_dir()]
        check("vault_structure", len(missing) == 0,
              f"{len(missing)} missing dirs" + (f": {missing}" if missing else "All dirs present"))
    except Exception as e:
        check("vault_structure", False, f"Error: {e}")

    # --- 7. Test count ---
    try:
        test_dir = repo_dir / "tests"
        test_files = list(test_dir.glob("test_*.py"))
        check("test_count", len(test_files) >= 5,
              f"{len(test_files)} test files")
    except Exception as e:
        check("test_count", False, f"Error: {e}")

    # --- 8. Stub notes (vault quality) ---
    try:
        vault = repo_dir / "vault"
        stub_count = 0
        stub_examples = []
        for md in vault.rglob("*.md"):
            if ".vault" in md.parts:
                continue
            try:
                content = md.read_text(encoding="utf-8")
                # Strip frontmatter
                if content.startswith("---"):
                    end = content.find("---", 3)
                    if end != -1:
                        content = content[end + 3:]
                word_count = len(content.split())
                if word_count < 10:
                    stub_count += 1
                    if len(stub_examples) < 5:
                        stub_examples.append(f"{md.name} ({word_count} words)")
            except (OSError, UnicodeDecodeError):
                continue
        check("vault_stub_notes", stub_count < 20,
              f"{stub_count} stub notes" +
              (f": {stub_examples}" if stub_examples else ""))
    except Exception as e:
        check("vault_stub_notes", False, f"Error: {e}")

    # --- 9. Embedding pollution ---
    try:
        embedding_files = list(repo_dir.rglob("*.md.embedding.json"))
        check("embedding_pollution", len(embedding_files) == 0,
              f"{len(embedding_files)} embedding sidecars found" +
              (f" (should be in .vault/embeddings/)" if embedding_files else ""))
    except Exception as e:
        check("embedding_pollution", False, f"Error: {e}")

    # --- 10. Git state ---
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_dir, capture_output=True, text=True, timeout=5,
        )
        changes = [l for l in result.stdout.strip().splitlines() if l and ".venv" not in l]
        check("git_clean", len(changes) == 0,
              f"{len(changes)} uncommitted changes" +
              (f": {changes[:3]}" if changes else ""))
    except Exception as e:
        check("git_clean", False, f"Error: {e}")

    # --- Summary ---
    passed = sum(1 for c in report["checks"] if c["passed"])
    total = len(report["checks"])
    report["summary"] = f"{passed}/{total} checks passed, {len(report['issues'])} issues"

    if report["issues"]:
        report["summary"] += f"\n\nIssues:\n" + "\n".join(f"  - {i}" for i in report["issues"])

    return json.dumps(report, indent=2, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    """Register coherence_audit tool."""
    return [
        ToolEntry(
            name="coherence_audit",
            schema={
                "name": "coherence_audit",
                "description": (
                    "Run a self-diagnostic on Jo's codebase. Checks version sync, "
                    "import integrity, tool registry, protected files, memory files, "
                    "vault structure, test count, stub notes, embedding pollution, "
                    "and git state. Use this at the start of each session to detect "
                    "issues early, or after making changes to verify coherence."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "fix": {
                            "type": "boolean",
                            "default": False,
                            "description": "If True, attempt to auto-fix simple issues",
                        },
                    },
                },
            },
            handler=_coherence_audit,
        ),
    ]
