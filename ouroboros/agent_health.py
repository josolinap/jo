"""System health verification for agent startup.

Extracted from agent.py (Principle 5: Minimalism).
Handles: restart verification, uncommitted changes, version sync, budget checks.
"""

from __future__ import annotations

import json
import logging
import os
import re
import subprocess
from typing import Any, Dict, Tuple

import pathlib

from ouroboros.utils import read_text, append_jsonl, utc_now_iso

log = logging.getLogger(__name__)


class SystemVerifier:
    """Handles all startup health checks for the agent."""

    def __init__(self, env: Any) -> None:
        self.env = env

    def verify_restart(self, git_sha: str) -> None:
        """Best-effort restart verification."""
        try:
            pending_path = self.env.drive_path("state") / "pending_restart_verify.json"
            claim_path = pending_path.with_name(f"pending_restart_verify.claimed.{os.getpid()}.json")
            try:
                os.rename(str(pending_path), str(claim_path))
            except (FileNotFoundError, Exception):
                return
            try:
                claim_data = json.loads(read_text(claim_path))
                expected_sha = str(claim_data.get("expected_sha", "")).strip()
                ok = bool(expected_sha and expected_sha == git_sha)
                append_jsonl(
                    self.env.drive_path("logs") / "events.jsonl",
                    {
                        "ts": utc_now_iso(),
                        "type": "restart_verify",
                        "pid": os.getpid(),
                        "ok": ok,
                        "expected_sha": expected_sha,
                        "observed_sha": git_sha,
                    },
                )
            except Exception:
                log.debug("Failed to log restart verify event", exc_info=True)
            try:
                claim_path.unlink()
            except Exception:
                log.debug("Failed to delete restart verify claim file", exc_info=True)
        except Exception:
            log.debug("Restart verification failed", exc_info=True)

    def verify_system_state(self, git_sha: str) -> None:
        """Bible Principle 1: verify system state on every startup.

        Checks:
        - Uncommitted changes (auto-rescue commit & push)
        - VERSION file sync with git tags
        - Budget remaining (warning thresholds)
        """
        checks: Dict[str, Any] = {}
        issues = 0
        drive_logs = self.env.drive_path("logs")

        # 1. Uncommitted changes
        checks["uncommitted_changes"], issue_count = self._check_uncommitted_changes()
        issues += issue_count

        # 2. VERSION vs git tag
        checks["version_sync"], issue_count = self._check_version_sync()
        issues += issue_count

        # 3. Budget check
        checks["budget"], issue_count = self._check_budget()
        issues += issue_count

        # Log verification result
        event = {
            "ts": utc_now_iso(),
            "type": "startup_verification",
            "checks": checks,
            "issues_count": issues,
            "git_sha": git_sha,
        }
        append_jsonl(drive_logs / "events.jsonl", event)

        if issues > 0:
            log.warning(f"Startup verification found {issues} issue(s): {checks}")

    def _check_uncommitted_changes(self) -> Tuple[dict, int]:
        """Check for uncommitted changes and attempt auto-rescue commit & push."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.env.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            dirty_files = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            # Filter out noise: tilde files, backup files, temp files
            dirty_files = [
                f for f in dirty_files if not (f.startswith("?? ~") or f.startswith("?? .") or "~" in f or ".tmp" in f)
            ]
            if dirty_files:
                # Auto-rescue: commit and push
                auto_committed = False
                try:
                    # Remove stale git index.lock from previous crashed operations
                    index_lock = self.env.repo_dir / ".git" / "index.lock"
                    if index_lock.exists():
                        index_lock.unlink(missing_ok=True)
                    # Only stage specific modified tracked files (not all with -u)
                    files_to_stage = []
                    for f in dirty_files:
                        status = f[:2] if len(f) >= 2 else ""
                        if status in (" M", "M ", "MM"):
                            path = f[3:].strip() if len(f) > 3 else ""
                            if path:
                                files_to_stage.append(path)
                    if not files_to_stage:
                        return {"dirty_files": dirty_files, "auto_committed": False, "issues": len(dirty_files)}
                    for fpath in files_to_stage:
                        subprocess.run(
                            ["git", "add", fpath],
                            cwd=str(self.env.repo_dir),
                            timeout=10,
                            check=True,
                        )
                    subprocess.run(
                        ["git", "commit", "-m", "auto-rescue: uncommitted changes detected on startup"],
                        cwd=str(self.env.repo_dir),
                        timeout=30,
                        check=True,
                    )
                    # Validate branch name
                    if not re.match(r"^[a-zA-Z0-9_/-]+$", self.env.branch_dev):
                        raise ValueError(f"Invalid branch name: {self.env.branch_dev}")
                    # Pull with rebase before push
                    subprocess.run(
                        ["git", "pull", "--rebase", "origin", self.env.branch_dev],
                        cwd=str(self.env.repo_dir),
                        timeout=60,
                        check=True,
                    )
                    # Push
                    try:
                        subprocess.run(
                            ["git", "push", "origin", self.env.branch_dev],
                            cwd=str(self.env.repo_dir),
                            timeout=60,
                            check=True,
                        )
                        auto_committed = True
                        log.warning(f"Auto-rescued {len(dirty_files)} uncommitted files on startup")
                    except subprocess.CalledProcessError:
                        # If push fails, undo the commit
                        subprocess.run(["git", "reset", "HEAD~1"], cwd=str(self.env.repo_dir), timeout=10, check=True)
                        raise
                except Exception as e:
                    log.warning(f"Failed to auto-rescue uncommitted changes: {e}", exc_info=True)
                return {
                    "status": "warning",
                    "files": dirty_files[:20],
                    "auto_committed": auto_committed,
                }, 1
            else:
                return {"status": "ok"}, 0
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0

    def _check_version_sync(self) -> Tuple[dict, int]:
        """Check VERSION file sync with git tags and pyproject.toml."""
        try:
            version_file = read_text(self.env.repo_path("VERSION")).strip()
            issue_count = 0
            result_data: Dict[str, Any] = {"version_file": version_file}

            # Check pyproject.toml version
            pyproject_path = self.env.repo_path("pyproject.toml")
            pyproject_content = read_text(pyproject_path)
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject_content, re.MULTILINE)
            if match:
                pyproject_version = match.group(1)
                result_data["pyproject_version"] = pyproject_version
                if version_file != pyproject_version:
                    result_data["status"] = "warning"
                    issue_count += 1

            # Check README.md version (Bible P7: VERSION == README version)
            try:
                readme_content = read_text(self.env.repo_path("README.md"))
                readme_match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", readme_content)
                if readme_match:
                    readme_version = readme_match.group(1)
                    result_data["readme_version"] = readme_version
                    if version_file != readme_version:
                        result_data["status"] = "warning"
                        issue_count += 1
            except Exception:
                log.debug("Failed to check README.md version", exc_info=True)

            # Check git tags
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(self.env.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                result_data["status"] = "warning"
                result_data["message"] = "no_tags"
                return result_data, issue_count
            else:
                latest_tag = result.stdout.strip().lstrip("v")
                result_data["latest_tag"] = latest_tag
                if version_file != latest_tag:
                    result_data["status"] = "warning"
                    issue_count += 1

            if issue_count == 0:
                result_data["status"] = "ok"

            return result_data, issue_count
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0

    def _check_budget(self) -> Tuple[dict, int]:
        """Check budget remaining with warning thresholds."""
        try:
            state_path = self.env.drive_path("state") / "state.json"
            state_data = json.loads(read_text(state_path))
            total_budget_str = os.environ.get("TOTAL_BUDGET", "")

            # Handle unset or zero budget gracefully
            if not total_budget_str or float(total_budget_str) == 0:
                return {"status": "unconfigured"}, 0
            else:
                total_budget = float(total_budget_str)
                spent = float(state_data.get("spent_usd", 0))
                remaining = max(0, total_budget - spent)

                if remaining < 10:
                    status = "emergency"
                    issues = 1
                elif remaining < 50:
                    status = "critical"
                    issues = 1
                elif remaining < 100:
                    status = "warning"
                    issues = 0
                else:
                    status = "ok"
                    issues = 0

                return {
                    "status": status,
                    "remaining_usd": round(remaining, 2),
                    "total_usd": total_budget,
                    "spent_usd": round(spent, 2),
                }, issues
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0
