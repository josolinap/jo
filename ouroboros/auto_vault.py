"""
Jo — Auto-Vault System.

Automatically persists tool outputs to vault so knowledge isn't lost after sessions.
Inspired by BIBLE.md Principle 1 (Continuity) and Principle 5 (Minimalism).

Key design:
1. Tools that produce knowledge should save to vault automatically
2. Different tool types save to different vault categories
3. Deduplication prevents vault bloat
4. Links back to source tool and session
"""

from __future__ import annotations

import hashlib
import logging
import pathlib
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class VaultEntry:
    """A vault entry with metadata."""

    title: str
    content: str
    category: str  # learnings, bugs, memories, concepts
    source_tool: str
    session_id: str = ""
    tags: list = None
    created_at: str = ""
    content_hash: str = ""


class AutoVault:
    """Automatically persists tool outputs to vault."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.vault_dir = repo_dir / "vault"
        self.learnings_dir = self.vault_dir / "learnings"
        self.bugs_dir = self.vault_dir / "bugs"
        self.memories_dir = self.vault_dir / "memories"
        self._ensure_dirs()
        self._index = self._load_index()

    def _ensure_dirs(self) -> None:
        """Ensure vault directories exist."""
        for d in [self.learnings_dir, self.bugs_dir, self.memories_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def _load_index(self) -> Dict[str, Any]:
        """Load the auto-vault index."""
        index_path = self.vault_dir / "auto_vault_index.json"
        if index_path.exists():
            try:
                import json

                return json.loads(index_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {"entries": {}, "last_cleanup": ""}

    def _save_index(self) -> None:
        """Save the auto-vault index."""
        index_path = self.vault_dir / "auto_vault_index.json"
        import json

        index_path.write_text(json.dumps(self._index, indent=2), encoding="utf-8")

    def _hash_content(self, content: str) -> str:
        """Hash content for deduplication."""
        return hashlib.md5(content.strip().encode()).hexdigest()[:12]

    def _is_duplicate(self, content: str, category: str) -> bool:
        """Check if content already exists in vault."""
        content_hash = self._hash_content(content)
        return content_hash in self._index.get("entries", {})

    def _make_filename(self, title: str, category: str) -> str:
        """Create a safe filename from title."""
        safe = "".join(c if c.isalnum() or c in "-_ " else "-" for c in title.lower())
        safe = "-".join(safe.split())  # Normalize whitespace
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"{safe}-{timestamp}.md"

    def save_learning(self, title: str, content: str, source_tool: str, session_id: str = "", tags: list = None) -> str:
        """Save a learning to vault/learnings/."""
        if self._is_duplicate(content, "learnings"):
            return f"⏭️ Learning already exists in vault (deduplicated)"

        filename = self._make_filename(title, "learnings")
        filepath = self.learnings_dir / filename

        content_hash = self._hash_content(content)
        now = datetime.now().isoformat()

        note = f"""---
title: "{title}"
type: learning
status: active
tags: [{", ".join(tags or [])}]
source: {source_tool}
session: {session_id}
created: {now}
---

# {title}

{content}

---
*Auto-saved by {source_tool} | Session: {session_id}*
"""
        filepath.write_text(note, encoding="utf-8")

        self._index.setdefault("entries", {})[content_hash] = {
            "title": title,
            "category": "learnings",
            "file": filename,
            "source": source_tool,
            "created": now,
        }
        self._save_index()

        return f"✅ Learning saved to vault/learnings/{filename}"

    def save_bug(
        self,
        error_message: str,
        file_path: str,
        root_cause: str,
        fix_description: str,
        source_tool: str = "buglog",
        session_id: str = "",
        tags: list = None,
    ) -> str:
        """Save a bug pattern to vault/bugs/."""
        content = f"Error: {error_message}\nFile: {file_path}\nRoot Cause: {root_cause}\nFix: {fix_description}"
        if self._is_duplicate(content, "bugs"):
            return f"⏭️ Bug pattern already exists in vault (deduplicated)"

        title = f"Bug: {error_message[:50]}"
        filename = self._make_filename(title, "bugs")
        filepath = self.bugs_dir / filename

        content_hash = self._hash_content(content)
        now = datetime.now().isoformat()

        note = f"""---
