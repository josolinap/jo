from __future__ import annotations
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import pathlib

from supervisor.sys_ops import safe_replace

log = logging.getLogger(__name__)

REPO_DIR = Path(os.environ.get("REPO_DIR", "."))


def import_test() -> Dict[str, Any]:
    import sys
    import os
    import subprocess
    from pathlib import Path

    exe = sys.executable if (isinstance(sys.executable, str) and os.path.isfile(sys.executable)) else "python"

    # On Windows, using shell=True helps with paths containing spaces
    kwargs: Dict[str, Any] = {
        "cwd": str(REPO_DIR),
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }

    if os.name == "nt":
        kwargs["shell"] = True
        # When shell=True, the command must be a string; quote exe to handle spaces
        cmd = f'"{exe}" -c "import ouroboros, ouroboros.agent; print(\'import_ok\')"'
    else:
        # On Unix, we can pass a list (safer)
        cmd = [exe, "-c", "import ouroboros, ouroboros.agent; print('import_ok')"]

    try:
        r = subprocess.run(cmd, **kwargs)
        return {
            "ok": (r.returncode == 0),
            "stdout": r.stdout,
            "stderr": r.stderr,
            "returncode": r.returncode,
        }
    except Exception as e:
        return {
            "ok": False,
            "stdout": "",
            "stderr": f"import_test_exception: {e}",
            "returncode": -1,
        }


def init(
    repo_dir: pathlib.Path,
    drive_root: pathlib.Path,
    remote_url: str,
    branch_dev: str,
    branch_stable: str,
) -> None:
    pass


def ensure_repo_present() -> None:
    pass


def checkout_and_reset(branch: str) -> None:
    pass


def sync_runtime_dependencies() -> None:
    pass


def safe_restart(reason: str = "", unsynced_policy: str = "rescue_and_reset") -> tuple:
    """Pull latest code and prepare for restart. Returns (ok: bool, msg: str)."""
    try:
        # Pull latest from remote
        pull_ok = safe_pull(branch="dev", repo_dir=REPO_DIR)
        if not pull_ok:
            return False, "git pull failed"
        # Run import test to verify code compiles
        result = import_test()
        if not result.get("ok"):
            stderr = str(result.get("stderr", ""))[:200]
            return False, f"import test failed: {stderr}"
        return True, "ok"
    except Exception as e:
        return False, str(e)[:200]


def get_current_sha(repo_dir: Optional[pathlib.Path] = None) -> str:
    """Return the actual git HEAD SHA from disk — no Drive state involved.

    Returns empty string on any error so callers can treat it as "unknown".
    """
    cwd = str(repo_dir or REPO_DIR)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        log.debug("get_current_sha failed: %s", result.stderr.strip())
        return ""
    except Exception as e:
        log.debug("get_current_sha exception: %s", e)
        return ""


def safe_pull(branch: str = "dev", repo_dir: Optional[pathlib.Path] = None) -> bool:
    """Pull latest changes from remote with rebase; hard-reset on conflict.

    Strategy:
      1. Try ``git pull --rebase origin <branch>``.
      2. If rebase fails (merge conflict), abort and hard-reset to the remote
         branch.  Agent code is generated, so hard-reset is almost always
         the correct conflict-resolution policy.

    Returns True if the repo is clean/updated after the call, False on
    unrecoverable errors.
    """
    cwd = str(repo_dir or REPO_DIR)
    try:
        result = subprocess.run(
            ["git", "pull", "--rebase", "origin", branch],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            # Atomic replace via sys_ops
            safe_replace(tmp_path, target_path)
            log.info("Recovery complete: repo state was invalid, restored from head (was on main/detached)")
            return True

        # Rebase failed — abort and fall through to hard reset
        log.warning(
            "safe_pull: rebase failed (branch '%s'), aborting.  stderr=%s",
            branch,
            result.stderr.strip()[:400],
        )
        subprocess.run(
            ["git", "rebase", "--abort"],
            cwd=cwd,
            capture_output=True,
            timeout=30,
        )
    except Exception as e:
        log.warning("safe_pull: pull/rebase raised exception: %s", e)

    # Hard-reset to remote — last resort
    try:
        subprocess.run(
            ["git", "fetch", "origin"],
            cwd=cwd,
            capture_output=True,
            timeout=60,
            check=True,
        )
        subprocess.run(
            ["git", "reset", "--hard", f"origin/{branch}"],
            cwd=cwd,
            capture_output=True,
            timeout=30,
            check=True,
        )
        log.warning(
            "safe_pull: hard-reset to origin/%s — local changes lost (regenerated code).",
            branch,
        )
        return True
    except Exception as e:
        log.error("safe_pull: hard-reset also failed: %s", e)
        return False


# Import GitHub API functions from separate module
from .github_api import (
    list_github_issues,
    get_github_issue,
    create_github_issue,
    comment_on_issue,
    close_github_issue,
)
