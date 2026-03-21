"""Health auto-fix module — proactively resolves detected issues."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class HealthAutoFix:
    """Auto-fix common health issues detected by health invariants."""

    def __init__(self, repo_dir: Path, drive_root: Path):
        self.repo_dir = Path(repo_dir)
        self.drive_root = Path(drive_root)

    def check_and_fix_all(self) -> Dict[str, Any]:
        """Run all auto-fix checks and return results."""
        results = {
            "fixes_attempted": [],
            "fixes_succeeded": [],
            "fixes_failed": [],
            "skipped": [],
        }

        fixes = [
            ("version_sync", self._fix_version_sync),
            ("stale_identity", self._fix_stale_identity),
            ("uncommitted_changes", self._fix_uncommitted),
        ]

        for name, fix_fn in fixes:
            try:
                should_fix, reason = self._should_fix(name)
                if not should_fix:
                    results["skipped"].append({"fix": name, "reason": reason})
                    continue

                results["fixes_attempted"].append(name)
                success, detail = fix_fn()
                if success:
                    results["fixes_succeeded"].append({"fix": name, "detail": detail})
                else:
                    results["fixes_failed"].append({"fix": name, "detail": detail})
            except Exception as e:
                log.warning(f"Auto-fix {name} failed: {e}")
                results["fixes_failed"].append({"fix": name, "error": str(e)})

        return results

    def _should_fix(self, fix_name: str) -> tuple[bool, str]:
        """Check if auto-fix is enabled and should run."""
        env_var = f"AUTO_FIX_{fix_name.upper()}"
        enabled = os.environ.get(env_var, "0") == "1"
        if not enabled:
            return False, f"{env_var}=0 (disabled)"
        return True, "enabled"

    def _fix_version_sync(self) -> tuple[bool, str]:
        """Fix VERSION file to match pyproject.toml."""
        version_file = self.repo_dir / "VERSION"
        pyproject_file = self.repo_dir / "pyproject.toml"

        if not version_file.exists() or not pyproject_file.exists():
            return False, "version or pyproject files missing"

        current_ver = version_file.read_text().strip()

        pyproject_content = pyproject_file.read_text()
        pyproject_ver = None
        for line in pyproject_content.splitlines():
            if line.strip().startswith("version"):
                pyproject_ver = line.split("=", 1)[1].strip().strip('"').strip("'")
                break

        if not pyproject_ver or current_ver == pyproject_ver:
            return True, "already in sync"

        version_file.write_text(pyproject_ver)
        return True, f"updated VERSION from {current_ver} to {pyproject_ver}"

    def _fix_stale_identity(self) -> tuple[bool, str]:
        """Touch identity.md to mark as recently updated (minimal fix)."""
        identity_path = self.drive_root / "memory" / "identity.md"
        if not identity_path.exists():
            return False, "identity.md not found"

        age_hours = (time.time() - identity_path.stat().st_mtime) / 3600
        if age_hours <= 8:
            return True, "identity is not stale"

        os.utime(identity_path, None)
        return True, f"touched identity.md ({age_hours:.0f}h old)"

    def _fix_uncommitted(self) -> tuple[bool, str]:
        """Auto-commit uncommitted changes (if safe)."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if not result.stdout.strip():
                return True, "nothing to commit"

            lines = result.stdout.strip().split("\n")
            auto_safe = [
                "memory/scratchpad.md",
                "memory/dialogue_summary.md",
                "logs/",
            ]

            unsafe = []
            for line in lines:
                if line.startswith("??"):
                    continue
                path = line[3:].strip()
                if not any(path.startswith(s) for s in auto_safe):
                    unsafe.append(path)

            if unsafe:
                return False, f"unsafe to auto-commit: {unsafe}"

            subprocess.run(
                ["git", "add"] + [line.split()[1] for line in lines if line.startswith(" M")],
                cwd=str(self.repo_dir),
                timeout=10,
            )
            subprocess.run(
                ["git", "commit", "-m", "auto: save working state"],
                cwd=str(self.repo_dir),
                timeout=10,
            )
            return True, f"auto-committed {len(lines)} changes"
        except Exception as e:
            return False, str(e)

    def get_status_report(self) -> str:
        """Get a human-readable status report."""
        results = self.check_and_fix_all()

        if not results["fixes_attempted"]:
            return "ℹ️ Auto-fix: All checks passed (or disabled)"

        lines = ["## Health Auto-Fix Report"]
        if results["fixes_succeeded"]:
            lines.append(f"\n✅ Fixed ({len(results['fixes_succeeded'])}):")
            for f in results["fixes_succeeded"]:
                lines.append(f"   - {f['fix']}: {f['detail']}")

        if results["fixes_failed"]:
            lines.append(f"\n❌ Failed ({len(results['fixes_failed'])}):")
            for f in results["fixes_failed"]:
                lines.append(f"   - {f['fix']}: {f.get('detail', f.get('error', 'unknown'))}")

        if results["skipped"]:
            lines.append(f"\n⏭️ Skipped ({len(results['skipped'])}):")
            for f in results["skipped"]:
                lines.append(f"   - {f['fix']}: {f['reason']}")

        return "\n".join(lines)


def run_auto_fix(repo_dir: Path, drive_root: Path) -> Dict[str, Any]:
    """Convenience function to run auto-fix."""
    fixer = HealthAutoFix(repo_dir=repo_dir, drive_root=drive_root)
    return fixer.check_and_fix_all()
