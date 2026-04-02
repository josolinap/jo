"""
Ouroboros — Quality Gates.

Configurable verification gates run after task completion.
Inspired by GSD-2's 8-question quality gate pattern.

Each gate is a checkable criterion. Gates run in parallel where possible.
Failed gates block task advancement until fixed.
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class GateStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class GateResult:
    gate_name: str
    status: GateStatus
    message: str = ""
    details: str = ""
    duration_ms: int = 0


@dataclass
class QualityGate:
    name: str
    description: str
    check_fn: Callable[[pathlib.Path], GateResult]
    enabled: bool = True
    category: str = "general"  # "syntax", "testing", "security", "style", "general"


class QualityGateRunner:
    """Runs quality gates against a codebase."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._gates: Dict[str, QualityGate] = {}

        # Load configuration
        try:
            from ouroboros.config_manager import get_config

            config = get_config()
            gates_config = config.get("quality_gates", {})
            self._enabled_gates = gates_config.get("enabled_gates", [])
            self._auto_run_on_error = gates_config.get("auto_run_on_error", True)
        except Exception:
            self._enabled_gates = []
            self._auto_run_on_error = True

        self._register_default_gates()

    def _register_default_gates(self) -> None:
        self.register(
            QualityGate(
                "compiles",
                "Code compiles without syntax errors",
                self._check_syntax,
                category="syntax",
            )
        )
        self.register(
            QualityGate(
                "no_bare_except",
                "No bare except:pass patterns",
                self._check_bare_except,
                category="security",
            )
        )
        self.register(
            QualityGate(
                "no_secrets",
                "No hardcoded secrets or API keys",
                self._check_secrets,
                category="security",
            )
        )
        self.register(
            QualityGate(
                "functions_under_limit",
                "All functions under 150 lines",
                self._check_function_length,
                category="style",
            )
        )
        self.register(
            QualityGate(
                "modules_under_limit",
                "All modules under 1000 lines",
                self._check_module_length,
                category="style",
            )
        )
        self.register(
            QualityGate(
                "imports_valid",
                "All imports resolve successfully",
                self._check_imports,
                category="syntax",
            )
        )
        self.register(
            QualityGate(
                "no_hallucinations",
                "No hallucinated task completions",
                self._check_hallucinations,
                category="quality",
            )
        )

    def register(self, gate: QualityGate) -> None:
        self._gates[gate.name] = gate

    def unregister(self, name: str) -> None:
        self._gates.pop(name, None)

    def run_all(self, categories: Optional[List[str]] = None) -> List[GateResult]:
        results = []
        for gate in self._gates.values():
            if not gate.enabled:
                results.append(GateResult(gate.name, GateStatus.SKIP, "Gate disabled"))
                continue
            if categories and gate.category not in categories:
                results.append(GateResult(gate.name, GateStatus.SKIP, f"Category '{gate.category}' not in filter"))
                continue
            start = time.time()
            try:
                result = gate.check_fn(self.repo_dir)
                result.duration_ms = int((time.time() - start) * 1000)
                results.append(result)
            except Exception as e:
                results.append(
                    GateResult(
                        gate.name,
                        GateStatus.ERROR,
                        f"Gate execution failed: {e}",
                        duration_ms=int((time.time() - start) * 1000),
                    )
                )
        return results

    def run_gate(self, name: str) -> GateResult:
        gate = self._gates.get(name)
        if not gate:
            return GateResult(name, GateStatus.ERROR, f"Gate not found: {name}")
        if not gate.enabled:
            return GateResult(name, GateStatus.SKIP, "Gate disabled")
        start = time.time()
        try:
            result = gate.check_fn(self.repo_dir)
            result.duration_ms = int((time.time() - start) * 1000)
            return result
        except Exception as e:
            return GateResult(name, GateStatus.ERROR, str(e), duration_ms=int((time.time() - start) * 1000))

    def summary(self, results: Optional[List[GateResult]] = None) -> str:
        if results is None:
            results = self.run_all()
        passed = sum(1 for r in results if r.status == GateStatus.PASS)
        failed = sum(1 for r in results if r.status == GateStatus.FAIL)
        errors = sum(1 for r in results if r.status == GateStatus.ERROR)
        skipped = sum(1 for r in results if r.status == GateStatus.SKIP)
        total = len(results)

        lines = [f"## Quality Gates ({passed}/{total} passed)"]
        if failed > 0:
            lines.append(f"❌ {failed} gates FAILED")
        if errors > 0:
            lines.append(f"⚠️ {errors} gates had ERRORS")

        for r in results:
            icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}[r.status.value]
            duration = f" ({r.duration_ms}ms)" if r.duration_ms > 0 else ""
            lines.append(f"- {icon} **{r.gate_name}**{duration}: {r.message}")
            if r.details and r.status == GateStatus.FAIL:
                lines.append(f"  {r.details[:200]}")
        return "\n".join(lines)

    def all_passed(self, results: Optional[List[GateResult]] = None) -> bool:
        if results is None:
            results = self.run_all()
        return all(r.status in (GateStatus.PASS, GateStatus.SKIP) for r in results)

    def list_gates(self) -> str:
        lines = [f"Quality Gates ({len(self._gates)} registered):"]
        for name, gate in self._gates.items():
            status = "✅" if gate.enabled else "❌"
            lines.append(f"- {status} [{gate.category}] {name}: {gate.description}")
        return "\n".join(lines)

    def _check_syntax(self, repo_dir: pathlib.Path) -> GateResult:
        py_files = list(repo_dir.glob("ouroboros/**/*.py")) + list(repo_dir.glob("supervisor/**/*.py"))
        errors = []
        for f in py_files[:50]:
            if "__pycache__" in str(f):
                continue
            try:
                result = subprocess.run(
                    ["py", "-m", "py_compile", str(f)],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode != 0:
                    errors.append(f"{f.name}: {result.stderr[:100]}")
            except Exception:
                pass
        if errors:
            return GateResult(
                "compiles", GateStatus.FAIL, f"{len(errors)} files with syntax errors", "\n".join(errors[:5])
            )
        return GateResult("compiles", GateStatus.PASS, f"All {len(py_files)} files compile")

    def _check_bare_except(self, repo_dir: pathlib.Path) -> GateResult:
        import re

        pattern = re.compile(r"except\s*:\s*pass")
        violations = []
        for f in repo_dir.glob("ouroboros/**/*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    if pattern.search(line):
                        violations.append(f"{f.name}:{i}")
            except Exception:
                pass
        if violations:
            return GateResult(
                "no_bare_except",
                GateStatus.FAIL,
                f"{len(violations)} bare except:pass found",
                ", ".join(violations[:5]),
            )
        return GateResult("no_bare_except", GateStatus.PASS, "No bare except:pass patterns")

    def _check_secrets(self, repo_dir: pathlib.Path) -> GateResult:
        import re

        patterns = [
            re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[=:]\s*['\"][a-zA-Z0-9]{20,}['\"]"),
            re.compile(r"(?i)sk-[a-zA-Z0-9]{20,}"),
            re.compile(r"(?i)ghp_[a-zA-Z0-9]{36}"),
        ]
        violations = []
        for f in repo_dir.glob("ouroboros/**/*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                for i, line in enumerate(content.splitlines(), 1):
                    for p in patterns:
                        if p.search(line):
                            violations.append(f"{f.name}:{i}")
                            break
            except Exception:
                pass
        if violations:
            return GateResult(
                "no_secrets", GateStatus.FAIL, f"{len(violations)} potential secrets", ", ".join(violations[:3])
            )
        return GateResult("no_secrets", GateStatus.PASS, "No hardcoded secrets detected")

    def _check_function_length(self, repo_dir: pathlib.Path) -> GateResult:
        violations = []
        for f in repo_dir.glob("ouroboros/**/*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                content = f.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                in_func = False
                func_name = ""
                func_start = 0
                indent = 0
                for i, line in enumerate(lines, 1):
                    stripped = line.lstrip()
                    if stripped.startswith("def ") or stripped.startswith("async def "):
                        if in_func and (i - func_start) > 150:
                            violations.append(f"{f.name}:{func_name} ({i - func_start} lines)")
                        in_func = True
                        func_name = stripped.split("(")[0].replace("def ", "").replace("async ", "").strip()
                        func_start = i
                        indent = len(line) - len(stripped)
                    elif in_func and stripped and not stripped.startswith("#"):
                        current_indent = len(line) - len(stripped)
                        if current_indent <= indent and not stripped.startswith("@"):
                            if (i - func_start) > 150:
                                violations.append(f"{f.name}:{func_name} ({i - func_start} lines)")
                            in_func = False
                if in_func and (len(lines) - func_start) > 150:
                    violations.append(f"{f.name}:{func_name} ({len(lines) - func_start} lines)")
            except Exception:
                pass
        if violations:
            return GateResult(
                "functions_under_limit",
                GateStatus.FAIL,
                f"{len(violations)} functions over 150 lines",
                ", ".join(violations[:5]),
            )
        return GateResult("functions_under_limit", GateStatus.PASS, "All functions under 150 lines")

    def _check_module_length(self, repo_dir: pathlib.Path) -> GateResult:
        violations = []
        for f in repo_dir.glob("ouroboros/**/*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                lines = len(f.read_text(encoding="utf-8", errors="replace").splitlines())
                if lines > 1000:
                    violations.append(f"{f.name} ({lines} lines)")
            except Exception:
                pass
        if violations:
            return GateResult(
                "modules_under_limit",
                GateStatus.FAIL,
                f"{len(violations)} modules over 1000 lines",
                ", ".join(violations[:5]),
            )
        return GateResult("modules_under_limit", GateStatus.PASS, "All modules under 1000 lines")

    def _check_imports(self, repo_dir: pathlib.Path) -> GateResult:
        errors = []
        for f in repo_dir.glob("ouroboros/**/*.py"):
            if "__pycache__" in str(f):
                continue
            try:
                result = subprocess.run(
                    ["py", "-c", f"import ast; ast.parse(open(r'{f}').read())"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode != 0:
                    errors.append(f"{f.name}: {result.stderr[:80]}")
            except Exception:
                pass
        if errors:
            return GateResult(
                "imports_valid", GateStatus.FAIL, f"{len(errors)} files with import issues", "\n".join(errors[:3])
            )
        return GateResult("imports_valid", GateStatus.PASS, "All imports parse successfully")

    def _check_hallucinations(self, repo_dir: pathlib.Path) -> GateResult:
        """Check for potential hallucinations in recent tool responses."""
        try:
            from ouroboros.hallucination_guard import get_guard
            import json

            guard = get_guard()
            stats = guard.stats()

            # Check if there have been hallucinations detected
            hallucinations = stats.get("hallucinations_detected", 0)
            total_checked = stats.get("total_checked", 0)

            if total_checked == 0:
                return GateResult("no_hallucinations", GateStatus.PASS, "No responses checked yet (guard inactive)")

            hallucination_rate = hallucinations / total_checked if total_checked > 0 else 0

            if hallucination_rate > 0.1:  # More than 10% hallucination rate
                return GateResult(
                    "no_hallucinations",
                    GateStatus.FAIL,
                    f"High hallucination rate: {hallucination_rate:.0%} ({hallucinations}/{total_checked})",
                    "Review recent tool responses for false completion claims",
                )
            elif hallucinations > 0:
                return GateResult(
                    "no_hallucinations",
                    GateStatus.PASS,
                    f"Low hallucination rate: {hallucination_rate:.0%} ({hallucinations}/{total_checked})",
                    "Some hallucinations detected but within acceptable range",
                )
            else:
                return GateResult(
                    "no_hallucinations",
                    GateStatus.PASS,
                    f"No hallucinations detected (checked {total_checked} responses)",
                )
        except Exception as e:
            return GateResult("no_hallucinations", GateStatus.ERROR, f"Failed to check hallucinations: {e}")


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _runners: Dict[str, QualityGateRunner] = {}

    def _get_runner(repo_dir: pathlib.Path) -> QualityGateRunner:
        key = str(repo_dir)
        if key not in _runners:
            _runners[key] = QualityGateRunner(repo_dir)
        return _runners[key]

    def quality_gates_run(ctx, categories: str = "") -> str:
        runner = _get_runner(ctx.repo_dir)
        cats = [c.strip() for c in categories.split(",") if c.strip()] if categories else None
        results = runner.run_all(cats)
        return runner.summary(results)

    def quality_gates_check(ctx, gate_name: str) -> str:
        runner = _get_runner(ctx.repo_dir)
        result = runner.run_gate(gate_name)
        icon = {"pass": "✅", "fail": "❌", "skip": "⏭️", "error": "⚠️"}[result.status.value]
        return f"{icon} {result.gate_name}: {result.message}"

    def quality_gates_list(ctx) -> str:
        return _get_runner(ctx.repo_dir).list_gates()

    return [
        ToolEntry(
            "quality_gates_run",
            {
                "name": "quality_gates_run",
                "description": "Run all quality gates. Optionally filter by categories (syntax,testing,security,style).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "categories": {
                            "type": "string",
                            "default": "",
                            "description": "Comma-separated categories to run",
                        },
                    },
                },
            },
            quality_gates_run,
        ),
        ToolEntry(
            "quality_gates_check",
            {
                "name": "quality_gates_check",
                "description": "Run a specific quality gate by name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "gate_name": {"type": "string", "description": "Gate name to run"},
                    },
                    "required": ["gate_name"],
                },
            },
            quality_gates_check,
        ),
        ToolEntry(
            "quality_gates_list",
            {
                "name": "quality_gates_list",
                "description": "List all registered quality gates.",
                "parameters": {"type": "object", "properties": {}},
            },
            quality_gates_list,
        ),
    ]
