"""Task graph for Jo - executes complex tasks in dependency order."""

from __future__ import annotations

import logging
import os
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

log = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskNode:
    id: str
    description: str
    role: str = "default"
    dependencies: Set[str] = field(default_factory=set)
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskGraphResult:
    success: bool
    completed: int
    failed: int
    skipped: int
    results: Dict[str, Any]
    execution_order: List[str]


class TaskGraph:
    """Executes tasks in dependency order with parallel execution support."""

    def __init__(self):
        self.nodes: Dict[str, TaskNode] = {}
        self._dependents: Dict[str, Set[str]] = defaultdict(set)

    def add_task(
        self,
        description: str,
        dependencies: Optional[List[str]] = None,
        role: str = "default",
    ) -> str:
        """Add a task with optional dependencies."""
        task_id = str(uuid.uuid4())[:8]
        deps = set(dependencies or [])

        self.nodes[task_id] = TaskNode(
            id=task_id,
            description=description,
            role=role,
            dependencies=deps,
        )

        for dep in deps:
            self._dependents[dep].add(task_id)

        return task_id

    def get_ready_tasks(self) -> List[TaskNode]:
        """Get tasks that are ready to execute (all deps done)."""
        ready = []
        for node in self.nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            if all(self.nodes[dep].status == TaskStatus.DONE for dep in node.dependencies):
                ready.append(node)
        return ready

    def mark_running(self, task_id: str) -> None:
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.RUNNING

    def mark_done(self, task_id: str, result: Any = None) -> None:
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.DONE
            self.nodes[task_id].result = result

    def mark_failed(self, task_id: str, error: str) -> None:
        if task_id in self.nodes:
            self.nodes[task_id].status = TaskStatus.FAILED
            self.nodes[task_id].error = error

    def get_blocked_tasks(self) -> List[TaskNode]:
        """Get tasks blocked by failures."""
        blocked = []
        for node in self.nodes.values():
            if node.status != TaskStatus.PENDING:
                continue
            for dep in node.dependencies:
                if self.nodes[dep].status == TaskStatus.FAILED:
                    node.status = TaskStatus.SKIPPED
                    node.error = f"Blocked by failed dependency: {dep}"
                    blocked.append(node)
                    break
        return blocked

    def get_topo_order(self) -> List[TaskNode]:
        """Return topological order of tasks."""
        visited: Set[str] = set()
        order: List[TaskNode] = []

        def visit(node_id: str) -> None:
            if node_id in visited:
                return
            visited.add(node_id)
            node = self.nodes[node_id]
            for dep in sorted(node.dependencies):
                visit(dep)
            order.append(node)

        for node_id in sorted(self.nodes.keys()):
            visit(node_id)

        return order

    def get_parallel_groups(self) -> List[List[TaskNode]]:
        """Group tasks that can run in parallel."""
        groups: List[List[TaskNode]] = []
        remaining = set(self.nodes.keys())

        while remaining:
            ready = []
            for node_id in list(remaining):
                node = self.nodes[node_id]
                if node.status != TaskStatus.PENDING:
                    continue
                if all(dep not in remaining or self.nodes[dep].status == TaskStatus.DONE for dep in node.dependencies):
                    ready.append(node)

            if not ready:
                break

            groups.append(ready)
            for node in ready:
                remaining.discard(node.id)

        return groups

    def is_complete(self) -> bool:
        """Check if all tasks are done or skipped."""
        for node in self.nodes.values():
            if node.status == TaskStatus.PENDING or node.status == TaskStatus.RUNNING:
                return False
        return True

    def get_stats(self) -> Dict[str, int]:
        """Get execution statistics."""
        stats = {
            "total": len(self.nodes),
            "pending": 0,
            "running": 0,
            "done": 0,
            "failed": 0,
            "skipped": 0,
        }
        for node in self.nodes.values():
            stats[node.status.value] += 1
        return stats

    def format_summary(self) -> str:
        """Format task graph summary."""
        stats = self.get_stats()

        lines = [
            "## Task Graph Summary",
            f"- Total tasks: {stats['total']}",
            f"- Completed: {stats['done']}",
            f"- Failed: {stats['failed']}",
            f"- Skipped: {stats['skipped']}",
        ]

        if stats["failed"] > 0:
            lines.append("")
            lines.append("### Failed Tasks")
            for node in self.nodes.values():
                if node.status == TaskStatus.FAILED:
                    lines.append(f"- {node.description}: {node.error[:100]}")

        return "\n".join(lines)


def decompose_into_graph(task: str) -> Optional[TaskGraph]:
    """Decompose a complex task into a task graph using simple heuristics."""
    task_lower = task.lower()

    if any(kw in task_lower for kw in ["analyze", "fix", "implement"]):
        graph = TaskGraph()

        analyze_id = graph.add_task(
            description="Analyze requirements and understand the task",
            role="analyzer",
        )

        plan_id = graph.add_task(
            description="Plan the implementation approach",
            role="planner",
            dependencies=[analyze_id],
        )

        implement_id = graph.add_task(
            description="Implement the changes",
            role="coder",
            dependencies=[plan_id],
        )

        test_id = graph.add_task(
            description="Test the implementation",
            role="tester",
            dependencies=[implement_id],
        )

        review_id = graph.add_task(
            description="Review and finalize",
            role="reviewer",
            dependencies=[test_id],
        )

        return graph

    return None


_graph: Optional[TaskGraph] = None


def get_active_graph() -> Optional[TaskGraph]:
    """Get the currently active task graph."""
    return _graph


def set_active_graph(graph: Optional[TaskGraph]) -> None:
    """Set the active task graph."""
    global _graph
    _graph = graph
