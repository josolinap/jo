"""
Ouroboros — Headless Query.

Instant state inspection without spawning an LLM session.
Inspired by GSD-2's headless query pattern (gsd headless query).

Returns JSON state in milliseconds — no LLM overhead.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class SystemState:
    version: str = ""
    git_sha: str = ""
    branch: str = ""
    module_count: int = 0
    total_lines: int = 0
    max_module_lines: int = 0
    tools_registered: int = 0
    vault_notes: int = 0
    evolution_mode: bool = False
    background_consciousness: bool = False
    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


@dataclass
class HealthState:
    all_passing: bool = True
    violations: List[str] = field(default_factory=list)
    drift_percentage: float = 0.0
    oversized_modules: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


@dataclass
class QueryResult:
    system: SystemState
    health: HealthState
    tools_available: List[str] = field(default_factory=list)
    recent_commits: List[str] = field(default_factory=list)
    query_time_ms: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "system": self.system.to_dict(),
            "health": self.health.to_dict(),
            "tools_count": len(self.tools_available),
            "recent_commits": self.recent_commits,
            "query_time_ms": self.query_time_ms,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2)


class HeadlessQuery:
    """Instant system state inspection without LLM overhead."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir

    def query(self) -> QueryResult:
        start = time.time()

        system = self._get_system_state()
        health = self._get_health_state()
        tools = self._get_tools()
        commits = self._get_recent_commits()

        elapsed_ms = int((time.time() - start) * 1000)

        return QueryResult(
            system=system,
            health=health,
            tools_available=tools,
            recent_commits=commits,
            query_time_ms=elapsed_ms,
        )

    def _get_system_state(self) -> SystemState:
        import subprocess

        version = ""
        version_path = self.repo_dir / "VERSION"
        if version_path.exists():
            version = version_path.read_text(encoding="utf-8").strip()

        git_sha = ""
        branch = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=self.repo_dir
            )
            if result.returncode == 0:
                git_sha = result.stdout.strip()
            result = subprocess.run(
                ["git", "branch", "--show-current"], capture_output=True, text=True, cwd=self.repo_dir
            )
            if result.returncode == 0:
                branch = result.stdout.strip()
        except Exception:
            pass

        module_count = 0
        total_lines = 0
        max_lines = 0
        for py_file in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                module_count += 1
                total_lines += lines
                max_lines = max(max_lines, lines)
            except Exception:
                pass

        vault_notes = 0
        vault_dir = self.repo_dir / "vault"
        if vault_dir.exists():
            vault_notes = len(list(vault_dir.rglob("*.md")))

        return SystemState(
            version=version,
            git_sha=git_sha,
            branch=branch,
            module_count=module_count,
            total_lines=total_lines,
            max_module_lines=max_lines,
            vault_notes=vault_notes,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

    def _get_health_state(self) -> HealthState:
        violations = []
        oversized = []

        for py_file in (self.repo_dir / "ouroboros").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                if lines > 1000:
                    oversized.append(f"{py_file.name} ({lines} lines)")
                    violations.append(f"Module {py_file.name} exceeds 1000 lines ({lines})")
            except Exception:
                pass

        return HealthState(
            all_passing=len(violations) == 0,
            violations=violations,
            oversized_modules=oversized,
        )

    def _get_tools(self) -> List[str]:
        try:
            from ouroboros.tools.registry import ToolRegistry

            registry = ToolRegistry(repo_dir=self.repo_dir, drive_root=self.repo_dir)
            return sorted(registry.available_tools())
        except Exception:
            return []

    def _get_recent_commits(self) -> List[str]:
        import subprocess

        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-5"],
                capture_output=True,
                text=True,
                cwd=self.repo_dir,
            )
            if result.returncode == 0:
                return result.stdout.strip().splitlines()
        except Exception:
            pass
        return []

    def quick_status(self) -> str:
        result = self.query()
        lines = [
            f"**Version**: {result.system.version} | **Branch**: {result.system.branch} | **SHA**: {result.system.git_sha}",
            f"**Modules**: {result.system.module_count} ({result.system.total_lines:,} lines, max {result.system.max_module_lines})",
            f"**Tools**: {len(result.tools_available)} | **Vault**: {result.system.vault_notes} notes",
            f"**Health**: {'✅ OK' if result.health.all_passing else '❌ Issues'} ({len(result.health.violations)} violations)",
            f"**Query time**: {result.query_time_ms}ms",
        ]
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _queries: Dict[str, HeadlessQuery] = {}

    def _get_query(repo_dir: pathlib.Path) -> HeadlessQuery:
        key = str(repo_dir)
        if key not in _queries:
            _queries[key] = HeadlessQuery(repo_dir)
        return _queries[key]

    def query_status(ctx) -> str:
        return _get_query(ctx.repo_dir).quick_status()

    def query_full(ctx) -> str:
        result = _get_query(ctx.repo_dir).query()
        return result.to_json()

    def query_health(ctx) -> str:
        result = _get_query(ctx.repo_dir).query()
        if result.health.all_passing:
            return "✅ All health checks passing"
        return f"❌ {len(result.health.violations)} violations:\n" + "\n".join(
            f"- {v}" for v in result.health.violations[:10]
        )

    return [
        ToolEntry(
            "query_status",
            {
                "name": "query_status",
                "description": "Get instant system status summary. No LLM overhead — returns in milliseconds.",
                "parameters": {"type": "object", "properties": {}},
            },
            query_status,
        ),
        ToolEntry(
            "query_full",
            {
                "name": "query_full",
                "description": "Get full system state as JSON. Instant, no LLM overhead.",
                "parameters": {"type": "object", "properties": {}},
            },
            query_full,
        ),
        ToolEntry(
            "query_health",
            {
                "name": "query_health",
                "description": "Get instant health check results.",
                "parameters": {"type": "object", "properties": {}},
            },
            query_health,
        ),
    ]
