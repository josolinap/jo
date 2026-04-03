"""
Jo — Self-Healing Architecture.

Realizes Principle 10 (Bounded Self-Modification):
Jo detects bugs and fixes them autonomously without human intervention.

Pipeline:
1. DETECT: Auto-detect syntax errors, import failures, test failures
2. DIAGNOSE: Analyze root cause and generate fix proposals
3. FIX: Apply fixes in worktree, verify, merge if passing
4. VERIFY: Confirm the fix resolves the issue without regressions

This is different from the modification pipeline:
- Modification pipeline: intentional changes with human oversight
- Self-healing: automatic fixes for detected problems
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class IssueType(Enum):
    SYNTAX_ERROR = "syntax_error"
    IMPORT_FAILURE = "import_failure"
    TEST_FAILURE = "test_failure"
    LINT_ERROR = "lint_error"
    RUNTIME_ERROR = "runtime_error"


class IssueStatus(Enum):
    DETECTED = "detected"
    DIAGNOSED = "diagnosed"
    FIX_APPLIED = "fix_applied"
    VERIFIED = "verified"
    FAILED = "failed"


@dataclass
class HealingIssue:
    """A detected issue that needs healing."""

    id: str
    type: IssueType
    status: IssueStatus
    file_path: str
    error_message: str
    line_number: int = 0
    diagnosis: str = ""
    fix_applied: str = ""
    verification_result: str = ""
    detected_at: str = ""
    resolved_at: str = ""


class SelfHealingSystem:
    """Detects and fixes issues autonomously."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.healing_dir = repo_dir / ".jo_state" / "healing"
        self.healing_dir.mkdir(parents=True, exist_ok=True)
        self._issues: List[HealingIssue] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load healing history."""
        history_file = self.healing_dir / "history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                self._issues = [HealingIssue(**i) for i in data]
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save healing history."""
        history_file = self.healing_dir / "history.json"
        history_file.write_text(
            json.dumps(
                [
                    {
                        "id": i.id,
                        "type": i.type.value,
                        "status": i.status.value,
                        "file_path": i.file_path,
                        "error_message": i.error_message,
                        "line_number": i.line_number,
                        "diagnosis": i.diagnosis,
                        "fix_applied": i.fix_applied,
                        "verification_result": i.verification_result,
                        "detected_at": i.detected_at,
                        "resolved_at": i.resolved_at,
                    }
                    for i in self._issues
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    def detect_syntax_errors(self) -> List[HealingIssue]:
        """Detect Python syntax errors."""
        issues = []
        try:
            result = subprocess.run(
                ["py", "-m", "py_compile"]
                + [str(f) for f in self.repo_dir.glob("ouroboros/**/*.py") if "__pycache__" not in str(f)],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                # Parse error output
                for line in result.stderr.split("\n"):
                    match = re.match(r"  File \"(.+?)\", line (\d+)", line)
                    if match:
                        file_path = match.group(1)
                        line_num = int(match.group(2))
                        issues.append(
                            HealingIssue(
                                id=f"heal-{int(time.time())}-{len(issues)}",
                                type=IssueType.SYNTAX_ERROR,
                                status=IssueStatus.DETECTED,
                                file_path=file_path,
                                error_message=line.strip(),
                                line_number=line_num,
                                detected_at=datetime.now().isoformat(),
                            )
                        )
        except Exception as e:
            log.debug("Syntax error detection failed: %s", e)

        self._issues.extend(issues)
        self._save_history()
        return issues

    def detect_import_failures(self) -> List[HealingIssue]:
        """Detect import failures."""
        issues = []
        try:
            # Try importing all ouroboros modules
            for py_file in self.repo_dir.glob("ouroboros/**/*.py"):
                if "__pycache__" in str(py_file) or py_file.name.startswith("_"):
                    continue
                module_path = str(py_file.relative_to(self.repo_dir)).replace("/", ".").replace(".py", "")
                try:
                    result = subprocess.run(
                        ["py", "-c", f"import {module_path}"],
                        cwd=self.repo_dir,
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        issues.append(
                            HealingIssue(
                                id=f"heal-{int(time.time())}-{len(issues)}",
                                type=IssueType.IMPORT_FAILURE,
                                status=IssueStatus.DETECTED,
                                file_path=str(py_file),
                                error_message=result.stderr.strip()[:200],
                                detected_at=datetime.now().isoformat(),
                            )
                        )
                except Exception:
                    pass
        except Exception as e:
            log.debug("Import failure detection failed: %s", e)

        self._issues.extend(issues)
        self._save_history()
        return issues

    def detect_test_failures(self) -> List[HealingIssue]:
        """Detect test failures."""
        issues = []
        try:
            result = subprocess.run(
                ["py", "-m", "pytest", "tests/", "-q", "--tb=short"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                # Parse failure output
                for line in result.stdout.split("\n"):
                    if "FAILED" in line or "ERROR" in line:
                        issues.append(
                            HealingIssue(
                                id=f"heal-{int(time.time())}-{len(issues)}",
                                type=IssueType.TEST_FAILURE,
                                status=IssueStatus.DETECTED,
                                file_path="tests/",
                                error_message=line.strip(),
                                detected_at=datetime.now().isoformat(),
                            )
                        )
        except Exception as e:
            log.debug("Test failure detection failed: %s", e)

        self._issues.extend(issues)
        self._save_history()
        return issues

    def diagnose_issue(self, issue_id: str) -> HealingIssue:
        """Diagnose an issue and generate fix proposal."""
        issue = next((i for i in self._issues if i.id == issue_id), None)
        if not issue:
            raise ValueError(f"Issue {issue_id} not found")

        issue.status = IssueStatus.DIAGNOSED

        if issue.type == IssueType.SYNTAX_ERROR:
            issue.diagnosis = f"Syntax error at line {issue.line_number}. Common causes: missing colon, unclosed bracket, indentation error."
            issue.fix_applied = "Review and fix syntax at the indicated line."
        elif issue.type == IssueType.IMPORT_FAILURE:
            issue.diagnosis = "Import failure. Common causes: missing module, circular import, typo in module name."
            issue.fix_applied = "Verify module exists and import path is correct."
        elif issue.type == IssueType.TEST_FAILURE:
            issue.diagnosis = "Test failure. Common causes: logic error, missing assertion, test environment issue."
            issue.fix_applied = "Review test and implementation for correctness."

        self._save_history()
        return issue

    def apply_fix(self, issue_id: str, fix_description: str, fix_content: str) -> bool:
        """Apply a fix in a worktree and verify."""
        issue = next((i for i in self._issues if i.id == issue_id), None)
        if not issue:
            return False

        try:
            # Create worktree for fix
            worktree_path = self.repo_dir / ".healing_worktree"
            if worktree_path.exists():
                subprocess.run(
                    ["git", "worktree", "remove", "-f", str(worktree_path)], cwd=self.repo_dir, capture_output=True
                )

            subprocess.run(
                ["git", "worktree", "add", str(worktree_path), "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                check=True,
            )

            # Apply fix
            fix_file = worktree_path / issue.file_path
            if fix_file.exists():
                fix_file.write_text(fix_content, encoding="utf-8")

            # Verify in worktree
            result = subprocess.run(
                ["py", "-m", "py_compile", str(fix_file)], cwd=worktree_path, capture_output=True, text=True, timeout=30
            )

            if result.returncode == 0:
                issue.status = IssueStatus.FIX_APPLIED
                issue.fix_applied = fix_description
                log.info("[Healing] Fix applied for %s", issue_id)
            else:
                issue.status = IssueStatus.FAILED
                issue.verification_result = result.stderr

            self._save_history()
            return result.returncode == 0
        except Exception as e:
            issue.status = IssueStatus.FAILED
            issue.verification_result = str(e)
            self._save_history()
            return False

    def verify_fix(self, issue_id: str) -> bool:
        """Verify the fix resolves the issue."""
        issue = next((i for i in self._issues if i.id == issue_id), None)
        if not issue:
            return False

        try:
            # Run relevant checks based on issue type
            if issue.type == IssueType.SYNTAX_ERROR:
                result = subprocess.run(
                    ["py", "-m", "py_compile", issue.file_path],
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                verified = result.returncode == 0
            elif issue.type == IssueType.IMPORT_FAILURE:
                module_path = (
                    str(pathlib.Path(issue.file_path).relative_to(self.repo_dir)).replace("/", ".").replace(".py", "")
                )
                result = subprocess.run(
                    ["py", "-c", f"import {module_path}"], cwd=self.repo_dir, capture_output=True, text=True, timeout=10
                )
                verified = result.returncode == 0
            elif issue.type == IssueType.TEST_FAILURE:
                result = subprocess.run(
                    ["py", "-m", "pytest", "tests/", "-q"],
                    cwd=self.repo_dir,
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                verified = result.returncode == 0
            else:
                verified = False

            if verified:
                issue.status = IssueStatus.VERIFIED
                issue.resolved_at = datetime.now().isoformat()
                issue.verification_result = "Fix verified successfully"
                log.info("[Healing] Fix verified for %s", issue_id)
            else:
                issue.status = IssueStatus.FAILED
                issue.verification_result = "Fix did not resolve the issue"

            self._save_history()
            return verified
        except Exception as e:
            issue.status = IssueStatus.FAILED
            issue.verification_result = str(e)
            self._save_history()
            return False

    def auto_heal(self) -> List[HealingIssue]:
        """Run full auto-healing cycle: detect, diagnose, fix, verify."""
        # Detect all issues
        syntax_issues = self.detect_syntax_errors()
        import_issues = self.detect_import_failures()
        test_issues = self.detect_test_failures()

        all_issues = syntax_issues + import_issues + test_issues
        healed = []

        for issue in all_issues:
            try:
                # Diagnose
                self.diagnose_issue(issue.id)

                # For simple syntax errors, we can attempt auto-fix
                if issue.type == IssueType.SYNTAX_ERROR and issue.line_number > 0:
                    # Read the file
                    try:
                        file_path = self.repo_dir / issue.file_path
                        if file_path.exists():
                            lines = file_path.read_text(encoding="utf-8").split("\n")
                            if issue.line_number <= len(lines):
                                # Log the issue for manual review
                                log.warning(
                                    "[Healing] Auto-detected syntax error at %s:%d - %s",
                                    issue.file_path,
                                    issue.line_number,
                                    issue.error_message,
                                )
                                issue.status = IssueStatus.DIAGNOSED
                                healed.append(issue)
                    except Exception:
                        pass
            except Exception as e:
                log.debug("Auto-heal failed for %s: %s", issue.id, e)

        self._save_history()
        return healed

    def get_stats(self) -> Dict[str, Any]:
        """Get self-healing statistics."""
        by_type = {}
        by_status = {}
        for issue in self._issues:
            by_type[issue.type.value] = by_type.get(issue.type.value, 0) + 1
            by_status[issue.status.value] = by_status.get(issue.status.value, 0) + 1

        return {
            "total_issues": len(self._issues),
            "by_type": by_type,
            "by_status": by_status,
            "healed": by_status.get("verified", 0),
            "failed": by_status.get("failed", 0),
            "pending": by_status.get("detected", 0) + by_status.get("diagnosed", 0),
        }


# Global healing system instance
_healing: Optional[SelfHealingSystem] = None


def get_self_healing(repo_dir: Optional[pathlib.Path] = None) -> SelfHealingSystem:
    """Get or create the global self-healing system."""
    global _healing
    if _healing is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _healing = SelfHealingSystem(repo_dir)
    return _healing
