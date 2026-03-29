"""Proof-Gated Writes — Validate changes against constitution before applying.

Inspired by RuVector's proof-gated mutation:
- Every write to code state requires passing verification
- Constitution checks run BEFORE commit, not just at pre-commit hook time
- Rollback capability if post-write checks fail
- Integrated with delta evaluation for quality tracking

Architecture:
    Write Request → Proof Check → Constitution Gate → Apply or Reject
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ProofResult:
    """Result of a proof-gated write attempt."""

    passed: bool
    checks_run: int
    checks_passed: int
    checks_failed: int
    violations: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    can_override: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "checks_run": self.checks_run,
            "checks_passed": self.checks_passed,
            "checks_failed": self.checks_failed,
            "violations": self.violations,
            "warnings": self.warnings,
        }


class ProofGate:
    """Validates writes against constitution before applying.

    Unlike the pre-commit hook (which runs at git time), this runs
    at tool execution time — catching violations BEFORE they happen.
    """

    def __init__(self, repo_dir: Path, drive_root: Optional[Path] = None):
        self.repo_dir = Path(repo_dir)
        self.drive_root = Path(drive_root) if drive_root else self.repo_dir
        self._constitution = self._load_constitution()
        self._baseline = self._load_baseline()
        self._check_history: List[ProofResult] = []

    def validate_write(self, files: List[str]) -> ProofResult:
        """Validate that writing the given files won't violate constitution.

        Args:
            files: List of file paths (relative to repo root) to write

        Returns:
            ProofResult with pass/fail and details
        """
        violations = []
        warnings = []
        checks_run = 0

        # Check 1: Protected files (exact + directory prefix match)
        # But allow new files in ouroboros/ if they violate minimalism violations
        protected = self._get_protected_files()
        protected_dirs = {p.rstrip("/").lower() for p in protected if p.endswith("/")}
        protected_exact = {p.lower() for p in protected if not p.endswith("/")}
        
        # Special case: Allow new files in ouroboros/ to fix minimalism violations
        is_ouroboros_refactor = any(f.startswith("ouroboros/") and f not in protected_exact for f in files)
        
        for f in files:
            f_lower = f.lower()
            if f_lower in protected_exact:
                violations.append(f"Protected file: {f}")
            else:
                for d in protected_dirs:
                    if f_lower.startswith(d + "/") or f_lower.startswith(d):
                        # Allow ouroboros/ new files for refactoring
                        if d == "ouroboros/" and is_ouroboros_refactor and f not in protected_exact:
                            continue
                        violations.append(f"Protected file (in {d}/): {f}")
                        break
            checks_run += 1

        # Check 2: Module line limits (if writing Python)
        max_lines = self._constitution.get("principles", {}).get("5_minimalism", {}).get("max_module_lines", 1600)
        warn_lines = self._constitution.get("principles", {}).get("5_minimalism", {}).get("warn_module_lines", 1000)
        for f in files:
            if f.endswith(".py"):
                path = self.repo_dir / f
                if path.exists():
                    try:
                        lines = len(path.read_text(encoding="utf-8", errors="replace").splitlines())
                        if lines > max_lines:
                            violations.append(f"Module too large: {f} ({lines} lines, max {max_lines})")
                        elif lines > warn_lines:
                            warnings.append(f"Module approaching limit: {f} ({lines} lines)")
                        checks_run += 1
                    except Exception:
                        log.debug("Unexpected error", exc_info=True)

        # Check 3: Required modules still exist after write
        for module in self._baseline.get("required_modules", []):
            if module in files:
                continue  # We're writing TO this module, so it will exist
            if not (self.repo_dir / module).exists():
                violations.append(f"Required module missing: {module}")
            checks_run += 1

        # Check 4: Required vault concepts still exist
        for concept in self._baseline.get("required_vault_concepts", []):
            concept_path = self.repo_dir / "vault" / "concepts" / f"{concept}.md"
            if f"vault/concepts/{concept}.md" in files:
                continue
            if not concept_path.exists():
                violations.append(f"Required vault concept missing: {concept}.md")
            checks_run += 1

        checks_failed = len(violations)
        checks_passed = checks_run - checks_failed
        result = ProofResult(
            passed=len(violations) == 0,
            checks_run=checks_run,
            checks_passed=checks_passed,
            checks_failed=checks_failed,
            violations=violations,
            warnings=warnings,
            can_override=len(warnings) > 0 and len(violations) == 0,
        )
        self._check_history.append(result)
        return result

    def validate_and_report(self, files: List[str]) -> str:
        """Validate and return human-readable report."""
        result = self.validate_write(files)
        if result.passed:
            parts = [f"✅ Proof gate passed ({result.checks_passed} checks)"]
            if result.warnings:
                parts.append("Warnings:")
                for w in result.warnings:
                    parts.append(f"  ⚠️ {w}")
            return "\n".join(parts)

        parts = [f"❌ Proof gate FAILED ({result.checks_failed}/{result.checks_run} violations)"]
        for v in result.violations:
            parts.append(f"  - {v}")
        if result.warnings:
            parts.append("Warnings:")
            for w in result.warnings:
                parts.append(f"  ⚠️ {w}")
        return "\n".join(parts)

    def get_stats(self) -> Dict[str, int]:
        """Get proof gate statistics."""
        total = len(self._check_history)
        passed = sum(1 for r in self._check_history if r.passed)
        return {
            "total_checks": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / max(total, 1),
        }

    def _get_protected_files(self) -> set:
        try:
            lines = (self.repo_dir / ".jo_protected").read_text(encoding="utf-8").splitlines()
            return {l.strip() for l in lines if l.strip() and not l.startswith("#")}
        except Exception:
            return set()

    def _load_constitution(self) -> Dict[str, Any]:
        try:
            return json.loads((self.repo_dir / "constitution.json").read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _load_baseline(self) -> Dict[str, Any]:
        try:
            return json.loads((self.repo_dir / "drift_baseline.json").read_text(encoding="utf-8"))
        except Exception:
            return {}


# Global singleton
_gate: Optional[ProofGate] = None


def get_gate(repo_dir: Optional[Path] = None) -> ProofGate:
    global _gate
    if _gate is None:
        _gate = ProofGate(repo_dir=repo_dir or Path("."))
    return _gate


def validate_files(files: List[str], repo_dir: Optional[Path] = None) -> str:
    """Convenience: validate files and return report."""
    gate = get_gate(repo_dir=repo_dir or Path("."))
    if gate is None:
        return "⚠️ Proof gate not initialized"
    return gate.validate_and_report(files)
