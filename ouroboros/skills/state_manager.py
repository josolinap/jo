"""
Jo — Advanced State Management.

Inspired by oh-my-claudecode's state system.
Provides compaction-resistant storage for critical information.

Components:
1. Notepad - survives context compaction
2. Project Memory - persistent project-level knowledge
3. Session Scope - isolated state per session
4. Plan Notepad - per-plan knowledge capture
5. Persistent Tags - time-based memory retention
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class NotepadEntry:
    """A single notepad entry."""

    content: str
    timestamp: str
    priority: bool = False  # High priority entries are never pruned
    source: str = ""  # Where this entry came from


@dataclass
class PlanNotepad:
    """Per-plan knowledge capture."""

    plan_name: str
    learnings: List[str] = field(default_factory=list)
    decisions: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""


class Notepad:
    """Compaction-resistant memo pad."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self._entries: List[NotepadEntry] = []
        self._load()

    def _load(self) -> None:
        """Load notepad from file."""
        if self.path.exists():
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
                self._entries = [NotepadEntry(**e) for e in data.get("entries", [])]
            except Exception as e:
                log.debug(f"Failed to load notepad: {e}")
                self._entries = []

    def _save(self) -> None:
        """Save notepad to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "entries": [
                {
                    "content": e.content,
                    "timestamp": e.timestamp,
                    "priority": e.priority,
                    "source": e.source,
                }
                for e in self._entries
            ]
        }
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def write(self, content: str, source: str = "", priority: bool = False) -> None:
        """Write an entry to the notepad."""
        entry = NotepadEntry(
            content=content,
            timestamp=datetime.now().isoformat(),
            priority=priority,
            source=source,
        )
        self._entries.append(entry)
        self._save()

    def read(self) -> str:
        """Read all notepad entries as formatted string."""
        if not self._entries:
            return ""

        parts = ["## Notepad\n"]
        for entry in self._entries:
            priority_marker = " [PRIORITY]" if entry.priority else ""
            parts.append(f"### {entry.timestamp}{priority_marker}")
            if entry.source:
                parts.append(f"Source: {entry.source}")
            parts.append(entry.content)
            parts.append("")

        return "\n".join(parts)

    def prune(self, max_entries: int = 50) -> int:
        """Remove old non-priority entries."""
        priority_entries = [e for e in self._entries if e.priority]
        non_priority = [e for e in self._entries if not e.priority]

        if len(non_priority) > max_entries:
            removed = len(non_priority) - max_entries
            non_priority = non_priority[-max_entries:]
            self._entries = priority_entries + non_priority
            self._save()
            return removed

        return 0

    def stats(self) -> Dict[str, Any]:
        """Get notepad statistics."""
        priority_count = sum(1 for e in self._entries if e.priority)
        return {
            "total_entries": len(self._entries),
            "priority_entries": priority_count,
            "working_entries": len(self._entries) - priority_count,
        }


class ProjectMemory:
    """Persistent project-level knowledge store."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self._memory: Dict[str, Any] = {
            "directives": [],
            "notes": [],
            "decisions": [],
            "patterns": [],
        }
        self._load()

    def _load(self) -> None:
        """Load project memory from file."""
        if self.path.exists():
            try:
                self._memory = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception as e:
                log.debug(f"Failed to load project memory: {e}")

    def _save(self) -> None:
        """Save project memory to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._memory, indent=2), encoding="utf-8")

    def add_note(self, note: str) -> None:
        """Add a note to project memory."""
        self._memory["notes"].append(
            {
                "content": note,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()

    def add_directive(self, directive: str) -> None:
        """Add a directive to project memory."""
        self._memory["directives"].append(
            {
                "content": directive,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()

    def add_decision(self, decision: str, rationale: str = "") -> None:
        """Add a decision to project memory."""
        self._memory["decisions"].append(
            {
                "content": decision,
                "rationale": rationale,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()

    def add_pattern(self, pattern: str, context: str = "") -> None:
        """Add a pattern to project memory."""
        self._memory["patterns"].append(
            {
                "content": pattern,
                "context": context,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save()

    def read(self) -> str:
        """Read project memory as formatted string."""
        parts = ["## Project Memory\n"]

        if self._memory.get("directives"):
            parts.append("### Directives")
            for d in self._memory["directives"]:
                parts.append(f"- {d['content']}")
            parts.append("")

        if self._memory.get("notes"):
            parts.append("### Notes")
            for n in self._memory["notes"]:
                parts.append(f"- {n['content']}")
            parts.append("")

        if self._memory.get("decisions"):
            parts.append("### Decisions")
            for d in self._memory["decisions"]:
                parts.append(f"- {d['content']}")
                if d.get("rationale"):
                    parts.append(f"  Rationale: {d['rationale']}")
            parts.append("")

        if self._memory.get("patterns"):
            parts.append("### Patterns")
            for p in self._memory["patterns"]:
                parts.append(f"- {p['content']}")
                if p.get("context"):
                    parts.append(f"  Context: {p['context']}")
            parts.append("")

        return "\n".join(parts) if len(parts) > 1 else ""


class PersistentTags:
    """Time-based memory retention system."""

    def __init__(self, path: pathlib.Path):
        self.path = path
        self._tags: List[Dict[str, Any]] = []
        self._load()

    def _load(self) -> None:
        """Load tags from file."""
        if self.path.exists():
            try:
                self._tags = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                self._tags = []

    def _save(self) -> None:
        """Save tags to file."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._tags, indent=2), encoding="utf-8")

    def add(self, content: str, permanent: bool = False) -> None:
        """Add a persistent tag."""
        tag = {
            "content": content,
            "created_at": datetime.now().isoformat(),
            "permanent": permanent,
            "expires_at": None if permanent else (datetime.now() + timedelta(days=7)).isoformat(),
        }
        self._tags.append(tag)
        self._save()

    def get_active(self) -> List[str]:
        """Get all active (non-expired) tags."""
        now = datetime.now()
        active = []
        for tag in self._tags:
            if tag.get("permanent"):
                active.append(tag["content"])
            else:
                expires = datetime.fromisoformat(tag["expires_at"])
                if now < expires:
                    active.append(tag["content"])
        return active

    def cleanup(self) -> int:
        """Remove expired tags."""
        before = len(self._tags)
        now = datetime.now()
        self._tags = [t for t in self._tags if t.get("permanent") or datetime.fromisoformat(t["expires_at"]) > now]
        self._save()
        return before - len(self._tags)