title: "{title}"
type: bug
status: fixed
tags: [{", ".join(tags or [])}]
source: {source_tool}
session: {session_id}
created: {now}
---

# {title}

## Error
{error_message}

## File
{file_path}

## Root Cause
{root_cause}

## Fix
{fix_description}

---
*Auto-saved by {source_tool} | Session: {session_id}*
"""
        filepath.write_text(note, encoding="utf-8")

        self._index.setdefault("entries", {})[content_hash] = {
            "title": title,
            "category": "bugs",
            "file": filename,
            "source": source_tool,
            "created": now,
        }
        self._save_index()

        return f"✅ Bug pattern saved to vault/bugs/{filename}"

    def save_memory(
        self,
        title: str,
        content: str,
        category: str = "pattern",
        source_tool: str = "memory_extractor",
        session_id: str = "",
        tags: list = None,
    ) -> str:
        """Save an extracted memory to vault/memories/."""
        if self._is_duplicate(content, "memories"):
            return f"⏭️ Memory already exists in vault (deduplicated)"

        filename = self._make_filename(title, "memories")
        filepath = self.memories_dir / filename

        content_hash = self._hash_content(content)
        now = datetime.now().isoformat()

        note = f"""---
title: "{title}"
type: memory
category: {category}
status: active
tags: [{", ".join(tags or [])}]
source: {source_tool}
session: {session_id}
created: {now}
---

# {title}

{content}

---
*Auto-saved by {source_tool} | Session: {session_id}*
"""
        filepath.write_text(note, encoding="utf-8")

        self._index.setdefault("entries", {})[content_hash] = {
            "title": title,
            "category": "memories",
            "file": filename,
            "source": source_tool,
            "created": now,
        }
        self._save_index()

        return f"✅ Memory saved to vault/memories/{filename}"

    def save_verification(
        self,
        report_summary: str,
        source_tool: str = "verification",
        session_id: str = "",
        passed: bool = True,
        tags: list = None,
    ) -> str:
        """Save a verification report to vault/learnings/."""
        title = f"Verification: {'PASS' if passed else 'FAIL'} - {datetime.now().strftime('%Y-%m-%d')}"
        content = report_summary
        if self._is_duplicate(content, "learnings"):
            return f"⏭️ Verification report already exists in vault (deduplicated)"

        filename = self._make_filename(title, "learnings")
        filepath = self.learnings_dir / filename

        content_hash = self._hash_content(content)
        now = datetime.now().isoformat()

        note = f"""---
title: "{title}"
type: verification
status: {"passed" if passed else "failed"}
tags: [{", ".join(tags or [])}]
source: {source_tool}
session: {session_id}
created: {now}
---

# {title}

{report_summary}

---
*Auto-saved by {source_tool} | Session: {session_id}*
"""
        filepath.write_text(note, encoding="utf-8")

        self._index.setdefault("entries", {})[content_hash] = {
            "title": title,
            "category": "learnings",
            "file": filename,
            "source": source_tool,
            "created": now,
        }
        self._save_index()

        return f"✅ Verification saved to vault/learnings/{filename}"

    def get_stats(self) -> Dict[str, Any]:
        """Get auto-vault statistics."""
        entries = self._index.get("entries", {})
        by_category = {}
        for entry in entries.values():
            cat = entry.get("category", "unknown")
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_entries": len(entries),
            "by_category": by_category,
            "last_cleanup": self._index.get("last_cleanup", "Never"),
        }


# Global auto-vault instance
_vault: Optional[AutoVault] = None


def get_auto_vault(repo_dir: Optional[pathlib.Path] = None) -> AutoVault:
    """Get or create the global auto-vault."""
    global _vault
    if _vault is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _vault = AutoVault(repo_dir)
    return _vault
