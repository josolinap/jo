"""Knowledge decay — forget what doesn't matter.

Archives low-value vault notes so active context stays clean.
Value = access_count × recency_weight × connection_count

Notes with low value get archived (not deleted).
Archived notes are still searchable but not in active context.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

DECAY_LOG = "~/.jo_data/knowledge_decay.json"
ARCHIVE_DIR = "vault/.archive"
MIN_VALUE_THRESHOLD = 0.1  # Below this, archive the note
RECENCY_HALFLIFE_DAYS = 30  # Value halves every 30 days


@dataclass
class NoteValue:
    """Value assessment for a vault note."""

    path: str
    title: str
    access_count: int
    days_since_modified: float
    connection_count: int
    value_score: float
    action: str  # keep / archive / review


class KnowledgeDecay:
    """Manages knowledge value and decay."""

    def __init__(self, repo_dir: pathlib.Path):
        self._repo_dir = repo_dir
        self._vault_dir = repo_dir / "vault"
        self._archive_dir = repo_dir / ARCHIVE_DIR
        self._log_path = pathlib.Path(DECAY_LOG).expanduser()

    def assess_all(self) -> List[NoteValue]:
        """Assess value of all vault notes."""
        if not self._vault_dir.exists():
            return []

        notes = []
        for md_file in self._vault_dir.rglob("*.md"):
            if ".archive" in str(md_file):
                continue
            value = self._assess_note(md_file)
            notes.append(value)

        notes.sort(key=lambda n: n.value_score)
        return notes

    def get_archive_candidates(self) -> List[NoteValue]:
        """Get notes that should be archived."""
        notes = self.assess_all()
        return [n for n in notes if n.value_score < MIN_VALUE_THRESHOLD]

    def archive_note(self, note_path: str) -> str:
        """Move a note to the archive."""
        src = self._repo_dir / note_path
        if not src.exists():
            return f"Note not found: {note_path}"

        self._archive_dir.mkdir(parents=True, exist_ok=True)
        dst = self._archive_dir / src.name

        try:
            src.rename(dst)
            self._log_action("archived", note_path)
            return f"Archived: {note_path}"
        except Exception as e:
            return f"Failed to archive: {e}"

    def restore_note(self, note_path: str) -> str:
        """Restore an archived note."""
        # Find in archive
        archived = self._archive_dir / pathlib.Path(note_path).name
        if not archived.exists():
            return f"Not found in archive: {note_path}"

        dst = self._repo_dir / note_path
        try:
            archived.rename(dst)
            self._log_action("restored", note_path)
            return f"Restored: {note_path}"
        except Exception as e:
            return f"Failed to restore: {e}"

    def get_decay_report(self) -> str:
        """Generate a decay report."""
        notes = self.assess_all()
        if not notes:
            return "No vault notes found."

        candidates = [n for n in notes if n.value_score < MIN_VALUE_THRESHOLD]
        low_value = [n for n in notes if MIN_VALUE_THRESHOLD <= n.value_score < 0.3]
        healthy = [n for n in notes if n.value_score >= 0.3]

        lines = [
            "## Knowledge Decay Report",
            "",
            f"**Total notes:** {len(notes)}",
            f"**Healthy (>=0.3):** {len(healthy)}",
            f"**Low value (0.1-0.3):** {len(low_value)}",
            f"**Archive candidates (<0.1):** {len(candidates)}",
        ]

        if candidates:
            lines.append("\n### Archive Candidates")
            for n in candidates[:10]:
                lines.append(
                    f"- [{n.value_score:.3f}] {n.title} ({n.days_since_modified:.0f}d, {n.connection_count} links)"
                )

        if low_value:
            lines.append("\n### Low Value (Review)")
            for n in low_value[:5]:
                lines.append(f"- [{n.value_score:.3f}] {n.title}")

        return "\n".join(lines)

    def _assess_note(self, md_file: pathlib.Path) -> NoteValue:
        """Assess the value of a single note."""
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
        except Exception:
            content = ""

        # Access count: count how many other notes link to this one
        title = md_file.stem
        link_count = self._count_incoming_links(title)

        # Connection count: wikilinks from this note
        outgoing = len(re.findall(r"\[\[([^\]]+)\]\]", content))

        # Recency
        try:
            mtime = md_file.stat().st_mtime
            days_since = (time.time() - mtime) / 86400
        except Exception:
            days_since = 365

        # Access count approximation: check frontmatter or estimate from links
        access_count = link_count + outgoing

        # Value score
        recency_weight = 2 ** (-days_since / RECENCY_HALFLIFE_DAYS)
        value = (access_count * 0.4 + 1) * recency_weight * (1 + link_count * 0.3)

        # Normalize to 0-1
        value_score = min(1.0, value / 10)

        # Determine action
        if value_score < MIN_VALUE_THRESHOLD:
            action = "archive"
        elif value_score < 0.3:
            action = "review"
        else:
            action = "keep"

        return NoteValue(
            path=str(md_file.relative_to(self._repo_dir)),
            title=title,
            access_count=access_count,
            days_since_modified=days_since,
            connection_count=link_count,
            value_score=value_score,
            action=action,
        )

    def _count_incoming_links(self, title: str) -> int:
        """Count how many other notes link to this title."""
        count = 0
        pattern = re.compile(rf"\[\[{re.escape(title)}\]\]", re.IGNORECASE)
        for md_file in self._vault_dir.rglob("*.md"):
            if md_file.stem.lower() == title.lower():
                continue
            if ".archive" in str(md_file):
                continue
            try:
                content = md_file.read_text(encoding="utf-8", errors="replace")
                if pattern.search(content):
                    count += 1
            except Exception:
                continue
        return count

    def _log_action(self, action: str, path: str) -> None:
        """Log a decay action."""
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            entry = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "action": action, "path": path}
            existing = []
            if self._log_path.exists():
                try:
                    existing = json.loads(self._log_path.read_text())
                except Exception:
                    existing = []
            existing.append(entry)
            self._log_path.write_text(json.dumps(existing[-100:], indent=2))
        except Exception:
            pass
