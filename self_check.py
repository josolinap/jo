#!/usr/bin/env python3
"""
Self-check script for Jo autonomous health monitoring.
Can run without ToolContext - uses basic Python only.

Usage:
    python self_check.py
"""

from __future__ import annotations

import json
import pathlib
import subprocess
import sys


def check_git_status() -> dict:
    """Check git working tree status."""
    try:
        repo_dir = pathlib.Path(__file__).parent.resolve()
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        # Filter out untracked files that are just cache/data directories
        changes = result.stdout.strip()
        if changes:
            filtered = []
            for line in changes.split("\n"):
                # Skip .gitignore'd files like .jo_data, __pycache__, etc
                if not any(x in line for x in [".jo_data", "__pycache__", ".pytest_cache", "self_check.py"]):
                    filtered.append(line)
            changes = "\n".join(filtered) if filtered else ""

        return {
            "clean": result.returncode == 0 and changes == "",
            "changes": changes[:500] if changes else "",
        }
    except Exception as e:
        return {"clean": None, "error": str(e)}


def check_git_diff() -> dict:
    """Check for uncommitted changes."""
    try:
        repo_dir = pathlib.Path(__file__).parent.resolve()
        result = subprocess.run(
            ["git", "diff", "--stat"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return {
            "has_changes": result.returncode == 0 and result.stdout.strip() != "",
            "stat": result.stdout.strip()[:200] if result.stdout else "",
        }
    except Exception as e:
        return {"has_changes": None, "error": str(e)}


def check_version() -> dict:
    """Check version file."""
    try:
        version_file = pathlib.Path(__file__).parent / "VERSION"
        if version_file.exists():
            version = version_file.read_text().strip()
            return {"version": version, "consistent": True}
        return {"version": None, "error": "VERSION file not found"}
    except Exception as e:
        return {"version": None, "error": str(e)}


def check_python_syntax() -> dict:
    """Check Python files for syntax errors."""
    errors = []
    python_files = list(pathlib.Path("ouroboros").rglob("*.py"))

    for f in python_files[:20]:  # Limit to 20 files for speed
        try:
            result = subprocess.run(
                [sys.executable, "-m", "py_compile", str(f)],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                errors.append(f"{f}: {result.stderr[:100]}")
        except Exception:
            pass

    return {"errors": errors[:5], "total_checked": min(20, len(python_files))}


def check_requirements() -> dict:
    """Check if requirements.txt is satisfied."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "check"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return {
            "satisfied": result.returncode == 0,
            "issues": result.stdout.strip()[:200] if result.stdout else "",
        }
    except Exception as e:
        return {"satisfied": None, "error": str(e)}


def check_data_dir() -> dict:
    """Check Jo's data directory."""
    import os

    home = pathlib.Path.home()
    data_root = pathlib.Path(os.environ.get("DATA_ROOT", home / ".jo_data"))

    if not data_root.exists():
        return {"exists": False}

    subdirs = ["state", "logs", "memory", "locks"]
    status = {}
    for sub in subdirs:
        path = data_root / sub
        status[sub] = path.exists() and path.is_dir()

    return {"exists": True, "subdirs": status}


def run_self_check() -> dict:
    """Run all self-checks and return report."""
    report = {
        "timestamp": subprocess.run(
            ["date", "+%Y-%m-%d %H:%M:%S"],
            capture_output=True,
            text=True,
        ).stdout.strip(),
        "git_status": check_git_status(),
        "git_diff": check_git_diff(),
        "version": check_version(),
        "python_syntax": check_python_syntax(),
        "requirements": check_requirements(),
        "data_dir": check_data_dir(),
    }
    return report


def main():
    """Main entry point."""
    print("[Jo Self-Check]")
    print("=" * 40)

    report = run_self_check()

    print(f"\nTimestamp: {report['timestamp']}")

    # Git Status
    gs = report["git_status"]
    if gs.get("clean"):
        print("[OK] Git: Working tree clean")
    elif gs.get("clean") is False:
        print(f"[WARN] Git: Uncommitted changes: {gs.get('changes', '')[:100]}")
    else:
        print(f"[ERR] Git: Error - {gs.get('error', 'unknown')}")

    # Version
    v = report["version"]
    if v.get("version"):
        print(f"[*] Version: {v['version']}")

    # Python Syntax
    ps = report["python_syntax"]
    if ps.get("errors"):
        print(f"[WARN] Syntax errors in {len(ps['errors'])} files:")
        for e in ps["errors"]:
            print(f"   - {e}")
    else:
        print(f"[OK] Python syntax: OK ({ps['total_checked']} files checked)")

    # Requirements
    r = report["requirements"]
    if r.get("satisfied"):
        print("[OK] Dependencies: All satisfied")
    elif r.get("satisfied") is False:
        print(f"[WARN] Dependencies: {r.get('issues', 'issues found')}")
    else:
        print(f"[ERR] Dependencies: {r.get('error', 'unknown')}")

    # Data Directory
    dd = report["data_dir"]
    if dd.get("exists"):
        print("[OK] Data directory: Exists")
    else:
        print("[WARN] Data directory: Not found (first run?)")

    print("\n" + "=" * 40)

    # Exit code based on health
    has_issues = not gs.get("clean", True) or bool(ps.get("errors")) or not r.get("satisfied", True)

    if has_issues:
        print("[WARN] Issues detected - review recommended")
        return 1
    else:
        print("[OK] All checks passed")
        return 0


if __name__ == "__main__":
    sys.exit(main())
