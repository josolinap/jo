"""Evolution sandbox — propose, verify, then apply changes safely.

Three-layer safety:
1. Consciousness proposes changes (never executes directly)
2. Sandbox verifies changes in isolation (syntax + tests)
3. Evolution applies only verified changes

Forbidden files are never modifiable regardless of proposals.
"""

from __future__ import annotations

import logging
import pathlib
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

# Files that can NEVER be modified by evolution
FORBIDDEN_PATHS = frozenset(
    {
        "BIBLE.md",
        "VERSION",
        "pyproject.toml",
        "requirements.txt",
        "ouroboros/consciousness.py",
        "ouroboros/evolution_strategy.py",
        "ouroboros/evolution_proposal.py",
        "ouroboros/evolution_sandbox.py",
        ".jo_protected",
    }
)

# Directories that require explicit approval
PROTECTED_DIRS = frozenset(
    {
        "ouroboros/",
        "supervisor/",
    }
)


@dataclass
class FileChange:
    """A single file change in a proposal."""

    path: str
    old_content: Optional[str] = None  # None for new files
    new_content: str = ""
    description: str = ""


@dataclass
class EvolutionProposal:
    """A proposed change that must be verified before applying."""

    id: str
    description: str
    changes: List[FileChange] = field(default_factory=list)
    risk_level: str = "safe"  # safe / risky / forbidden
    verification_result: str = "not_run"  # not_run / pass / fail
    verification_details: str = ""
    created_by: str = "consciousness"
    created_at: str = ""
    applied: bool = False


class EvolutionSandbox:
    """Verify and apply evolution proposals safely."""

    def __init__(self, repo_dir: pathlib.Path):
        self._repo_dir = repo_dir
        self._proposals: List[EvolutionProposal] = []

    def create_proposal(
        self,
        description: str,
        changes: List[FileChange],
        created_by: str = "consciousness",
    ) -> EvolutionProposal:
        """Create a new evolution proposal."""
        proposal_id = f"prop_{int(time.time())}"

        # Determine risk level
        risk = self._assess_risk(changes)

        proposal = EvolutionProposal(
            id=proposal_id,
            description=description,
            changes=changes,
            risk_level=risk,
            created_by=created_by,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )

        if risk == "forbidden":
            proposal.verification_result = "fail"
            proposal.verification_details = "Proposal modifies forbidden files"

        self._proposals.append(proposal)
        return proposal

    def verify_proposal(self, proposal: EvolutionProposal) -> bool:
        """Verify a proposal in a sandbox before applying."""
        if proposal.risk_level == "forbidden":
            proposal.verification_result = "fail"
            proposal.verification_details = "Cannot verify forbidden proposal"
            return False

        if proposal.risk_level == "risky":
            log.warning("Verifying risky proposal: %s", proposal.description)

        # Create temp directory for sandbox
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir)

            # Copy repo to sandbox
            try:
                self._copy_to_sandbox(tmp_path)
            except Exception as e:
                proposal.verification_result = "fail"
                proposal.verification_details = f"Failed to create sandbox: {e}"
                return False

            # Apply changes to sandbox
            try:
                self._apply_changes_to_sandbox(tmp_path, proposal.changes)
            except Exception as e:
                proposal.verification_result = "fail"
                proposal.verification_details = f"Failed to apply changes: {e}"
                return False

            # Run syntax check
            syntax_ok, syntax_detail = self._check_syntax(tmp_path)
            if not syntax_ok:
                proposal.verification_result = "fail"
                proposal.verification_details = f"Syntax error: {syntax_detail}"
                return False

            # Run tests
            tests_ok, tests_detail = self._run_tests(tmp_path)
            if not tests_ok:
                proposal.verification_result = "fail"
                proposal.verification_details = f"Tests failed: {tests_detail}"
                return False

        proposal.verification_result = "pass"
        proposal.verification_details = "All checks passed"
        return True

    def apply_proposal(self, proposal: EvolutionProposal) -> str:
        """Apply a verified proposal to the actual repo."""
        if proposal.verification_result != "pass":
            return f"Cannot apply: verification {proposal.verification_result}"

        if proposal.risk_level == "forbidden":
            return "Cannot apply: forbidden changes"

        results = []
        for change in proposal.changes:
            path = self._repo_dir / change.path
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(change.new_content, encoding="utf-8")
                results.append(f"OK: {change.path}")
            except Exception as e:
                results.append(f"FAIL: {change.path} ({e})")

        proposal.applied = True
        return "\n".join(results)

    def get_proposal_history(self) -> List[Dict[str, Any]]:
        """Get history of all proposals."""
        return [
            {
                "id": p.id,
                "description": p.description,
                "risk_level": p.risk_level,
                "verification": p.verification_result,
                "applied": p.applied,
                "created_at": p.created_at,
                "created_by": p.created_by,
            }
            for p in self._proposals
        ]

    def _assess_risk(self, changes: List[FileChange]) -> str:
        """Assess risk level of a set of changes."""
        for change in changes:
            # Check forbidden paths
            if change.path in FORBIDDEN_PATHS:
                return "forbidden"
            for forbidden in FORBIDDEN_PATHS:
                if change.path.startswith(forbidden + "/"):
                    return "forbidden"

            # Check protected directories
            for protected in PROTECTED_DIRS:
                if change.path.startswith(protected):
                    return "risky"

        return "safe"

    def _copy_to_sandbox(self, sandbox_dir: pathlib.Path) -> None:
        """Copy essential files to sandbox for testing."""
        # Copy Python files
        for subdir in ["ouroboros", "supervisor", "tests"]:
            src = self._repo_dir / subdir
            if src.exists():
                shutil.copytree(src, sandbox_dir / subdir, dirs_exist_ok=True)

        # Copy config files
        for fname in ["pyproject.toml", "VERSION", "Makefile"]:
            src = self._repo_dir / fname
            if src.exists():
                shutil.copy2(src, sandbox_dir / fname)

    def _apply_changes_to_sandbox(self, sandbox_dir: pathlib.Path, changes: List[FileChange]) -> None:
        """Apply changes to sandbox directory."""
        for change in changes:
            path = sandbox_dir / change.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(change.new_content, encoding="utf-8")

    def _check_syntax(self, sandbox_dir: pathlib.Path) -> tuple[bool, str]:
        """Check Python syntax in sandbox."""
        try:
            result = subprocess.run(
                ["py", "-m", "py_compile", str(sandbox_dir / "ouroboros" / "*.py")],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=str(sandbox_dir),
            )
            if result.returncode != 0:
                return False, result.stderr[:500]
            return True, "OK"
        except Exception as e:
            return False, str(e)

    def _run_tests(self, sandbox_dir: pathlib.Path) -> tuple[bool, str]:
        """Run tests in sandbox."""
        try:
            result = subprocess.run(
                ["py", "-m", "pytest", "tests/", "-q", "--tb=short", "-x"],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=str(sandbox_dir),
            )
            if result.returncode != 0:
                return False, result.stdout[-500:]
            return True, "All tests passed"
        except subprocess.TimeoutExpired:
            return False, "Tests timed out"
        except Exception as e:
            return False, str(e)
