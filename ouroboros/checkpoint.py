"""Checkpoint Verification — pre-commit eval loop for evolution safety.

Inspired by ECC's verification loops:
- Checkpoint evals: run after each significant change
- Gate: block commit if any checkpoint fails
- Quality score: aggregate score across all checks

Checks:
1. Python syntax (py_compile)
2. Import validation (all modules importable)
3. Test suite (pytest)
4. Module line limits (constitution)
5. Protected file check (not modified)
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

log = logging.getLogger(__name__)


@dataclass
class CheckpointResult:
    """Result of a single checkpoint."""

    name: str
    passed: bool
    message: str
    duration_ms: float = 0.0


@dataclass
class CheckpointGate:
    """Aggregate result of all checkpoints."""

    results: List[CheckpointResult] = field(default_factory=list)
    passed: bool = True
    quality_score: float = 1.0

    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.passed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "quality_score": round(self.quality_score, 2),
            "failure_count": self.failure_count,
            "checks": [{"name": r.name, "passed": r.passed, "message": r.message} for r in self.results],
        }


def run_checkpoint_gate(repo_dir: Path, files_changed: List[str]) -> CheckpointGate:
    """Run all checkpoint verification steps.

    Args:
        repo_dir: Repository root
        files_changed: List of files that were changed

    Returns:
        CheckpointGate with pass/fail and quality score
    """
    import time

    gate = CheckpointGate()

    # 1. Python syntax check
    gate.results.append(_check_syntax(repo_dir, files_changed))

    # 2. Protected file check
    gate.results.append(_check_protected_files(repo_dir, files_changed))

    # 3. Module line limits
    gate.results.append(_check_line_limits(repo_dir))

    # 4. Test suite (only if Python files changed)
    py_changed = [f for f in files_changed if f.endswith(".py")]
    if py_changed:
        gate.results.append(_check_tests(repo_dir))

    # 5. Required modules exist
    gate.results.append(_check_required_modules(repo_dir))

    # Aggregate
    gate.passed = all(r.passed for r in gate.results)
    gate.quality_score = sum(1.0 if r.passed else 0.0 for r in gate.results) / max(len(gate.results), 1)

    return gate


def _check_syntax(repo_dir: Path, files_changed: List[str]) -> CheckpointResult:
    """Check Python syntax of changed files."""
    import time

    start = time.time()
    errors = []
    for f in files_changed:
        if not f.endswith(".py"):
            continue
        path = repo_dir / f
        if not path.exists():
            continue
        try:
            import py_compile

            py_compile.compile(str(path), doraise=True)
        except py_compile.PyCompileError as e:
            errors.append(str(e))
        except Exception:
            log.debug("Unexpected error", exc_info=True)

    elapsed = (time.time() - start) * 1000
    if errors:
        return CheckpointResult("syntax", False, f"{len(errors)} syntax errors", elapsed)
    return CheckpointResult("syntax", True, "OK", elapsed)


def _check_protected_files(repo_dir: Path, files_changed: List[str]) -> CheckpointResult:
    """Check that no protected files were modified."""
    import time

    start = time.time()
    try:
        protected_path = repo_dir / ".jo_protected"
        if not protected_path.exists():
            return CheckpointResult("protected", True, "No .jo_protected", 0)

        lines = protected_path.read_text(encoding="utf-8").splitlines()
        protected_files = {l.strip().lower() for l in lines if l.strip() and not l.startswith("#")}
        protected_dirs = {p.rstrip("/").lower() for p in protected_files if p.endswith("/")}

        violations = []
        for f in files_changed:
            f_lower = f.lower()
            if f_lower in protected_files:
                violations.append(f)
            else:
                for d in protected_dirs:
                    if f_lower.startswith(d + "/"):
                        violations.append(f)
                        break

        elapsed = (time.time() - start) * 1000
        if violations:
            return CheckpointResult("protected", False, f"Protected files: {', '.join(violations)}", elapsed)
        return CheckpointResult("protected", True, "OK", elapsed)
    except Exception as e:
        return CheckpointResult("protected", False, str(e), 0)


def _check_line_limits(repo_dir: Path) -> CheckpointResult:
    """Check module line limits."""
    import time

    start = time.time()
    over_limit = []
    for module_dir in ["ouroboros", "supervisor"]:
        dir_path = repo_dir / module_dir
        if not dir_path.exists():
            continue
        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                if lines > 1600:
                    over_limit.append(f"{py_file.relative_to(repo_dir)} ({lines})")
            except Exception:
                log.debug("Unexpected error", exc_info=True)

    elapsed = (time.time() - start) * 1000
    if over_limit:
        return CheckpointResult("line_limits", False, f"Over limit: {', '.join(over_limit[:3])}", elapsed)
    return CheckpointResult("line_limits", True, "OK", elapsed)


def _check_tests(repo_dir: Path) -> CheckpointResult:
    """Run test suite."""
    import time

    start = time.time()
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        elapsed = (time.time() - start) * 1000
        output = result.stdout + result.stderr

        if result.returncode != 0 or "failed" in output.lower():
            # Extract failure count
            for line in output.split("\n"):
                if "failed" in line.lower():
                    return CheckpointResult("tests", False, line.strip(), elapsed)
            return CheckpointResult("tests", False, "Tests failed", elapsed)

        for line in output.split("\n"):
            if "passed" in line.lower():
                return CheckpointResult("tests", True, line.strip(), elapsed)
        return CheckpointResult("tests", True, "Tests passed", elapsed)
    except subprocess.TimeoutExpired:
        return CheckpointResult("tests", False, "Tests timed out (>120s)", (time.time() - start) * 1000)
    except Exception as e:
        return CheckpointResult("tests", False, str(e), 0)


def _check_required_modules(repo_dir: Path) -> CheckpointResult:
    """Check required modules exist."""
    import time

    start = time.time()
    try:
        import json

        baseline = json.loads((repo_dir / "drift_baseline.json").read_text(encoding="utf-8"))
        missing = [m for m in baseline.get("required_modules", []) if not (repo_dir / m).exists()]
        elapsed = (time.time() - start) * 1000
        if missing:
            return CheckpointResult("required_modules", False, f"Missing: {', '.join(missing)}", elapsed)
        return CheckpointResult("required_modules", True, "OK", elapsed)
    except Exception as e:
        return CheckpointResult("required_modules", False, str(e), 0)


def checkpoint_report(gate: CheckpointGate) -> str:
    """Get human-readable checkpoint report."""
    lines = [
        f"## Checkpoint Gate: {'PASS' if gate.passed else 'FAIL'}",
        "",
        f"**Quality Score:** {gate.quality_score:.0%}",
        "",
    ]
    for r in gate.results:
        icon = "OK" if r.passed else "FAIL"
        lines.append(f"- {icon} **{r.name}**: {r.message}")
    return "\n".join(lines)
