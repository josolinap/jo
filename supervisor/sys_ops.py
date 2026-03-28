"""
OS-agnostic system operations for Ouroboros.
Consolidates Windows/Unix differences for file operations, shell execution, and restarts.
"""

import os
import sys
import logging
import pathlib
import subprocess
from typing import List, Optional, Tuple, Union

log = logging.getLogger(__name__)

def safe_replace(src: Union[str, pathlib.Path], dst: Union[str, pathlib.Path]) -> None:
    """Atomic replacement of dst with src. Handles Windows 'FileExistsError'."""
    src = str(src)
    dst = str(dst)
    try:
        os.replace(src, dst)
    except Exception as e:
        log.error(f"Failed to replace {dst} with {src}: {e}")
        raise

def run_shell_command(cmd_args: List[str], cwd: Optional[pathlib.Path] = None, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a shell command consistently across platforms."""
    is_windows = sys.platform == "win32"
    
    # On Windows, we often need shell=True for glob expansion or built-in commands
    # But shell=True prefers a single string command on Windows.
    if is_windows:
        # Join args into a single string if they aren't already
        full_cmd = " ".join(f'"{a}"' if " " in a else a for a in cmd_args)
        return subprocess.run(
            full_cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout
        )
    else:
        # Standard Unix behavior: shell=False with list is safer and better
        return subprocess.run(
            cmd_args,
            shell=False,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout
        )

def get_platform_info() -> dict:
    return {
        "os": sys.platform,
        "is_windows": sys.platform == "win32",
        "python_version": sys.version,
        "cwd": os.getcwd()
    }
