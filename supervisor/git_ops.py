from __future__ import annotations
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict
import pathlib

REPO_DIR = Path(os.environ.get("OUROBOROS_REPO_DIR", "/content/ouroboros_repo"))


def import_test() -> Dict[str, Any]:
    exe = sys.executable if (isinstance(sys.executable, str) and os.path.isfile(sys.executable)) else "python"

    kwargs: Dict[str, Any] = {
        "cwd": str(REPO_DIR),
        "capture_output": True,
        "text": True,
    }
    if os.name == "nt":
        kwargs["shell"] = True

    try:
        r = subprocess.run([exe, "-c", "import ouroboros, ouroboros.agent; print('import_ok')"], **kwargs)
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


def safe_restart() -> None:
    pass

# Import GitHub API functions from separate module
from .github_api import (
    list_github_issues,
    get_github_issue,
    create_github_issue,
    comment_on_issue,
    close_github_issue,
)