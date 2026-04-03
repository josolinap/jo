"""Evolution fingerprinting — snapshot state before changes.

Inspired by Lazarus's BatchPlan fingerprinting pattern.
Takes a snapshot of critical files before evolution runs.
If post-evolution state doesn't match expectations, detect drift.

Fingerprints:
- Git SHA
- File hashes for protected files
- Module line counts
- Test pass count
- Tool/skill counts

This lets Jo detect: "Something changed that shouldn't have."
"""

from __future__ import annotations

import hashlib
import json
import logging
import pathlib
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

FINGERPRINT_PATH = "~/.jo_data/evolution_fingerprints.json"


@dataclass
class EvolutionFingerprint:
    """A snapshot of system state before evolution."""

    snapshot_id: str
    timestamp: str
    git_sha: str
    file_hashes: Dict[str, str] = field(default_factory=dict)
    module_line_counts: Dict[str, int] = field(default_factory=dict)
    test_count: int = 0
    tool_count: int = 0
    skill_count: int = 0
    vault_note_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "ts": self.timestamp,
            "git_sha": self.git_sha,
            "file_hashes": self.file_hashes,
            "module_lines": self.module_line_counts,
            "test_count": self.test_count,
            "tool_count": self.tool_count,
            "skill_count": self.skill_count,
            "vault_notes": self.vault_note_count,
        }


class EvolutionFingerprinter:
    """Take and compare evolution fingerprints."""

    def __init__(self, repo_dir: pathlib.Path):
        self._repo_dir = repo_dir
        self._path = pathlib.Path(str(pathlib.Path(FINGERPRINT_PATH).expanduser()))

    def take_snapshot(self) -> EvolutionFingerprint:
        """Take a snapshot of current system state."""
        snapshot_id = f"snap_{int(time.time())}"

        # Git SHA
        git_sha = self._get_git_sha()

        # Protected file hashes
        protected_files = [
            "BIBLE.md",
            "VERSION",
            "pyproject.toml",
            "ouroboros/consciousness.py",
            "ouroboros/evolution_strategy.py",
        ]
        file_hashes = {}
        for f in protected_files:
            path = self._repo_dir / f
            if path.exists():
                file_hashes[f] = self._hash_file(path)

        # Module line counts
        module_lines = {}
        ouroboros_dir = self._repo_dir / "ouroboros"
        if ouroboros_dir.exists():
            for py_file in ouroboros_dir.glob("*.py"):
                try:
                    lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                    module_lines[py_file.name] = lines
                except Exception:
                    pass

        # Test count
        test_count = self._count_tests()

        # Tool/skill counts
        tool_count = self._count_tools()
        skill_count = self._count_skills()
        vault_count = self._count_vault_notes()

        snapshot = EvolutionFingerprint(
            snapshot_id=snapshot_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            git_sha=git_sha,
            file_hashes=file_hashes,
            module_line_counts=module_lines,
            test_count=test_count,
            tool_count=tool_count,
            skill_count=skill_count,
            vault_note_count=vault_count,
        )

        self._save_snapshot(snapshot)
        return snapshot

    def compare_with_current(self, snapshot: EvolutionFingerprint) -> Dict[str, Any]:
        """Compare a snapshot with current state to detect changes."""
        current = self.take_snapshot()
        changes = {
            "git_changed": snapshot.git_sha != current.git_sha,
            "protected_file_changes": [],
            "module_size_changes": [],
            "test_count_change": current.test_count - snapshot.test_count,
            "tool_count_change": current.tool_count - snapshot.tool_count,
            "skill_count_change": current.skill_count - snapshot.skill_count,
        }

        # Check protected files
        for f, old_hash in snapshot.file_hashes.items():
            new_hash = current.file_hashes.get(f, "MISSING")
            if old_hash != new_hash:
                changes["protected_file_changes"].append(
                    {
                        "file": f,
                        "old_hash": old_hash[:12],
                        "new_hash": new_hash[:12],
                    }
                )

        # Check module sizes
        for mod, old_lines in snapshot.module_line_counts.items():
            new_lines = current.module_line_counts.get(mod, 0)
            diff = new_lines - old_lines
            if abs(diff) > 10:
                changes["module_size_changes"].append(
                    {
                        "module": mod,
                        "old": old_lines,
                        "new": new_lines,
                        "diff": diff,
                    }
                )

        return changes

    def get_fingerprint_report(self) -> str:
        """Generate a fingerprint report."""
        snapshot = self.take_snapshot()
        lines = [
            "## Evolution Fingerprint",
            "",
            f"**Snapshot:** {snapshot.snapshot_id}",
            f"**Git SHA:** {snapshot.git_sha[:12]}",
            f"**Tests:** {snapshot.test_count}",
            f"**Tools:** {snapshot.tool_count}",
            f"**Skills:** {snapshot.skill_count}",
            f"**Vault notes:** {snapshot.vault_note_count}",
        ]

        # Protected files
        lines.append("\n### Protected Files")
        for f, h in snapshot.file_hashes.items():
            lines.append(f"- {f}: `{h[:12]}`")

        # Largest modules
        sorted_modules = sorted(snapshot.module_line_counts.items(), key=lambda x: -x[1])[:5]
        lines.append("\n### Largest Modules")
        for mod, lines_count in sorted_modules:
            marker = " ***" if lines_count > 1000 else ""
            lines.append(f"- {mod}: {lines_count} lines{marker}")

        return "\n".join(lines)

    def generate_report(self) -> str:
        """Generate an evolution fingerprint report (alias for compatibility)."""
        return self.get_fingerprint_report()

    def _get_git_sha(self) -> str:
        """Get current git SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=str(self._repo_dir),
            )
            return result.stdout.strip()[:40]
        except Exception:
            return "unknown"

    def _hash_file(self, path: pathlib.Path) -> str:
        """Hash a file's contents."""
        try:
            content = path.read_bytes()
            return hashlib.sha256(content).hexdigest()
        except Exception:
            return "error"

    def _count_tests(self) -> int:
        """Count tests."""
        try:
            test_dir = self._repo_dir / "tests"
            if test_dir.exists():
                count = 0
                for py_file in test_dir.glob("test_*.py"):
                    content = py_file.read_text(encoding="utf-8", errors="replace")
                    count += content.count("def test_")
                return count
        except Exception:
            pass
        return 0

    def _count_tools(self) -> int:
        """Count registered tools."""
        try:
            from ouroboros.tools.registry import ToolRegistry

            r = ToolRegistry(repo_dir=self._repo_dir, drive_root=self._repo_dir)
            return len(r.schemas())
        except Exception:
            return 0

    def _count_skills(self) -> int:
        """Count registered skills."""
        try:
            from ouroboros.tools.skills import SKILLS

            return len(SKILLS)
        except Exception:
            return 0

    def _count_vault_notes(self) -> int:
        """Count vault notes."""
        try:
            vault_dir = self._repo_dir / "vault"
            if vault_dir.exists():
                return len(list(vault_dir.rglob("*.md")))
        except Exception:
            pass
        return 0

    def _save_snapshot(self, snapshot: EvolutionFingerprint) -> None:
        """Save snapshot to disk."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            existing = []
            if self._path.exists():
                try:
                    existing = json.loads(self._path.read_text(encoding="utf-8"))
                except Exception:
                    existing = []
            existing.append(snapshot.to_dict())
            self._path.write_text(json.dumps(existing[-50:], indent=2), encoding="utf-8")
        except Exception as e:
            log.warning("Failed to save fingerprint: %s", e)
