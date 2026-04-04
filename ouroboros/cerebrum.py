"""
Ouroboros — Cerebrum (Learning Memory).

Accumulates preferences, corrections, and Do-Not-Repeat rules across sessions.
Inspired by OpenWolf's cerebrum.md pattern.

Stores data in memory/cerebrum.json with three sections:
- do_not_repeat: mistakes that should never happen again
- preferences: user/agent coding preferences
- learnings: key insights about the codebase
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class CerebrumEntry:
    content: str
    category: str  # "do_not_repeat", "preference", "learning"
    added_at: str = ""
    tags: List[str] = field(default_factory=list)
    source: str = ""  # where this was learned from


@dataclass
class Cerebrum:
    do_not_repeat: List[CerebrumEntry] = field(default_factory=list)
    preferences: List[CerebrumEntry] = field(default_factory=list)
    learnings: List[CerebrumEntry] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "do_not_repeat": [vars(e) for e in self.do_not_repeat],
            "preferences": [vars(e) for e in self.preferences],
            "learnings": [vars(e) for e in self.learnings],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Cerebrum:
        def _entries(raw_list: List[Dict]) -> List[CerebrumEntry]:
            return [CerebrumEntry(**e) for e in raw_list]

        return cls(
            do_not_repeat=_entries(data.get("do_not_repeat", [])),
            preferences=_entries(data.get("preferences", [])),
            learnings=_entries(data.get("learnings", [])),
        )

    def search(self, query: str, limit: int = 5) -> List[CerebrumEntry]:
        query_lower = query.lower()
        all_entries = self.do_not_repeat + self.preferences + self.learnings
        matches = [
            e for e in all_entries if query_lower in e.content.lower() or any(query_lower in t.lower() for t in e.tags)
        ]
        return matches[:limit]

    def check_violations(self, action: str) -> List[CerebrumEntry]:
        action_lower = action.lower()
        return [
            e
            for e in self.do_not_repeat
            if e.content.lower() in action_lower or any(t.lower() in action_lower for t in e.tags)
        ]


class CerebrumManager:
    """Manages the cerebrum learning memory."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.cerebrum_path = repo_dir / "memory" / "cerebrum.json"
        self._cerebrum: Optional[Cerebrum] = None

        # Load configuration
        try:
            from ouroboros.config_manager import get_config_manager

            config = get_config_manager().as_dict()
            cerebrum_config = config.get("cerebrum", {})
            self._max_do_not_repeat = cerebrum_config.get("max_do_not_repeat", 100)
            self._max_preferences = cerebrum_config.get("max_preferences", 200)
            self._max_learnings = cerebrum_config.get("max_learnings", 500)
            self._min_confidence = cerebrum_config.get("min_confidence", 0.6)
        except Exception:
            self._max_do_not_repeat = 100
            self._max_preferences = 200
            self._max_learnings = 500
            self._min_confidence = 0.6

    def _load(self) -> Cerebrum:
        if self._cerebrum is not None:
            return self._cerebrum
        if self.cerebrum_path.exists():
            try:
                data = json.loads(self.cerebrum_path.read_text(encoding="utf-8"))
                self._cerebrum = Cerebrum.from_dict(data)
            except Exception as e:
                log.warning("Failed to load cerebrum: %s", e)
                self._cerebrum = Cerebrum()
        else:
            self._cerebrum = Cerebrum()
        return self._cerebrum

    def _save(self) -> None:
        self.cerebrum_path.parent.mkdir(parents=True, exist_ok=True)
        self.cerebrum_path.write_text(
            json.dumps(self._cerebrum.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def add_do_not_repeat(self, content: str, tags: Optional[List[str]] = None, source: str = "") -> str:
        entry = CerebrumEntry(
            content=content,
            category="do_not_repeat",
            added_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            tags=tags or [],
            source=source,
        )
        cerebrum = self._load()
        cerebrum.do_not_repeat.append(entry)
        self._save()
        return f"Added Do-Not-Repeat rule: {content}"

    def add_preference(self, content: str, tags: Optional[List[str]] = None, source: str = "") -> str:
        entry = CerebrumEntry(
            content=content,
            category="preference",
            added_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            tags=tags or [],
            source=source,
        )
        cerebrum = self._load()
        cerebrum.preferences.append(entry)
        self._save()
        return f"Added preference: {content}"

    def add_learning(self, content: str, tags: Optional[List[str]] = None, source: str = "") -> str:
        entry = CerebrumEntry(
            content=content,
            category="learning",
            added_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
            tags=tags or [],
            source=source,
        )
        cerebrum = self._load()
        cerebrum.learnings.append(entry)
        self._save()
        return f"Added learning: {content}"

    def search(self, query: str, limit: int = 5) -> str:
        cerebrum = self._load()
        matches = cerebrum.search(query, limit)
        if not matches:
            return f"No cerebrum entries found for: {query}"
        lines = [f"Found {len(matches)} entries for '{query}':"]
        for m in matches:
            lines.append(f"- [{m.category}] {m.content} (tags: {', '.join(m.tags) if m.tags else 'none'})")
        return "\n".join(lines)

    def check_before_action(self, action: str) -> str:
        cerebrum = self._load()
        violations = cerebrum.check_violations(action)
        if not violations:
            return ""
        lines = ["⚠️ Cerebrum Do-Not-Repeat violations detected:"]
        for v in violations:
            lines.append(f"  - {v.content}")
        return "\n".join(lines)

    def summary(self) -> str:
        cerebrum = self._load()
        lines = [
            "## Cerebrum (Learning Memory)",
            f"- Do-Not-Repeat rules: {len(cerebrum.do_not_repeat)}",
            f"- Preferences: {len(cerebrum.preferences)}",
            f"- Learnings: {len(cerebrum.learnings)}",
        ]
        if cerebrum.do_not_repeat:
            lines.append("\n### Do-Not-Repeat")
            for e in cerebrum.do_not_repeat[-5:]:
                lines.append(f"- {e.content}")
        if cerebrum.preferences:
            lines.append("\n### Preferences")
            for e in cerebrum.preferences[-5:]:
                lines.append(f"- {e.content}")
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, CerebrumManager] = {}

    def _get_manager(repo_dir: pathlib.Path) -> CerebrumManager:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = CerebrumManager(repo_dir)
        return _managers[key]

    def cerebrum_add(ctx, content: str, category: str = "learning", tags: str = "", source: str = "") -> str:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []
        mgr = _get_manager(ctx.repo_dir)
        if category == "do_not_repeat":
            return mgr.add_do_not_repeat(content, tag_list, source)
        elif category == "preference":
            return mgr.add_preference(content, tag_list, source)
        else:
            return mgr.add_learning(content, tag_list, source)

    def cerebrum_search(ctx, query: str, limit: int = 5) -> str:
        return _get_manager(ctx.repo_dir).search(query, limit)

    def cerebrum_check(ctx, action: str) -> str:
        result = _get_manager(ctx.repo_dir).check_before_action(action)
        return result if result else "✅ No Do-Not-Repeat violations detected."

    def cerebrum_summary(ctx) -> str:
        return _get_manager(ctx.repo_dir).summary()

    return [
        ToolEntry(
            "cerebrum_add",
            {
                "name": "cerebrum_add",
                "description": "Add an entry to the cerebrum learning memory. Use category='do_not_repeat' for mistakes to avoid, 'preference' for coding style, 'learning' for codebase insights.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "The learning/preference/rule content"},
                        "category": {
                            "type": "string",
                            "enum": ["do_not_repeat", "preference", "learning"],
                            "default": "learning",
                        },
                        "tags": {"type": "string", "description": "Comma-separated tags for searchability"},
                        "source": {"type": "string", "description": "Where this was learned from"},
                    },
                    "required": ["content"],
                },
            },
            cerebrum_add,
        ),
        ToolEntry(
            "cerebrum_search",
            {
                "name": "cerebrum_search",
                "description": "Search the cerebrum for relevant learnings, preferences, or rules.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "limit": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
            cerebrum_search,
        ),
        ToolEntry(
            "cerebrum_check",
            {
                "name": "cerebrum_check",
                "description": "Check if an action violates any Do-Not-Repeat rules before executing.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "The action to check"},
                    },
                    "required": ["action"],
                },
            },
            cerebrum_check,
        ),
        ToolEntry(
            "cerebrum_summary",
            {
                "name": "cerebrum_summary",
                "description": "Get a summary of all cerebrum entries.",
                "parameters": {"type": "object", "properties": {}},
            },
            cerebrum_summary,
        ),
    ]
