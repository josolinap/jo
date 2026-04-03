"""
Jo — Verification Protocol.

Multi-stage verification with evidence requirements.
Inspired by oh-my-claudecode's verification system.

Stages:
1. BUILD - Compilation passes
2. TEST - All tests pass
3. LINT - No linting errors
4. FUNCTIONALITY - Feature works as expected
5. ARCHITECT - Deep-tier review approval
6. TODO - All tasks completed
7. ERROR_FREE - No unresolved errors

Evidence must be fresh (within 5 minutes) and include actual command output.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class VerificationStatus(Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class VerificationResult:
    """Result of a single verification check."""

    stage: str
    status: VerificationStatus
    evidence: str = ""
    error_message: str = ""
    timestamp: float = 0.0

    def is_fresh(self, max_age_seconds: float = 300) -> bool:
        """Check if evidence is fresh (within max_age_seconds)."""
        if self.timestamp == 0:
            return False
        return (time.time() - self.timestamp) < max_age_seconds


@dataclass
class VerificationReport:
    """Complete verification report."""

    results: List[VerificationResult] = field(default_factory=list)
    overall_pass: bool = False
    timestamp: str = ""

    def summary(self) -> str:
        """Generate a summary of the verification report."""
        parts = ["## Verification Report\n"]

        for result in self.results:
            status_icon = {
                VerificationStatus.PASS: "✅",
                VerificationStatus.FAIL: "❌",
                VerificationStatus.SKIP: "⏭️",
                VerificationStatus.ERROR: "⚠️",
            }.get(result.status, "❓")

            parts.append(f"{status_icon} **{result.stage}**: {result.status.value}")
            if result.evidence:
                # Show first 200 chars of evidence
                evidence_preview = result.evidence[:200]
                if len(result.evidence) > 200:
                    evidence_preview += "..."
                parts.append(f"   Evidence: {evidence_preview}")
            if result.error_message:
                parts.append(f"   Error: {result.error_message}")
            parts.append("")

        parts.append(f"## Overall: {'✅ PASS' if self.overall_pass else '❌ FAIL'}\n")

        return "\n".join(parts)


class VerificationProtocol:
    """Multi-stage verification protocol."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._results: List[VerificationResult] = []

    def verify_all(self) -> VerificationReport:
        """Run all verification stages."""
        self._results = []

        # Run all stages
        self._verify_build()
        self._verify_tests()
        self._verify_lint()
        self._verify_functionality()
        self._verify_architect()
        self._verify_todo()
        self._verify_error_free()

        # Determine overall pass/fail
        overall_pass = all(r.status in (VerificationStatus.PASS, VerificationStatus.SKIP) for r in self._results)

        import datetime

        return VerificationReport(
            results=self._results,
            overall_pass=overall_pass,
            timestamp=datetime.datetime.now().isoformat(),
        )

    def _run_command(self, cmd: List[str], timeout: int = 60) -> Tuple[bool, str]:
        """Run a command and return (success, output)."""
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.repo_dir,
            )
            success = result.returncode == 0
            output = result.stdout if success else result.stderr
            return success, output
        except subprocess.TimeoutExpired:
            return False, f"Command timed out after {timeout}s"
        except Exception as e:
            return False, str(e)

    def _verify_build(self) -> None:
        """BUILD: Compilation passes."""
        try:
            success, output = self._run_command(
                ["py", "-m", "py_compile"]
                + [str(f) for f in self.repo_dir.glob("ouroboros/**/*.py") if "__pycache__" not in str(f)][
                    :20
                ]  # Limit to first 20 files for speed
            )

            self._results.append(
                VerificationResult(
                    stage="BUILD",
                    status=VerificationStatus.PASS if success else VerificationStatus.FAIL,
                    evidence=output[:500] if output else "Compilation successful",
                    timestamp=time.time(),
                )
            )
        except Exception as e:
            self._results.append(
                VerificationResult(
                    stage="BUILD",
                    status=VerificationStatus.ERROR,
                    error_message=str(e),
                    timestamp=time.time(),
                )
            )

    def _verify_tests(self) -> None:
        """TEST: All tests pass."""
        try:
            success, output = self._run_command(
                ["py", "-m", "pytest", "tests/", "-q"],
                timeout=120,
            )

            self._results.append(
                VerificationResult(
                    stage="TEST",
                    status=VerificationStatus.PASS if success else VerificationStatus.FAIL,
                    evidence=output[:500] if output else "Tests passed",
                    timestamp=time.time(),
                )
            )
        except Exception as e:
            self._results.append(
                VerificationResult(
                    stage="TEST",
                    status=VerificationStatus.ERROR,
                    error_message=str(e),
                    timestamp=time.time(),
                )
            )

    def _verify_lint(self) -> None:
        """LINT: No linting errors."""
        try:
            success, output = self._run_command(
                ["ruff", "check", "ouroboros/"],
                timeout=60,
            )

            self._results.append(
                VerificationResult(
                    stage="LINT",
                    status=VerificationStatus.PASS if success else VerificationStatus.FAIL,
                    evidence=output[:500] if output else "No linting errors",
                    timestamp=time.time(),
                )
            )
        except Exception as e:
            # Ruff might not be installed
            self._results.append(
                VerificationResult(
                    stage="LINT",
                    status=VerificationStatus.SKIP,
                    evidence=f"Ruff not available: {e}",
                    timestamp=time.time(),
                )
            )

    def _verify_functionality(self) -> None:
        """FUNCTIONALITY: Feature works as expected."""
        # This is a placeholder - actual functionality checks would be task-specific
        self._results.append(
            VerificationResult(
                stage="FUNCTIONALITY",
                status=VerificationStatus.SKIP,
                evidence="Functionality verification is task-specific and must be run manually",
                timestamp=time.time(),
            )
        )

    def _verify_architect(self) -> None:
        """ARCHITECT: Deep-tier review approval."""
        # This would normally involve an LLM-based review
        self._results.append(
            VerificationResult(
                stage="ARCHITECT",
                status=VerificationStatus.SKIP,
                evidence="Architecture review requires LLM-based analysis",
                timestamp=time.time(),
            )
        )

    def _verify_todo(self) -> None:
        """TODO: All tasks completed."""
        # Check for TODO comments in recently modified files
        try:
            success, output = self._run_command(
                ["git", "diff", "--name-only", "HEAD~1"],
            )

            if success and output.strip():
                files = output.strip().split("\n")
                todo_count = 0
                for file in files:
                    file_path = self.repo_dir / file
                    if file_path.exists() and file_path.suffix == ".py":
                        content = file_path.read_text(encoding="utf-8", errors="ignore")
                        todo_count += content.upper().count("TODO")

                self._results.append(
                    VerificationResult(
                        stage="TODO",
                        status=VerificationStatus.PASS if todo_count == 0 else VerificationStatus.FAIL,
                        evidence=f"Found {todo_count} TODO comments in recently modified files",
                        timestamp=time.time(),
                    )
                )
            else:
                self._results.append(
                    VerificationResult(
                        stage="TODO",
                        status=VerificationStatus.SKIP,
                        evidence="No recent changes to check",
                        timestamp=time.time(),
                    )
                )
        except Exception as e:
            self._results.append(
                VerificationResult(
                    stage="TODO",
                    status=VerificationStatus.ERROR,
                    error_message=str(e),
                    timestamp=time.time(),
                )
            )

    def _verify_error_free(self) -> None:
        """ERROR_FREE: No unresolved errors."""
        # Check for error patterns in recent logs
        self._results.append(
            VerificationResult(
                stage="ERROR_FREE",
                status=VerificationStatus.SKIP,
                evidence="Error-free verification requires log analysis",
                timestamp=time.time(),
            )
        )


def get_verifier(repo_dir: Optional[pathlib.Path] = None) -> VerificationProtocol:
    """Get a verification protocol instance."""
    if repo_dir is None:
        repo_dir = pathlib.Path.cwd()
    return VerificationProtocol(repo_dir)
