"""
Jo — Working Memory System (TodoWrite Pattern).

Inspired by Claude Code's working memory pattern and the awesome-agentic-patterns
catalogue. Provides explicit working memory for complex multi-step tasks.

Problem: Without explicit working memory, agents lose track of subtasks,
forget intermediate results, and can't maintain state across long conversations.

Solution: A structured todo list that serves as working memory.
The agent writes todos, updates them as it progresses, and uses them
to maintain coherence across complex tasks.

Key features:
- Hierarchical todos (parent/child relationships)
- Status tracking (pending, in_progress, completed, failed)
- Progress calculation
- Automatic persistence to .jo_state/
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class TodoStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TodoItem:
    """A single todo item in working memory."""

    id: str
    content: str
    status: TodoStatus = TodoStatus.PENDING
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    notes: str = ""
    created_at: str = ""
    updated_at: str = ""
    completed_at: str = ""


class WorkingMemory:
    """Manages working memory via todo list for complex tasks."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "working_memory"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._todos: Dict[str, TodoItem] = {}
        self._active_task: str = ""
        self._load_state()

    def _load_state(self) -> None:
        """Load working memory state."""
        state_file = self.state_dir / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self._todos = {tid: TodoItem(**t) for tid, t in data.get("todos", {}).items()}
                self._active_task = data.get("active_task", "")
            except Exception:
                pass

    def _save_state(self) -> None:
        """Save working memory state."""
        state_file = self.state_dir / "state.json"
        state_file.write_text(
            json.dumps(
                {
                    "active_task": self._active_task,
                    "todos": {
                        tid: {
                            "id": t.id,
                            "content": t.content,
                            "status": t.status.value,
                            "parent_id": t.parent_id,
                            "children": t.children,
                            "notes": t.notes,
                            "created_at": t.created_at,
                            "updated_at": t.updated_at,
                            "completed_at": t.completed_at,
                        }
                        for tid, t in self._todos.items()
                    },
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def create_todo(self, content: str, parent_id: Optional[str] = None) -> str:
        """Create a new todo item."""
        todo_id = f"todo-{int(time.time())}-{len(self._todos)}"
        now = datetime.now().isoformat()
        todo = TodoItem(
            id=todo_id,
            content=content,
            parent_id=parent_id,
            created_at=now,
            updated_at=now,
        )
        self._todos[todo_id] = todo

        # Add to parent's children
        if parent_id and parent_id in self._todos:
            self._todos[parent_id].children.append(todo_id)

        self._save_state()
        log.info("[WorkingMemory] Created todo: %s", content[:100])
        return todo_id

    def update_todo(
        self,
        todo_id: str,
        status: Optional[TodoStatus] = None,
        notes: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Update a todo item."""
        todo = self._todos.get(todo_id)
        if not todo:
            return False

        now = datetime.now().isoformat()
        todo.updated_at = now

        if status is not None:
            todo.status = status
            if status in (TodoStatus.COMPLETED, TodoStatus.FAILED, TodoStatus.CANCELLED):
                todo.completed_at = now

        if notes is not None:
            todo.notes = notes

        if content is not None:
            todo.content = content

        self._save_state()
        return True

    def get_progress(self) -> Dict[str, Any]:
        """Get overall progress statistics."""
        if not self._todos:
            return {"total": 0, "completed": 0, "pending": 0, "in_progress": 0, "failed": 0, "progress_pct": 0.0}

        total = len(self._todos)
        completed = sum(1 for t in self._todos.values() if t.status == TodoStatus.COMPLETED)
        in_progress = sum(1 for t in self._todos.values() if t.status == TodoStatus.IN_PROGRESS)
        pending = sum(1 for t in self._todos.values() if t.status == TodoStatus.PENDING)
        failed = sum(1 for t in self._todos.values() if t.status == TodoStatus.FAILED)

        # Progress is weighted: completed = 100%, in_progress = 50%
        progress_pct = ((completed * 1.0 + in_progress * 0.5) / total * 100) if total > 0 else 0.0

        return {
            "total": total,
            "completed": completed,
            "in_progress": in_progress,
            "pending": pending,
            "failed": failed,
            "progress_pct": round(progress_pct, 1),
        }

    def get_todos(self, status: Optional[TodoStatus] = None) -> List[TodoItem]:
        """Get todos, optionally filtered by status."""
        todos = list(self._todos.values())
        if status:
            todos = [t for t in todos if t.status == status]
        return sorted(todos, key=lambda t: t.created_at)

    def format_todos(self, indent: int = 0) -> str:
        """Format todos as a readable tree."""
        lines = []
        root_todos = [t for t in self._todos.values() if t.parent_id is None]

        for todo in root_todos:
            lines.append(self._format_todo_tree(todo, indent))

        progress = self.get_progress()
        lines.append(
            f"\n**Progress**: {progress['progress_pct']}% ({progress['completed']}/{progress['total']} completed)"
        )

        return "\n".join(lines)

    def _format_todo_tree(self, todo: TodoItem, indent: int) -> str:
        """Format a single todo and its children as a tree."""
        status_icon = {
            TodoStatus.PENDING: "⬜",
            TodoStatus.IN_PROGRESS: "🔄",
            TodoStatus.COMPLETED: "✅",
            TodoStatus.FAILED: "❌",
            TodoStatus.CANCELLED: "⏹️",
        }.get(todo.status, "❓")

        prefix = "  " * indent
        line = f"{prefix}{status_icon} {todo.content}"
        if todo.notes:
            line += f"\n{prefix}   _{todo.notes}_"

        lines = [line]
        for child_id in todo.children:
            child = self._todos.get(child_id)
            if child:
                lines.append(self._format_todo_tree(child, indent + 1))

        return "\n".join(lines)

    def clear_completed(self) -> int:
        """Clear completed and cancelled todos."""
        before = len(self._todos)
        self._todos = {
            tid: t for tid, t in self._todos.items() if t.status not in (TodoStatus.COMPLETED, TodoStatus.CANCELLED)
        }
        cleared = before - len(self._todos)
        if cleared > 0:
            self._save_state()
        return cleared

    def get_stats(self) -> Dict[str, Any]:
        """Get working memory statistics."""
        return {
            **self.get_progress(),
            "active_task": self._active_task,
            "total_todos_created": len(self._todos),
        }


# Global working memory instance
_memory: Optional[WorkingMemory] = None


def get_working_memory(repo_dir: Optional[pathlib.Path] = None) -> WorkingMemory:
    """Get or create the global working memory."""
    global _memory
    if _memory is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _memory = WorkingMemory(repo_dir)
    return _memory
