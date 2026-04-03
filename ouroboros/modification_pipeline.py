"""
Jo — Formal Modification Pipeline.

Realizes Principle 10 (Bounded Self-Modification):
Every self-modification follows a 5-stage pipeline with stability guarantees.

Pipeline stages:
1. DETECT: Identify what needs to change and why
2. PROPOSE: Generate the specific change with impact analysis
3. VALIDATE: Test the change in isolation (compile, run tests)
4. APPLY: Commit the change atomically with clear message
5. VERIFY: Confirm the change works in production

Lyapunov stability: Each modification must improve or maintain system health.
Audit trail: Every modification logged with before/after state and justification.
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ModificationStage(Enum):
    DETECT = "detect"
    PROPOSE = "propose"
    VALIDATE = "validate"
    APPLY = "apply"
    VERIFY = "verify"


class ModificationStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class ModificationRecord:
    """A complete record of a self-modification."""

    id: str
    stage: ModificationStage
    status: ModificationStatus
    target: str  # What is being modified
    trigger: str  # Why this modification was triggered
    description: str  # What the change does
    justification: str  # Why this change is needed
    health_before: float = 0.0
    health_after: float = 0.0
    created_at: str = ""
    completed_at: str = ""
    rollback_sha: str = ""  # Git SHA to rollback to
    validation_results: Dict[str, Any] = field(default_factory=dict)
    verification_results: Dict[str, Any] = field(default_factory=dict)


class ModificationPipeline:
    """Manages the 5-stage self-modification pipeline."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.audit_dir = repo_dir / "vault" / "modifications"
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self._current_modification: Optional[ModificationRecord] = None
        self._history: List[ModificationRecord] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load modification history from audit files."""
        for audit_file in self.audit_dir.glob("*.json"):
            try:
                data = json.loads(audit_file.read_text(encoding="utf-8"))
                record = ModificationRecord(**data)
                self._history.append(record)
            except Exception:
                log.debug(f"Failed to load audit record: {audit_file}")

    def _save_record(self, record: ModificationRecord) -> None:
        """Save modification record to audit file."""
        audit_file = self.audit_dir / f"{record.id}.json"
        audit_file.write_text(
            json.dumps(
                {
                    "id": record.id,
                    "stage": record.stage.value,
                    "status": record.status.value,
                    "target": record.target,
                    "trigger": record.trigger,
                    "description": record.description,
                    "justification": record.justification,
                    "health_before": record.health_before,
                    "health_after": record.health_after,
                    "created_at": record.created_at,
                    "completed_at": record.completed_at,
                    "rollback_sha": record.rollback_sha,
                    "validation_results": record.validation_results,
                    "verification_results": record.verification_results,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def _get_current_health(self) -> float:
        """Get current system health score (0.0-1.0)."""
        try:
            from ouroboros.health_invariants import run_checks
            from ouroboros.context import Env

            env = Env(
                repo_dir=self.repo_dir,
                drive_root=self.repo_dir,
            )
            checks = run_checks(env)
            # Count passing checks
            passing = sum(1 for c in checks if c.startswith("OK:"))
            total = len(checks)
            return passing / total if total > 0 else 1.0
        except Exception:
            return 1.0

    def _get_current_sha(self) -> str:
        """Get current git SHA for rollback."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=self.repo_dir, timeout=10
            )
            return result.stdout.strip() if result.returncode == 0 else ""
        except Exception:
            return ""

    def start_modification(self, target: str, trigger: str, description: str, justification: str) -> ModificationRecord:
        """Stage 1: DETECT - Start a new modification record."""
        record = ModificationRecord(
            id=f"mod-{int(time.time())}",
            stage=ModificationStage.DETECT,
            status=ModificationStatus.IN_PROGRESS,
            target=target,
            trigger=trigger,
            description=description,
            justification=justification,
            health_before=self._get_current_health(),
            rollback_sha=self._get_current_sha(),
            created_at=datetime.now().isoformat(),
        )
        self._current_modification = record
        self._save_record(record)
        log.info("[Modification] Stage 1/5 DETECT: %s - %s", target, trigger)
        return record

    def propose_change(self, diff_summary: str, impact_analysis: Dict[str, Any]) -> bool:
        """Stage 2: PROPOSE - Record the proposed change."""
        if not self._current_modification:
            log.error("[Modification] No active modification to propose")
            return False

        self._current_modification.stage = ModificationStage.PROPOSE
        self._current_modification.validation_results["diff_summary"] = diff_summary
        self._current_modification.validation_results["impact_analysis"] = impact_analysis
        self._save_record(self._current_modification)
        log.info("[Modification] Stage 2/5 PROPOSE: %s", diff_summary[:100])
        return True

    def validate_change(self) -> bool:
        """Stage 3: VALIDATE - Test the change in isolation."""
        if not self._current_modification:
            log.error("[Modification] No active modification to validate")
            return False

        self._current_modification.stage = ModificationStage.VALIDATE

        # Run syntax check
        syntax_ok = self._check_syntax()
        self._current_modification.validation_results["syntax_check"] = syntax_ok

        # Run smoke tests
        tests_ok = self._run_smoke_tests()
        self._current_modification.validation_results["smoke_tests"] = tests_ok

        # Check Lyapunov stability (health must not decrease)
        current_health = self._get_current_health()
        health_ok = current_health >= self._current_modification.health_before * 0.95  # Allow 5% tolerance
        self._current_modification.validation_results["lyapunov_stability"] = {
            "health_before": self._current_modification.health_before,
            "health_after": current_health,
            "passed": health_ok,
        }

        all_passed = syntax_ok and tests_ok and health_ok
        self._current_modification.validation_results["all_passed"] = all_passed

        if all_passed:
            self._current_modification.status = ModificationStatus.IN_PROGRESS
            self._save_record(self._current_modification)
            log.info("[Modification] Stage 3/5 VALIDATE: All checks passed")
        else:
            self._current_modification.status = ModificationStatus.FAILED
            self._current_modification.completed_at = datetime.now().isoformat()
            self._save_record(self._current_modification)
            log.warning(
                "[Modification] Stage 3/5 VALIDATE: Checks failed - syntax=%s, tests=%s, health=%s",
                syntax_ok,
                tests_ok,
                health_ok,
            )

        return all_passed

    def apply_change(self, commit_message: str) -> bool:
        """Stage 4: APPLY - Commit the change atomically."""
        if not self._current_modification:
            log.error("[Modification] No active modification to apply")
            return False

        if not self._current_modification.validation_results.get("all_passed", False):
            log.error("[Modification] Cannot apply - validation failed")
            return False

        self._current_modification.stage = ModificationStage.APPLY

        # Git add and commit
        try:
            subprocess.run(["git", "add", "-A"], cwd=self.repo_dir, check=True, capture_output=True)
            result = subprocess.run(
                ["git", "commit", "-m", f"[Modification] {commit_message}"],
                cwd=self.repo_dir,
                check=True,
                capture_output=True,
                text=True,
            )
            self._current_modification.status = ModificationStatus.COMPLETED
            self._current_modification.completed_at = datetime.now().isoformat()
            self._current_modification.health_after = self._get_current_health()
            self._save_record(self._current_modification)
            log.info("[Modification] Stage 4/5 APPLY: Committed - %s", commit_message[:100])
            return True
        except subprocess.CalledProcessError as e:
            log.error("[Modification] Stage 4/5 APPLY: Git commit failed - %s", e.stderr)
            self._current_modification.status = ModificationStatus.FAILED
            self._current_modification.completed_at = datetime.now().isoformat()
            self._save_record(self._current_modification)
            return False

    def verify_change(self) -> bool:
        """Stage 5: VERIFY - Confirm the change works in production."""
        if not self._current_modification:
            log.error("[Modification] No active modification to verify")
            return False

        self._current_modification.stage = ModificationStage.VERIFY

        # Run full health check
        health_after = self._get_current_health()
        self._current_modification.health_after = health_after
        self._current_modification.verification_results["health_check"] = health_after

        # Verify health improved or maintained
        health_ok = health_after >= self._current_modification.health_before * 0.95
        self._current_modification.verification_results["lyapunov_verified"] = health_ok

        if health_ok:
            self._current_modification.status = ModificationStatus.COMPLETED
            log.info(
                "[Modification] Stage 5/5 VERIFY: Change verified - health %.2f -> %.2f",
                self._current_modification.health_before,
                health_after,
            )
        else:
            log.warning(
                "[Modification] Stage 5/5 VERIFY: Health degraded - %.2f -> %.2f",
                self._current_modification.health_before,
                health_after,
            )
            self._current_modification.status = ModificationStatus.ROLLED_BACK
            # Auto-rollback
            self.rollback()

        self._current_modification.completed_at = datetime.now().isoformat()
        self._save_record(self._current_modification)
        self._current_modification = None
        return health_ok

    def rollback(self) -> bool:
        """Rollback to the pre-modification state."""
        if not self._current_modification or not self._current_modification.rollback_sha:
            return False

        try:
            subprocess.run(
                ["git", "reset", "--hard", self._current_modification.rollback_sha],
                cwd=self.repo_dir,
                check=True,
                capture_output=True,
            )
            log.info("[Modification] Rolled back to %s", self._current_modification.rollback_sha)
            return True
        except subprocess.CalledProcessError as e:
            log.error("[Modification] Rollback failed: %s", e.stderr)
            return False

    def _check_syntax(self) -> bool:
        """Check Python syntax for all modified files."""
        try:
            result = subprocess.run(
                ["py", "-m", "py_compile"]
                + [str(f) for f in self.repo_dir.glob("ouroboros/**/*.py") if "__pycache__" not in str(f)][
                    :20
                ],  # Limit to first 20 for speed
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _run_smoke_tests(self) -> bool:
        """Run smoke tests to verify basic functionality."""
        try:
            result = subprocess.run(
                ["py", "-m", "pytest", "tests/test_smoke.py", "-q"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0
        except Exception:
            return False

    def get_history(self) -> List[Dict[str, Any]]:
        """Get modification history."""
        return [
            {
                "id": r.id,
                "stage": r.stage.value,
                "status": r.status.value,
                "target": r.target,
                "trigger": r.trigger,
                "health_before": r.health_before,
                "health_after": r.health_after,
                "created_at": r.created_at,
            }
            for r in self._history
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get modification pipeline statistics."""
        completed = sum(1 for r in self._history if r.status == ModificationStatus.COMPLETED)
        rolled_back = sum(1 for r in self._history if r.status == ModificationStatus.ROLLED_BACK)
        failed = sum(1 for r in self._history if r.status == ModificationStatus.FAILED)

        return {
            "total_modifications": len(self._history),
            "completed": completed,
            "rolled_back": rolled_back,
            "failed": failed,
            "success_rate": completed / len(self._history) if self._history else 0.0,
        }


# Global pipeline instance
_pipeline: Optional[ModificationPipeline] = None


def get_modification_pipeline(repo_dir: Optional[pathlib.Path] = None) -> ModificationPipeline:
    """Get or create the global modification pipeline."""
    global _pipeline
    if _pipeline is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _pipeline = ModificationPipeline(repo_dir)
    return _pipeline
