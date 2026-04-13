"""
Jo — Task DAG Orchestrator.

Inspired by open-multi-agent's runTeam() - auto task decomposition,
dependency resolution, and parallel execution.
"""

from __future__ import annotations

import json
import logging
import pathlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class TaskNode:
    """A node in the task DAG."""

    task_id: str
    description: str
    assignee: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    depends_on: List[str] = field(default_factory=list)
    blocks: List[str] = field(default_factory=list)
    result: str = ""
    error: str = ""
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 2
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentConfig:
    """Configuration for a team agent."""

    name: str
    role: str
    goal: str
    instructions: str
    tools: List[str] = field(default_factory=list)
    model: Optional[str] = None
    max_steps: int = 50


@dataclass
class TeamConfig:
    """Configuration for a team of agents."""

    name: str
    agents: List[AgentConfig] = field(default_factory=list)
    shared_memory: bool = True
    max_parallel: int = 3


class TaskDAG:
    """Task dependency graph with auto-resolution."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.tasks: Dict[str, TaskNode] = {}
        self.state_file = repo_dir / ".jo_state" / "task_dag" / "state.json"
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_state()

    def add_task(
        self,
        description: str,
        depends_on: Optional[List[str]] = None,
        blocks: Optional[List[str]] = None,
        priority: TaskPriority = TaskPriority.NORMAL,
    ) -> str:
        """Add a task to the DAG."""
        task_id = f"task-{len(self.tasks) + 1}-{uuid.uuid4().hex[:6]}"
        task = TaskNode(
            task_id=task_id,
            description=description,
            depends_on=depends_on or [],
            blocks=blocks or [],
            priority=priority,
        )
        self.tasks[task_id] = task
        self._save_state()
        return task_id

    def get_ready_tasks(self) -> List[TaskNode]:
        """Get tasks that are ready to run (all dependencies complete)."""
        ready = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_complete = all(
                self.tasks.get(dep_id, TaskNode(task_id="", description="")).status == TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )

            if deps_complete:
                ready.append(task)

        # Sort by priority (higher first)
        ready.sort(key=lambda t: t.priority.value, reverse=True)
        return ready

    def get_blocked_tasks(self) -> List[TaskNode]:
        """Get tasks that are blocked by incomplete dependencies."""
        blocked = []
        for task in self.tasks.values():
            if task.status != TaskStatus.PENDING:
                continue

            # Check if any dependency is not completed
            deps_incomplete = any(
                self.tasks.get(dep_id, TaskNode(task_id="", description="")).status != TaskStatus.COMPLETED
                for dep_id in task.depends_on
            )

            if deps_incomplete:
                blocked.append(task)

        return blocked

    def start_task(self, task_id: str) -> bool:
        """Mark task as running."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now().isoformat()
        self._save_state()
        return True

    def complete_task(self, task_id: str, result: str) -> bool:
        """Mark task as completed."""
        task = self.tasks.get(task_id)
        if not task:
            return False
        task.status = TaskStatus.COMPLETED
        task.result = result
        task.completed_at = datetime.now().isoformat()
        self._save_state()
        return True

    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark task as failed."""
        task = self.tasks.get(task_id)
        if not task:
            return False

        # Check for retry
        if task.retry_count < task.max_retries:
            task.retry_count += 1
            task.status = TaskStatus.PENDING
            task.error = f"Retry {task.retry_count}/{task.max_retries}: {error}"
            self._save_state()
            return True

        task.status = TaskStatus.FAILED
        task.error = error
        task.completed_at = datetime.now().isoformat()
        self._save_state()
        return True

    def is_complete(self) -> bool:
        """Check if all tasks are complete or failed."""
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in self.tasks.values())

    def is_blocked(self) -> bool:
        """Check if all pending tasks are blocked."""
        pending = [t for t in self.tasks.values() if t.status == TaskStatus.PENDING]
        if not pending:
            return False
        return all(
            any(
                self.tasks.get(dep_id, TaskNode(task_id="", description="")).status != TaskStatus.COMPLETED
                for dep_id in t.depends_on
            )
            for t in pending
        )

    def get_status_summary(self) -> str:
        """Get a summary of task status."""
        stats = {s: 0 for s in TaskStatus}
        for task in self.tasks.values():
            stats[task.status] += 1

        lines = ["## Task DAG Status\n"]
        lines.append(f"Total tasks: {len(self.tasks)}")
        for status, count in stats.items():
            if count > 0:
                lines.append(f"- {status.value}: {count}")

        # Show ready and blocked
        ready = self.get_ready_tasks()
        blocked = self.get_blocked_tasks()
        lines.append(f"\n**Ready to run: {len(ready)}**")
        lines.append(f"**Blocked: {len(blocked)}**")

        return "\n".join(lines)

    def _save_state(self) -> None:
        """Save state to file."""
        data = {
            "tasks": {
                tid: {
                    "task_id": t.task_id,
                    "description": t.description,
                    "assignee": t.assignee,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "depends_on": t.depends_on,
                    "blocks": t.blocks,
                    "result": t.result,
                    "error": t.error,
                    "started_at": t.started_at,
                    "completed_at": t.completed_at,
                    "retry_count": t.retry_count,
                    "max_retries": t.max_retries,
                    "metadata": t.metadata,
                }
                for tid, t in self.tasks.items()
            }
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def _load_state(self) -> None:
        """Load state from file."""
        if not self.state_file.exists():
            return

        try:
            data = json.loads(self.state_file.read_text())
            for tid, tdata in data.get("tasks", {}).items():
                self.tasks[tid] = TaskNode(
                    task_id=tdata["task_id"],
                    description=tdata["description"],
                    assignee=tdata.get("assignee"),
                    status=TaskStatus(tdata["status"]),
                    priority=TaskPriority(tdata["priority"]),
                    depends_on=tdata.get("depends_on", []),
                    blocks=tdata.get("blocks", []),
                    result=tdata.get("result", ""),
                    error=tdata.get("error", ""),
                    started_at=tdata.get("started_at"),
                    completed_at=tdata.get("completed_at"),
                    retry_count=tdata.get("retry_count", 0),
                    max_retries=tdata.get("max_retries", 2),
                    metadata=tdata.get("metadata", {}),
                )
        except Exception as e:
            log.warning(f"Failed to load task DAG state: {e}")


class TeamOrchestrator:
    """Multi-agent team orchestrator - inspired by open-multi-agent's runTeam()."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.dag = TaskDAG(repo_dir)
        self.teams: Dict[str, TeamConfig] = {}
        self.message_bus: Dict[str, List[Dict[str, Any]]] = {}

    def create_team(
        self,
        name: str,
        agents: Optional[List[AgentConfig]] = None,
        shared_memory: bool = True,
    ) -> TeamConfig:
        """Create a team of agents."""
        team = TeamConfig(
            name=name,
            agents=agents or [],
            shared_memory=shared_memory,
        )
        self.teams[name] = team
        self.message_bus[name] = []
        return team

    def decompose_goal(self, goal: str) -> List[Dict[str, Any]]:
        """Auto-decompose a goal into tasks with dependencies."""
        # This would ideally use an LLM to decompose
        # For now, return a simple structure
        tasks = []

        # Common patterns
        if "research" in goal.lower():
            tasks.append(
                {
                    "description": "Research the topic",
                    "depends_on": [],
                }
            )

        if "implement" in goal.lower() or "build" in goal.lower():
            tasks.append(
                {
                    "description": "Implement the solution",
                    "depends_on": ["research"],
                }
            )

        if "test" in goal.lower():
            tasks.append(
                {
                    "description": "Test the implementation",
                    "depends_on": ["implement"],
                }
            )

        if "review" in goal.lower():
            tasks.append(
                {
                    "description": "Review the code",
                    "depends_on": ["implement"],
                }
            )

        # Default: single task
        if not tasks:
            tasks.append(
                {
                    "description": goal,
                    "depends_on": [],
                }
            )

        return tasks

    def run_team(
        self,
        team_name: str,
        goal: str,
        auto_decompose: bool = True,
    ) -> Dict[str, Any]:
        """Run a team towards a goal - similar to open-multi-agent's runTeam()."""
        if team_name not in self.teams:
            return {"error": f"Team '{team_name}' not found"}

        team = self.teams[team_name]

        # Decompose goal into tasks
        if auto_decompose:
            task_specs = self.decompose_goal(goal)
            task_ids = []

            for spec in task_specs:
                task_id = self.dag.add_task(
                    description=spec["description"],
                    depends_on=[],  # Will link after creation
                )
                task_ids.append(task_id)

            # Link dependencies
            for i, task_id in enumerate(task_ids):
                if i > 0:
                    self.dag.tasks[task_id].depends_on = [task_ids[i - 1]]

        return {
            "team": team_name,
            "goal": goal,
            "task_count": len(self.dag.tasks),
            "status": "initiated",
        }

    def get_team_status(self, team_name: str) -> str:
        """Get status of a team."""
        if team_name not in self.teams:
            return f"Team '{team_name}' not found"

        team = self.teams[team_name]
        lines = [f"## Team: {team.name}\n"]

        for agent in team.agents:
            lines.append(f"- **{agent.name}** ({agent.role}): {agent.goal}")

        lines.append(f"\n{self.dag.get_status_summary()}")

        return "\n".join(lines)

    def get_dag(self) -> TaskDAG:
        """Get the task DAG."""
        return self.dag


# Singleton instance
_orchestrator: Optional[TeamOrchestrator] = None


def get_orchestrator(repo_dir: pathlib.Path) -> TeamOrchestrator:
    """Get or create the team orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = TeamOrchestrator(repo_dir)
    return _orchestrator
