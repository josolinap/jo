"""
Unit tests for the Git race-condition fixes.

Tests:
  - get_current_sha() returns a non-empty SHA or empty string (never raises)
  - safe_pull() returns bool and doesn't raise
  - load_state() SHA reconciliation path (mocked git + state)
  - SHA watchdog is inactive when OUROBOROS_EXPECTED_SHA is not set
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Tests for supervisor.git_ops
# ---------------------------------------------------------------------------


class TestGetCurrentSha(unittest.TestCase):
    """get_current_sha() must never raise and returns str."""

    def test_returns_string(self):
        from supervisor.git_ops import get_current_sha

        result = get_current_sha()
        self.assertIsInstance(result, str)

    def test_valid_sha_in_real_repo(self):
        """If we're inside a git repo, we should get a 40-char hex SHA."""
        from supervisor.git_ops import get_current_sha

        repo_root = pathlib.Path(__file__).parent.parent
        if not (repo_root / ".git").exists():
            self.skipTest("Not inside a git repo")
        sha = get_current_sha(repo_root)
        self.assertEqual(len(sha), 40, f"Expected 40-char SHA, got: {sha!r}")
        self.assertTrue(all(c in "0123456789abcdef" for c in sha))

    def test_non_repo_dir_returns_empty(self):
        """A non-git dir should return '' not raise."""
        from supervisor.git_ops import get_current_sha

        with tempfile.TemporaryDirectory() as d:
            result = get_current_sha(pathlib.Path(d))
        self.assertEqual(result, "")

    def test_missing_dir_returns_empty(self):
        """A missing dir should return '' (git error), not raise."""
        from supervisor.git_ops import get_current_sha

        result = get_current_sha(pathlib.Path("/nonexistent/path/xyz"))
        self.assertEqual(result, "")


class TestSafePull(unittest.TestCase):
    """safe_pull() must return bool and never raise."""

    def test_returns_bool(self):
        from supervisor.git_ops import safe_pull

        # Will fail because default REPO_DIR doesn't exist in test env, but
        # it must return False cleanly instead of raising.
        with tempfile.TemporaryDirectory() as d:
            result = safe_pull("dev", pathlib.Path(d))
        self.assertIsInstance(result, bool)

    def test_rebase_success_path(self):
        """Mock a successful rebase — should return True."""
        from supervisor.git_ops import safe_pull
        import pathlib

        mock_result = MagicMock()
        mock_result.returncode = 0
        with patch("subprocess.run", return_value=mock_result):
            result = safe_pull("dev", pathlib.Path("/fake"))
        self.assertTrue(result)

    def test_rebase_fail_then_hard_reset_success(self):
        """Mock rebase failure + successful hard reset — should return True."""
        from supervisor.git_ops import safe_pull

        fail = MagicMock()
        fail.returncode = 1
        fail.stderr = "CONFLICT"
        ok = MagicMock()
        ok.returncode = 0

        # Calls in order: pull --rebase (fail), rebase --abort (ok),
        # fetch (ok), reset --hard (ok)
        with patch("subprocess.run", side_effect=[fail, ok, ok, ok]):
            result = safe_pull("dev", pathlib.Path("/fake"))
        self.assertTrue(result)

    def test_hard_reset_also_fails_returns_false(self):
        """When both rebase and hard reset fail, return False."""
        from supervisor.git_ops import safe_pull
        import subprocess

        fail = MagicMock()
        fail.returncode = 1
        fail.stderr = "CONFLICT"
        ok = MagicMock()
        ok.returncode = 0

        def side_effect(*args, **kwargs):
            # pull --rebase: fail; abort: ok; fetch: raise
            cmd = args[0] if args else []
            if "fetch" in cmd:
                raise subprocess.CalledProcessError(1, cmd)
            if "--abort" in cmd:
                return ok
            return fail

        with patch("subprocess.run", side_effect=side_effect):
            result = safe_pull("dev", pathlib.Path("/fake"))
        self.assertFalse(result)


# ---------------------------------------------------------------------------
# Tests for SHA watchdog (agent.py)
# ---------------------------------------------------------------------------


class TestShaWatchdog(unittest.TestCase):
    """_start_sha_watchdog() is a no-op when env var is not set."""

    def test_watchdog_inactive_without_env_var(self):
        """When OUROBOROS_EXPECTED_SHA is unset, no watchdog thread starts."""
        env_backup = os.environ.pop("OUROBOROS_EXPECTED_SHA", None)
        try:
            threads_before = {t.name for t in threading.enumerate()}

            # Build a minimal mock agent just to call _start_sha_watchdog
            from ouroboros.agent import OuroborosAgent, Env
            import queue as _queue

            with tempfile.TemporaryDirectory() as d:
                env = Env(
                    repo_dir=pathlib.Path(d),
                    drive_root=pathlib.Path(d),
                )
                # Patch __init__ heavy operations
                with patch.object(OuroborosAgent, "__init__", lambda self, *a, **kw: None):
                    agent = OuroborosAgent.__new__(OuroborosAgent)
                    agent.env = env
                    agent._start_hot_reload_manager()

            threads_after = {t.name for t in threading.enumerate()}
            self.assertNotIn("hot-reload-manager", threads_after - threads_before)
        finally:
            if env_backup is not None:
                os.environ["OUROBOROS_EXPECTED_SHA"] = env_backup

    def test_watchdog_starts_with_env_var(self):
        """When OUROBOROS_EXPECTED_SHA is set, the watchdog thread starts."""
        os.environ["OUROBOROS_EXPECTED_SHA"] = "a" * 40
        try:
            from ouroboros.agent import OuroborosAgent, Env

            with tempfile.TemporaryDirectory() as d:
                env = Env(
                    repo_dir=pathlib.Path(d),
                    drive_root=pathlib.Path(d),
                )
                with patch.object(OuroborosAgent, "__init__", lambda self, *a, **kw: None):
                    agent = OuroborosAgent.__new__(OuroborosAgent)
                    agent.env = env
                    agent._start_hot_reload_manager(check_interval=9999)  # long interval — won't fire

            # Thread should now exist
            names = {t.name for t in threading.enumerate()}
            self.assertIn("hot-reload-manager", names)
        finally:
            os.environ.pop("OUROBOROS_EXPECTED_SHA", None)


if __name__ == "__main__":
    unittest.main()
