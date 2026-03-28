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
from typing import Optional, Dict, Any

from supervisor.state import load_state, save_state
from supervisor.git_ops import get_current_sha

log = logging.getLogger(__name__)

class InfrastructureWatchdog:
    def __init__(self, drive_root: pathlib.Path, repo_dir: pathlib.Path, check_interval: int = 300):
        self.drive_root = drive_root
        self.repo_dir = repo_dir
        self.check_interval = check_interval
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

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

        # 3. Budget reporting
        # (Reserved for future periodic budget notifications if chat is quiet)
        
        log.debug("Watchdog check complete.")

    def _restore_from_last_good(self):
        last_good_path = self.drive_root / "state" / "state.last_good.json"
        if last_good_path.exists():
            try:
                with open(last_good_path, 'r') as f:
                    good_st = json.load(f)
                save_state(good_st)
                log.info("Watchdog: successfully restored state from state.last_good.json")
            except Exception as e:
                log.error("Watchdog: critical failure - could not restore from last good state: %s", e)
