"""
Hot Reload Manager - Smart restart detection and module reloading.

Monitors for code changes and can either:
1. Hot reload changed modules (no restart, preserve context)
2. Notify model of vault/doc changes (no reload needed)
3. Full restart when runtime code changes

This enables Jo to update vault notes without losing context.
"""

from __future__ import annotations

import logging
import subprocess
import threading
import time
from pathlib import Path
from typing import Callable, Optional, Set

log = logging.getLogger(__name__)

# Files/directories that DON'T need a restart
SOFT_RELOAD_DIRS: Set[str] = {
    "vault/",
    "memory/",
    "docs/",
    "prompts/",
    "config/",
    "README.md",
    ".github/",
    ".gitignore",
    ".githooks/",
}

# Files/directories that DO need restart/reload
HARD_RELOAD_FILES: Set[str] = {
    "ouroboros/",
    "supervisor/",
}


def get_changed_files_since_sha(repo_dir: Path, since_sha: str) -> list[str]:
    """Get list of files changed since a given SHA."""
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", since_sha, "HEAD"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception as e:
        log.debug(f"Failed to get changed files: {e}")
    return []


def classify_changes(changed_files: list[str]) -> tuple[list[str], list[str], bool]:
    """Classify changes into categories.

    Returns:
        (soft_changes, hard_changes, needs_restart)
    """
    soft_changes = []
    hard_changes = []

    for f in changed_files:
        is_soft = any(f.startswith(d) or f == d for d in SOFT_RELOAD_DIRS)
        if is_soft:
            soft_changes.append(f)
        else:
            hard_changes.append(f)

    # Restart needed if there are hard changes (code changes)
    needs_restart = len(hard_changes) > 0

    return soft_changes, hard_changes, needs_restart


def notify_model_of_changes(soft_changes: list[str]) -> str:
    """Generate notification message for vault/doc changes."""
    if not soft_changes:
        return ""

    vault_changes = [f for f in soft_changes if f.startswith("vault/")]
    memory_changes = [f for f in soft_changes if f.startswith("memory/")]
    doc_changes = [f for f in soft_changes if f.startswith("docs/") or f.endswith(".md")]

    lines = []
    if vault_changes:
        count = len(set(vault_changes))
        lines.append(f"Vault updated: {count} file(s) changed")

    if memory_changes:
        count = len(set(memory_changes))
        lines.append(f"Memory updated: {count} file(s) changed")

    if doc_changes:
        count = len(set(doc_changes))
        lines.append(f"Docs updated: {count} file(s) changed")

    return " | ".join(lines) if lines else ""


