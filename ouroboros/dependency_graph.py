"""
Ouroboros — Task Dependency Graph.

Tracks task dependencies with blocked-by/blocks syntax.
Inspired by aidevops' Beads pattern for task graph management.

Features:
- Dependency tracking: blocked-by:t001, blocks:t002
- Hierarchical tasks: t001.1 (subtask)
- Ready tasks: tasks with no open blockers
- Critical path analysis
- Graph visualization
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class DepTask:
    task_id: str
    title: str
    status: str = "pending"
    blocked_by: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    parent: Optional[str] = None
    subtasks: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    completed_at: str = ""
    priority: int = 0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


class DependencyGraph:
    """Manages task dependencies as a directed acyclic graph."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.graph_path = repo_dir / "memory" / "dependency_graph.json"
        self._tasks: Dict[str, DepTask] = {}
        self._load()

    def _load(self) -> None:
        if self.graph_path.exists():
            try:
                data = json.loads(self.graph_path.read_text(encoding="utf-8"))
                for tid, tdata in data.get("tasks", {}).items():
                    self._tasks[tid] = DepTask(**tdata)
            except Exception as e:
                log.warning("Failed to load dependency graph: %s", e)

    def _save(self) -> None:
        self.graph_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "tasks": {tid: t.to_dict() for tid, t in self._tasks.items()},
            "updated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.graph_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def add_task(
        self,
        task_id: str,
        title: str,
        blocked_by: Optional[List[str]] = None,
        parent: Optional[str] = None,
        priority: int = 0,
        tags: Optional[List[str]] = None,
    ) -> str:
        if task_id in self._tasks:
            return f"Task '{task_id}' already exists"
        task = DepTask(
            task_id=task_id,
            title=title,
            blocked_by=blocked_by or [],
            parent=parent,
            priority=priority,
            tags=tags or [],
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._tasks[task_id] = task
        for dep_id in task.blocked_by:
            if dep_id in self._tasks:
                if task_id not in self._tasks[dep_id].blocks:
                    self._tasks[dep_id].blocks.append(task_id)
        if parent and parent in self._tasks:
            if task_id not in self._tasks[parent].subtasks:
                self._tasks[parent].subtasks.append(task_id)
        self._save()
        return f"Added task '{task_id}': {title}"

    def complete_task(self, task_id: str) -> str:
        if task_id not in self._tasks:
            return f"Task '{task_id}' not found"
        task = self._tasks[task_id]
        task.status = "done"
        task.completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self._save()
        unblocked = []
        for blocked_id in task.blocks:
            blocked = self._tasks.get(blocked_id)
            if blocked and all(self._tasks.get(d, DepTask("", "")).status == "done" for d in blocked.blocked_by):
                blocked.status = "pending"
                unblocked.append(blocked_id)
        msg = f"Completed task '{task_id}'"
        if unblocked:
            msg += f"\nUnblocked: {', '.join(unblocked)}"
        return msg

    def get_ready_tasks(self) -> List[DepTask]:
        ready = []
        for task in self._tasks.values():
            if task.status != "pending":
                continue
            if all(self._tasks.get(d, DepTask("", "")).status == "done" for d in task.blocked_by):
                ready.append(task)
        ready.sort(key=lambda t: -t.priority)
        return ready

    def get_blocked_tasks(self) -> List[Tuple[DepTask, List[str]]]:
        blocked = []
        for task in self._tasks.values():
            if task.status == "done":
                continue
            blockers = [d for d in task.blocked_by if self._tasks.get(d, DepTask("", "")).status != "done"]
            if blockers:
                blocked.append((task, blockers))
        return blocked

    def get_critical_path(self) -> List[str]:
        depths: Dict[str, int] = {}
        for task in self._tasks.values():
            if task.status == "done":
                depths[task.task_id] = 0
            elif not task.blocked_by:
                depths[task.task_id] = 1
            else:
                depths[task.task_id] = max(depths.get(d, 0) for d in task.blocked_by) + 1
        if not depths:
            return []
        max_depth = max(depths.values())
        critical = [tid for tid, d in depths.items() if d == max_depth and self._tasks[tid].status != "done"]
        return critical[:5]

    def summary(self) -> str:
        total = len(self._tasks)
        done = sum(1 for t in self._tasks.values() if t.status == "done")
        ready = len(self.get_ready_tasks())
        blocked = len(self.get_blocked_tasks())
        in_progress = sum(1 for t in self._tasks.values() if t.status == "in_progress")
        lines = [
            f"## Dependency Graph ({total} tasks)",
            f"- **Done**: {done}",
            f"- **In Progress**: {in_progress}",
            f"- **Ready**: {ready}",
            f"- **Blocked**: {blocked}",
        ]
        ready_tasks = self.get_ready_tasks()
        if ready_tasks:
            lines.append("\n### Ready Tasks")
            for t in ready_tasks[:10]:
                lines.append(f"- `{t.task_id}`: {t.title}")
        blocked_tasks = self.get_blocked_tasks()
        if blocked_tasks:
            lines.append("\n### Blocked Tasks")
            for t, blockers in blocked_tasks[:5]:
                lines.append(f"- `{t.task_id}`: {t.title} (blocked by: {', '.join(blockers)})")
        critical = self.get_critical_path()
        if critical:
            lines.append(f"\n### Critical Path: {' → '.join(critical)}")
        return "\n".join(lines)

    def parse_todo(self, content: str) -> str:
        import re

        pattern = re.compile(
            r"^- \[([ x])\] (?:`?(\w+)`?\s+)?(.+?)(?:\s+blocked-by:(\S+))?(?:\s+blocks:(\S+))?\s*$", re.MULTILINE
        )
        added = 0
        for m in pattern.finditer(content):
            checked, tid, title, blocked_by, blocks = m.groups()
            task_id = tid or f"t{added + 1:03d}"
            status = "done" if checked == "x" else "pending"
            deps = [d.strip() for d in blocked_by.split(",")] if blocked_by else []
            if task_id not in self._tasks:
                self.add_task(task_id, title.strip(), deps)
                if status == "done":
                    self.complete_task(task_id)
                added += 1
        self._save()
        return f"Parsed {added} tasks from TODO content"

    def export_todo(self) -> str:
        lines = []
        for task in sorted(self._tasks.values(), key=lambda t: (t.status == "done", -t.priority)):
            check = "x" if task.status == "done" else " "
            deps = f" blocked-by:{','.join(task.blocked_by)}" if task.blocked_by else ""
            blocks_str = f" blocks:{','.join(task.blocks)}" if task.blocks else ""
            lines.append(f"- [{check}] `{task.task_id}` {task.title}{deps}{blocks_str}")
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _graphs: Dict[str, DependencyGraph] = {}

    def _get_graph(repo_dir: pathlib.Path) -> DependencyGraph:
        key = str(repo_dir)
        if key not in _graphs:
            _graphs[key] = DependencyGraph(repo_dir)
        return _graphs[key]

    def depgraph_add(ctx, task_id: str, title: str, blocked_by: str = "", priority: int = 0) -> str:
        deps = [d.strip() for d in blocked_by.split(",") if d.strip()] if blocked_by else []
        return _get_graph(ctx.repo_dir).add_task(task_id, title, deps, priority=priority)

    def depgraph_complete(ctx, task_id: str) -> str:
        return _get_graph(ctx.repo_dir).complete_task(task_id)

    def depgraph_ready(ctx) -> str:
        graph = _get_graph(ctx.repo_dir)
        ready = graph.get_ready_tasks()
        if not ready:
            return "No ready tasks."
        return "Ready tasks:\n" + "\n".join(f"- `{t.task_id}`: {t.title}" for t in ready[:15])

    def depgraph_summary(ctx) -> str:
        return _get_graph(ctx.repo_dir).summary()

    def depgraph_parse(ctx, content: str) -> str:
        return _get_graph(ctx.repo_dir).parse_todo(content)

    return [
        ToolEntry(
            "depgraph_add",
            {
                "name": "depgraph_add",
                "description": "Add a task with dependencies to the dependency graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Unique task ID (e.g. t001)"},
                        "title": {"type": "string", "description": "Task description"},
                        "blocked_by": {
                            "type": "string",
                            "default": "",
                            "description": "Comma-separated task IDs this depends on",
                        },
                        "priority": {"type": "integer", "default": 0},
                    },
                    "required": ["task_id", "title"],
                },
            },
            depgraph_add,
        ),
        ToolEntry(
            "depgraph_complete",
            {
                "name": "depgraph_complete",
                "description": "Mark a task as complete and unblock dependent tasks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_id": {"type": "string", "description": "Task ID to complete"},
                    },
                    "required": ["task_id"],
                },
            },
            depgraph_complete,
        ),
        ToolEntry(
            "depgraph_ready",
            {
                "name": "depgraph_ready",
                "description": "Get tasks that are ready to work on (no open blockers).",
                "parameters": {"type": "object", "properties": {}},
            },
            depgraph_ready,
        ),
        ToolEntry(
            "depgraph_summary",
            {
                "name": "depgraph_summary",
                "description": "Get dependency graph summary with critical path.",
                "parameters": {"type": "object", "properties": {}},
            },
            depgraph_summary,
        ),
        ToolEntry(
            "depgraph_parse",
            {
                "name": "depgraph_parse",
                "description": "Parse TODO.md content with blocked-by/blocks syntax into dependency graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "TODO.md content to parse"},
                    },
                    "required": ["content"],
                },
            },
            depgraph_parse,
        ),
    ]
