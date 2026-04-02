"""
Ouroboros — Bug Log (Searchable Fix Memory).

Before fixing a bug, search for known solutions.
After fixing, log the solution for future reference.
Inspired by OpenWolf's buglog.json pattern.

Stores data in memory/buglog.json as a list of bug entries.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class BugEntry:
    bug_id: str
    error_message: str
    file_path: str
    root_cause: str
    fix_description: str
    tags: List[str] = field(default_factory=list)
    fixed_at: str = ""
    session_id: str = ""


class BugLog:
    """Manages the searchable bug fix memory."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.buglog_path = repo_dir / "memory" / "buglog.json"
        self._entries: Optional[List[BugEntry]] = None

    def _load(self) -> List[BugEntry]:
        if self._entries is not None:
            return self._entries
        if self.buglog_path.exists():
            try:
                data = json.loads(self.buglog_path.read_text(encoding="utf-8"))
                self._entries = [BugEntry(**e) for e in data.get("bugs", [])]
            except Exception as e:
                log.warning("Failed to load buglog: %s", e)
                self._entries = []
        else:
            self._entries = []
        return self._entries

    def _save(self) -> None:
        self.buglog_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"bugs": [vars(e) for e in self._entries], "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        self.buglog_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def log_fix(
        self,
        error_message: str,
        file_path: str,
        root_cause: str,
        fix_description: str,
        tags: Optional[List[str]] = None,
        session_id: str = "",
    ) -> str:
        entries = self._load()
        bug_id = f"bug-{uuid.uuid4().hex[:6]}"
        entry = BugEntry(
            bug_id=bug_id,
            error_message=error_message,
            file_path=file_path,
            root_cause=root_cause,
            fix_description=fix_description,
            tags=tags or [],
            fixed_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            session_id=session_id,
        )
        entries.append(entry)
        self._save()

        # Learning loop: Feed to Cerebrum
        try:
            from ouroboros.cerebrum import CerebrumManager

            cerebrum = CerebrumManager(self.repo_dir)
            # Add to do-not-repeat to avoid making the same mistake
            do_not_repeat_content = f"{error_message}: {root_cause}"
            cerebrum.add_do_not_repeat(
                content=do_not_repeat_content, tags=(tags or []) + ["buglog", "auto-learned"], source=f"buglog:{bug_id}"
            )
            # Add fix as a learning
            cerebrum.add_learning(
                content=f"Fix for {error_message[:50]}: {fix_description[:100]}",
                tags=(tags or []) + ["fix-pattern", "buglog"],
                source=f"buglog:{bug_id}",
            )
        except Exception:
            log.debug("Failed to feed buglog to cerebrum", exc_info=True)

        return f"Logged bug fix {bug_id}: {error_message[:80]}"

    def search(self, query: str, limit: int = 5) -> str:
        entries = self._load()
        query_lower = query.lower()
        matches = []
        for e in entries:
            searchable = (
                f"{e.error_message} {e.root_cause} {e.fix_description} {e.file_path} {' '.join(e.tags)}".lower()
            )
            if query_lower in searchable:
                matches.append(e)
        if not matches:
            return f"No known fixes found for: {query}"
        lines = [f"Found {len(matches)} known fixes for '{query}':"]
        for m in matches[:limit]:
            lines.append(f"\n### {m.bug_id} ({m.fixed_at})")
            lines.append(f"- **Error**: {m.error_message[:120]}")
            lines.append(f"- **File**: {m.file_path}")
            lines.append(f"- **Root cause**: {m.root_cause[:120]}")
            lines.append(f"- **Fix**: {m.fix_description[:120]}")
            if m.tags:
                lines.append(f"- **Tags**: {', '.join(m.tags)}")
        return "\n".join(lines)

    def summary(self) -> str:
        entries = self._load()
        if not entries:
            return "Bug log is empty."
        lines = [f"## Bug Log ({len(entries)} entries)"]
        tag_counts: Dict[str, int] = {}
        for e in entries:
            for t in e.tags:
                tag_counts[t] = tag_counts.get(t, 0) + 1
        if tag_counts:
            lines.append("\n### Top tags")
            for tag, count in sorted(tag_counts.items(), key=lambda x: -x[1])[:10]:
                lines.append(f"- {tag}: {count}")
        lines.append("\n### Recent fixes")
        for e in entries[-5:]:
            lines.append(f"- [{e.bug_id}] {e.error_message[:60]} → {e.fix_description[:60]}")
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, BugLog] = {}

    def _get_manager(repo_dir: pathlib.Path) -> BugLog:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = BugLog(repo_dir)
        return _managers[key]

    def buglog_log(
        ctx, error_message: str, file_path: str, root_cause: str, fix_description: str, tags: str = ""
    ) -> str:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        return _get_manager(ctx.repo_dir).log_fix(error_message, file_path, root_cause, fix_description, tag_list)

    def buglog_search(ctx, query: str, limit: int = 5) -> str:
        return _get_manager(ctx.repo_dir).search(query, limit)

    def buglog_summary(ctx) -> str:
        return _get_manager(ctx.repo_dir).summary()

    return [
        ToolEntry(
            "buglog_log",
            {
                "name": "buglog_log",
                "description": "Log a bug fix to the searchable bug memory. Call after successfully fixing a bug.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "error_message": {"type": "string", "description": "The error message or symptom"},
                        "file_path": {"type": "string", "description": "File where the bug occurred"},
                        "root_cause": {"type": "string", "description": "What caused the bug"},
                        "fix_description": {"type": "string", "description": "How the bug was fixed"},
                        "tags": {"type": "string", "description": "Comma-separated tags (e.g. 'null-check,api,react')"},
                    },
                    "required": ["error_message", "file_path", "root_cause", "fix_description"],
                },
            },
            buglog_log,
        ),
        ToolEntry(
            "buglog_search",
            {
                "name": "buglog_search",
                "description": "Search the bug log for known fixes before attempting to fix a bug.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Error message or keywords to search"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            buglog_search,
        ),
        ToolEntry(
            "buglog_summary",
            {
                "name": "buglog_summary",
                "description": "Get a summary of all logged bug fixes.",
                "parameters": {"type": "object", "properties": {}},
            },
            buglog_summary,
        ),
    ]