class StateManager:
    """Manages all state components for Jo."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state"
        self.notepad = Notepad(self.state_dir / "notepad.json")
        self.project_memory = ProjectMemory(self.state_dir / "project_memory.json")
        self.persistent_tags = PersistentTags(self.state_dir / "persistent_tags.json")
        self.plan_notepads: Dict[str, PlanNotepad] = {}
        self._load_plan_notepads()

    def _load_plan_notepads(self) -> None:
        """Load existing plan notepads."""
        plans_dir = self.state_dir / "plans"
        if plans_dir.exists():
            for plan_dir in plans_dir.iterdir():
                if plan_dir.is_dir():
                    plan_file = plan_dir / "plan.json"
                    if plan_file.exists():
                        try:
                            data = json.loads(plan_file.read_text(encoding="utf-8"))
                            self.plan_notepads[plan_dir.name] = PlanNotepad(**data)
                        except Exception:
                            pass

    def create_plan_notepad(self, plan_name: str) -> PlanNotepad:
        """Create a new plan notepad."""
        now = datetime.now().isoformat()
        plan = PlanNotepad(
            plan_name=plan_name,
            created_at=now,
            updated_at=now,
        )
        self.plan_notepads[plan_name] = plan
        self._save_plan_notepad(plan_name)
        return plan

    def _save_plan_notepad(self, plan_name: str) -> None:
        """Save a plan notepad to file."""
        plan = self.plan_notepads.get(plan_name)
        if not plan:
            return

        plans_dir = self.state_dir / "plans" / plan_name
        plans_dir.mkdir(parents=True, exist_ok=True)
        plan.updated_at = datetime.now().isoformat()

        plan_file = plans_dir / "plan.json"
        plan_file.write_text(
            json.dumps(
                {
                    "plan_name": plan.plan_name,
                    "learnings": plan.learnings,
                    "decisions": plan.decisions,
                    "issues": plan.issues,
                    "problems": plan.problems,
                    "created_at": plan.created_at,
                    "updated_at": plan.updated_at,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def add_plan_learning(self, plan_name: str, learning: str) -> None:
        """Add a learning to a plan notepad."""
        if plan_name not in self.plan_notepads:
            self.create_plan_notepad(plan_name)
        self.plan_notepads[plan_name].learnings.append(learning)
        self._save_plan_notepad(plan_name)

    def add_plan_decision(self, plan_name: str, decision: str) -> None:
        """Add a decision to a plan notepad."""
        if plan_name not in self.plan_notepads:
            self.create_plan_notepad(plan_name)
        self.plan_notepads[plan_name].decisions.append(decision)
        self._save_plan_notepad(plan_name)

    def add_plan_issue(self, plan_name: str, issue: str) -> None:
        """Add an issue to a plan notepad."""
        if plan_name not in self.plan_notepads:
            self.create_plan_notepad(plan_name)
        self.plan_notepads[plan_name].issues.append(issue)
        self._save_plan_notepad(plan_name)

    def add_plan_problem(self, plan_name: str, problem: str) -> None:
        """Add a problem to a plan notepad."""
        if plan_name not in self.plan_notepads:
            self.create_plan_notepad(plan_name)
        self.plan_notepads[plan_name].problems.append(problem)
        self._save_plan_notepad(plan_name)

    def get_full_context(self) -> str:
        """Get full state context for injection."""
        parts = []

        # Notepad
        notepad_content = self.notepad.read()
        if notepad_content:
            parts.append(notepad_content)

        # Project Memory
        project_memory = self.project_memory.read()
        if project_memory:
            parts.append(project_memory)

        # Persistent Tags
        active_tags = self.persistent_tags.get_active()
        if active_tags:
            parts.append("## Persistent Tags\n")
            for tag in active_tags:
                parts.append(f"- {tag}")
            parts.append("")

        # Plan Notepads
        if self.plan_notepads:
            parts.append("## Plan Knowledge\n")
            for name, plan in self.plan_notepads.items():
                parts.append(f"### Plan: {name}")
                if plan.learnings:
                    parts.append("Learnings:")
                    for l in plan.learnings:
                        parts.append(f"- {l}")
                if plan.decisions:
                    parts.append("Decisions:")
                    for d in plan.decisions:
                        parts.append(f"- {d}")
                if plan.issues:
                    parts.append("Issues:")
                    for i in plan.issues:
                        parts.append(f"- {i}")
                if plan.problems:
                    parts.append("Problems:")
                    for p in plan.problems:
                        parts.append(f"- {p}")
                parts.append("")

        return "\n".join(parts) if parts else ""

    def cleanup(self) -> Dict[str, int]:
        """Clean up expired and old state."""
        return {
            "expired_tags_removed": self.persistent_tags.cleanup(),
            "notepad_entries_pruned": self.notepad.prune(),
        }


# Global state manager instance
_manager: Optional[StateManager] = None


def get_state_manager(repo_dir: Optional[pathlib.Path] = None) -> StateManager:
    """Get or create the global state manager."""
    global _manager
    if _manager is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _manager = StateManager(repo_dir)
    return _manager
