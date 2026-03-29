"""
Supervisor watchdog - background health monitoring for Ouroboros.
Automatically detects and fixes common infrastructure issues.
"""

import os
import time
import logging
import threading
import json
import pathlib
import datetime
from typing import Optional, Dict, Any, List

from supervisor.state import load_state, save_state
from supervisor.git_ops import get_current_sha
from supervisor.sys_ops import safe_replace
from supervisor.health_reporter import HealthReporter
from ouroboros.experience_indexer import ExperienceIndexer

log = logging.getLogger(__name__)


class InfrastructureWatchdog:
    def __init__(self, drive_root: pathlib.Path, repo_dir: pathlib.Path, check_interval: int = 300):
        self.drive_root = drive_root
        self.repo_dir = repo_dir
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self._indexer = ExperienceIndexer(drive_root)
        self._reporter = HealthReporter(drive_root)

    def start(self):
        """Start the watchdog in a background thread."""
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="jo-watchdog", daemon=True)
        self._thread.start()
        log.info("Infrastructure watchdog started (interval=%ds)", self.check_interval)

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        while not self._stop_event.is_set():
            try:
                self.perform_health_check()
            except Exception as e:
                log.error("Watchdog health check failed: %s", e, exc_info=True)
            self._stop_event.wait(self.check_interval)

    def perform_health_check(self):
        """Analyze system state and auto-fix drift."""
        log.debug("Watchdog: performing health check...")

        # 1. State integrity check
        try:
            st = load_state()
            # Basic sanity check
            if "owner_id" not in st:
                log.warning("Watchdog: owner_id missing from state. Restoring from last good...")
                self._restore_from_last_good()
        except Exception as e:
            log.error("Watchdog: state load failure: %s. Attempting restore...", e)
            self._restore_from_last_good()

        # 2. Git SHA drift detection
        expected_sha = os.environ.get("OUROBOROS_EXPECTED_SHA")
        if expected_sha:
            current_sha = get_current_sha(self.repo_dir)
            if current_sha and current_sha != expected_sha:
                log.warning("Watchdog: git drift detected! Expected %s, observed %s", expected_sha[:8], current_sha[:8])
                # Note: we don't auto-restart here (loop.py handles that if it checks expected_sha)
                # But we log it for the supervisor to see.

        # 3. Experience Indexing
        try:
            self._indexer.rebuild()
        except Exception as e:
            log.error("Watchdog: background indexing failed: %s", e)

        # 4. Task Monitoring (detect stuck workers)
        try:
            self._monitor_tasks(st)
        except Exception as e:
            log.error("Watchdog: task monitoring failed: %s", e)

        # 5. Storage Cleanup
        try:
            self._cleanup_storage()
        except Exception as e:
            log.error("Watchdog: storage cleanup failed: %s", e)

        # 6. Periodic Heartbeat
        try:
            heartbeat = self._reporter.generate_heartbeat()
            log.info("Watchdog Heartbeat:\n%s", heartbeat)
        except Exception as e:
            log.error("Watchdog: heartbeat generation failed: %s", e)

        # 6. Budget reporting
        # (Reserved for future periodic budget notifications if chat is quiet)

        log.debug("Watchdog check complete.")

    def _monitor_tasks(self, state: Dict[str, Any]):
        """Check for workers that haven't made progress in > 2 hours."""
        running = state.get("running_tasks", {})
        now = time.time()
        for task_id, info in running.items():
            start_ts = info.get("start_ts")
            if start_ts:
                # Convert ISO string or use timestamp
                try:
                    dt = datetime.datetime.fromisoformat(start_ts.replace("Z", "+00:00"))
                    elapsed = (datetime.datetime.now(datetime.timezone.utc) - dt).total_seconds()
                    if elapsed > 7200:  # 2 hours
                        log.warning("Watchdog: Task %s likely stuck (running for %.1fh)", task_id, elapsed / 3600)
                        # Future: auto-restart stuck worker could be added here
                except (ValueError, TypeError) as e:
                    log.debug("Failed to parse task timestamp: %s", e)
                    continue

    def _cleanup_storage(self):
        """Delete old /tmp files and rotate logs if too large."""
        # 1. /tmp cleanup
        tmp_dir = self.drive_root / "tmp"
        if tmp_dir.exists():
            now = time.time()
            for f in tmp_dir.iterdir():
                if f.is_file() and (now - f.stat().st_mtime) > 259200:  # 3 days
                    try:
                        f.unlink()
                        log.info("Watchdog: cleaned up old tmp file %s", f.name)
                    except (OSError, PermissionError) as e:
                        log.debug("Failed to clean up tmp file: %s", e)

        # 2. Log rotation (basic)
        events_path = self.drive_root / "logs" / "events.jsonl"
        if events_path.exists() and events_path.stat().st_size > 10 * 1024 * 1024:  # 10MB
            log.info("Watchdog: rotating events.jsonl (size > 10MB)")
            backup_path = events_path.with_suffix(".jsonl.old")
            try:
                # Naive rotation: just keep one backup
                safe_replace(events_path, backup_path)
            except (OSError, IOError) as e:
                log.warning("Failed to rotate events.jsonl: %s", e)

    def _restore_from_last_good(self):
        last_good_path = self.drive_root / "state" / "state.last_good.json"
        if last_good_path.exists():
            try:
                with open(last_good_path, "r") as f:
                    good_st = json.load(f)
                save_state(good_st)
                log.info("Watchdog: successfully restored state from state.last_good.json")
            except Exception as e:
                log.error("Watchdog: critical failure - could not restore from last good state: %s", e)