class HotReloadManager:
    """Manages smart reload detection for Jo's workers."""

    def __init__(
        self,
        repo_dir: Path,
        drive_root: Path,
        initial_sha: str,
        check_interval: int = 30,
        on_vault_change: Optional[Callable[[str], None]] = None,
        on_code_change: Optional[Callable[[list[str]], None]] = None,
    ):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self.initial_sha = initial_sha
        self.check_interval = check_interval
        self.on_vault_change = on_vault_change
        self.on_code_change = on_code_change
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Start the hot reload manager."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="hot-reload-manager")
        self._thread.start()
        log.debug("Hot reload manager started (initial_sha=%s)", self.initial_sha[:8])

    def stop(self) -> None:
        """Stop the hot reload manager."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
            self._thread = None

    def check_for_changes(self) -> tuple[bool, bool, str]:
        """Manually check for changes.

        Returns:
            (has_changes, needs_restart, notification_message)
        """
        changed_files = get_changed_files_since_sha(self.repo_dir, self.initial_sha)
        if not changed_files:
            return False, False, ""

        soft, hard, needs_restart = classify_changes(changed_files)
        notification = notify_model_of_changes(soft)

        return True, needs_restart, notification

    def _run(self) -> None:
        """Run the hot reload check loop."""
        while self._running:
            time.sleep(self.check_interval)

            try:
                result = subprocess.run(
                    ["git", "rev-parse", "HEAD"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                current_sha = result.stdout.strip() if result.returncode == 0 else ""
            except Exception:
                continue

            if not current_sha or current_sha == self.initial_sha:
                continue

            # SHA changed - classify the changes
            changed_files = get_changed_files_since_sha(self.repo_dir, self.initial_sha)
            soft, hard, needs_restart = classify_changes(changed_files)

            log.info(
                "Code change detected: %d soft, %d hard files. Restart: %s",
                len(soft),
                len(hard),
                needs_restart,
            )

            if needs_restart:
                # Full restart needed for code changes
                self._exit_for_restart(current_sha, hard)
            elif soft:
                # Reload config if config files changed
                config_changes = [f for f in soft if f.startswith("config/")]
                if config_changes:
                    try:
                        from ouroboros.config_manager import get_config_manager

                        cm = get_config_manager(self.repo_dir)
                        if cm.reload_if_changed():
                            log.info("Configuration reloaded after config file changes")
                            if self.on_vault_change:
                                self.on_vault_change("Configuration reloaded")
                    except Exception as e:
                        log.debug("Config reload failed: %s", e)

                # Notify about vault/doc changes
                notification = notify_model_of_changes(soft)
                if notification and self.on_vault_change:
                    try:
                        self.on_vault_change(notification)
                    except Exception as e:
                        log.debug(f"Vault change notification failed: {e}")

                # Update the initial_sha to ignore these changes
                # This prevents repeated notifications
                self.initial_sha = current_sha

    def _exit_for_restart(self, new_sha: str, changed_files: list[str]) -> None:
        """Exit worker for clean restart when code changes."""
        self._running = False

        # CRITICAL: Save any uncommitted work before exiting
        self._save_uncommitted_work()

        try:
            from supervisor.state import append_jsonl
            from ouroboros.utils import utc_now_iso

            append_jsonl(
                self.drive_root / "logs" / "events.jsonl",
                {
                    "ts": utc_now_iso(),
                    "type": "worker_code_change_restart",
                    "initial_sha": self.initial_sha[:8],
                    "new_sha": new_sha[:8],
                    "changed_files": changed_files[:20],
                },
            )
        except Exception:
            log.debug("Unexpected error", exc_info=True)

        log.warning(
            "Code changed (SHA %s -> %s) — %d files changed. Exiting for clean respawn.",
            self.initial_sha[:8],
            new_sha[:8],
            len(changed_files),
        )

        if self.on_code_change:
            try:
                self.on_code_change(changed_files)
            except Exception:
                log.debug("Unexpected error", exc_info=True)

        import os

        os._exit(1)

    def _save_uncommitted_work(self) -> None:
        """Save any uncommitted work before restart - CRITICAL to prevent data loss.

        Checks for uncommitted changes and attempts to rescue them:
        1. Vault changes → commit and push
        2. Other uncommitted work → notify and warn
        """
        import subprocess

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            dirty_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]

            if not dirty_files:
                return  # Nothing to save

            # Separate vault changes from other changes
            vault_changes = [
                f
                for f in dirty_files
                if "vault/" in f and (f.startswith("??") or f.startswith(" M") or f.startswith("M "))
            ]

            # Try to rescue vault changes (most important)
            for f in dirty_files:
                path = f.strip()[3:].strip() if len(f) > 3 else ""
                if path.startswith("vault/") or path.startswith("memory/"):
                    try:
                        # Add specific file
                        subprocess.run(
                            ["git", "add", path],
                            cwd=str(self.repo_dir),
                            timeout=10,
                            capture_output=True,
                        )
                    except Exception:
                        log.debug("Unexpected error", exc_info=True)

            # Check if anything was staged
            result = subprocess.run(
                ["git", "diff", "--cached", "--name-only"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            staged = result.stdout.strip()

            if staged:
                try:
                    # Commit with descriptive message
                    subprocess.run(
                        ["git", "commit", "-m", "auto-save: uncommitted work rescued before restart"],
                        cwd=str(self.repo_dir),
                        timeout=30,
                        capture_output=True,
                    )
                    # Push immediately
                    subprocess.run(
                        ["git", "push", "origin", "dev"],
                        cwd=str(self.repo_dir),
                        timeout=60,
                        capture_output=True,
                    )
                    log.warning("Rescued uncommitted work before restart: %s", staged[:200])
                except Exception as e:
                    log.error("Failed to rescue uncommitted work: %s", e)
            else:
                log.warning("Uncommitted work detected but not staged: %s", dirty_files[:5])

        except Exception as e:
            log.warning("Failed to check for uncommitted work: %s", e)
