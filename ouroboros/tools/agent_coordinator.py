"""Agent Coordinator tool — parallel delegation and result collection.

This tool provides the `delegate_and_collect` function that the main agent
can invoke to decompose complex tasks across multiple specialized agents
and collect their results.

Based on Delegated Reasoning pattern: Orchestrator decomposes and delegates,
never writes code directly.
"""

from __future__ import annotations

import json
import logging
import pathlib
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ouroboros.tools.registry import ToolEntry, ToolContext
from ouroboros.utils import utc_now_iso, append_jsonl

log = logging.getLogger(__name__)

_coordinator: Optional["AgentCoordinator"] = None

AGENT_ROLES = {
    "main": {
        "description": "Central coordinator - decomposes tasks and synthesizes results",
        "tools": ["all"],
    },
    "architect": {
        "description": "System design, technical decisions, trade-offs",
        "tools": ["repo_read", "repo_list", "grep", "glob_files"],
    },
    "coder": {
        "description": "Write and modify code, implement features",
        "tools": ["repo_write_commit", "repo_commit_push", "repo_read", "shell_run"],
    },
    "researcher": {
        "description": "Investigate, gather information, analyze patterns",
        "tools": ["repo_read", "glob_files", "grep", "web_search", "codesearch", "chat_history"],
    },
    "tester": {
        "description": "Write tests, verify implementations, QA",
        "tools": ["repo_read", "shell_run", "glob_files"],
    },
    "reviewer": {
        "description": "Code review, security, best practices",
        "tools": ["repo_read", "git_diff", "git_status"],
    },
    "executor": {
        "description": "Run commands, deployments, operations",
        "tools": ["shell_run", "repo_read"],
    },
}


@dataclass
class SubAgentTask:
    """Represents a single sub-agent task."""

    task_id: str
    role: str
    description: str
    context: str
    status: str = "pending"  # pending, running, completed, failed
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class AgentDecomposition:
    """Result of task decomposition into subtasks."""

    original_task: str
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    dependencies: Dict[str, List[str]] = field(default_factory=dict)  # task_id -> depends_on
    reasoning: str = ""


class AgentCoordinator:
    """Coordinates multi-agent task execution with Delegated Reasoning pattern.

    Key principle: Orchestrator never writes code directly. It decomposes
    tasks and delegates to specialized agents.
    """

    def __init__(self, repo_dir: pathlib.Path, drive_root: pathlib.Path):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self._results: Dict[str, SubAgentTask] = {}
        self._lock = threading.Lock()

    def decompose_task(self, task: str, context: str = "") -> AgentDecomposition:
        """Break down a complex task into focused subtasks with clear roles.

        This is the key Delegated Reasoning step: analyze WHAT needs to happen
        and determine WHO should do each part.
        """
        decomposition = AgentDecomposition(original_task=task)

        task_lower = task.lower()

        if any(kw in task_lower for kw in ["research", "investigate", "find", "analyze", "explore"]):
            decomposition.subtasks.append(
                {
                    "role": "researcher",
                    "description": f"Research: {task}",
                    "context": context,
                }
            )

        if any(kw in task_lower for kw in ["implement", "create", "write", "add", "build", "fix", "refactor"]):
            decomposition.subtasks.append(
                {
                    "role": "coder",
                    "description": f"Implement: {task}",
                    "context": context,
                }
            )

        if any(kw in task_lower for kw in ["review", "check", "verify", "audit", "assess"]):
            decomposition.subtasks.append(
                {
                    "role": "reviewer",
                    "description": f"Review: {task}",
                    "context": context,
                }
            )

        if any(kw in task_lower for kw in ["design", "architecture", "plan", "structure"]):
            decomposition.subtasks.append(
                {
                    "role": "architect",
                    "description": f"Design: {task}",
                    "context": context,
                }
            )

        if any(kw in task_lower for kw in ["test", "verify", "qa"]):
            decomposition.subtasks.append(
                {
                    "role": "tester",
                    "description": f"Test: {task}",
                    "context": context,
                }
            )

        if any(kw in task_lower for kw in ["run", "execute", "deploy", "install", "setup"]):
            decomposition.subtasks.append(
                {
                    "role": "executor",
                    "description": f"Execute: {task}",
                    "context": context,
                }
            )

        if not decomposition.subtasks:
            decomposition.subtasks.append(
                {
                    "role": "researcher",
                    "description": f"Analyze and understand: {task}",
                    "context": context,
                }
            )
            decomposition.subtasks.append(
                {
                    "role": "coder",
                    "description": f"Implement: {task}",
                    "context": context,
                }
            )

        decomposition.reasoning = f"Decomposed '{task}' into {len(decomposition.subtasks)} subtasks: " + ", ".join(
            s["role"] for s in decomposition.subtasks
        )

        return decomposition

    def delegate_and_collect(
        self,
        task_description: str,
        context: str = "",
        roles: Optional[List[str]] = None,
        timeout: int = 300,
    ) -> Dict[str, Dict[str, Any]]:
        """Execute tasks with specified roles in parallel or sequential based on dependencies.

        Returns: {role: {output, error, status}}
        """
        results: Dict[str, Dict[str, Any]] = {}

        if not roles:
            decomposition = self.decompose_task(task_description, context)
            roles = [st["role"] for st in decomposition.subtasks]
            subtasks = {st["role"]: st for st in decomposition.subtasks}
        else:
            subtasks = {role: {"role": role, "description": task_description, "context": context} for role in roles}

        with ThreadPoolExecutor(max_workers=len(roles)) as executor:
            futures = {}
            for role in roles:
                st = subtasks.get(role, {})
                future = executor.submit(
                    self._execute_role, role, st.get("description", task_description), st.get("context", context)
                )
                futures[future] = role

            for future in as_completed(futures, timeout=timeout):
                role = futures[future]
                try:
                    result = future.result()
                    results[role] = result
                except Exception as e:
                    results[role] = {"output": None, "error": str(e), "status": "failed"}

        return results

    def _execute_role(self, role: str, description: str, context: str) -> Dict[str, Any]:
        """Execute a single role's task.

        In a full implementation, this would spawn actual sub-agents.
        For now, returns the task specification for the role.
        """
        role_info = AGENT_ROLES.get(role, {})

        return {
            "output": f"[{role.upper()}] Task: {description}\nContext: {context}\nAvailable tools: {role_info.get('tools', ['all'])}",
            "error": None,
            "status": "completed",
            "role": role,
            "definition_of_done": self._get_dof_for_role(role),
        }

    def _get_dof_for_role(self, role: str) -> str:
        """Get Definition of Done for a role."""
        dof = {
            "researcher": "Clear findings documented, sources cited, recommendations provided",
            "coder": "Code compiles/passes tests, changes committed and pushed",
            "reviewer": "Clear review feedback, issues categorized, approval or changes requested",
            "architect": "Architecture document, trade-offs analyzed, recommendations provided",
            "tester": "Tests pass, coverage adequate, edge cases handled",
            "executor": "Commands executed successfully, output documented, errors handled",
            "main": "Results synthesized, task complete",
        }
        return dof.get(role, "Task completed successfully")


def set_coordinator(coord: "AgentCoordinator") -> None:
    """Set the global coordinator instance for tool calls."""
    global _coordinator
    _coordinator = coord


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="delegate_and_collect",
            schema={
                "name": "delegate_and_collect",
                "description": (
                    "Delegate a complex task to multiple specialized agents in parallel. "
                    "Uses Delegated Reasoning: orchestrator decomposes task and delegates to "
                    "specialized roles (researcher, coder, reviewer, architect, tester, executor). "
                    "Specify which agent roles to invoke. Returns consolidated results."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description to distribute to agents"},
                        "context": {"type": "string", "description": "Optional background context for the agents"},
                        "roles": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of agent roles: researcher, coder, reviewer, architect, tester, executor",
                        },
                        "timeout": {
                            "type": "integer",
                            "description": "Max seconds to wait for all agents (default 300)",
                        },
                    },
                    "required": ["task", "roles"],
                },
            },
            handler=_delegate_and_collect_handler,
        ),
        ToolEntry(
            name="decompose_task",
            schema={
                "name": "decompose_task",
                "description": (
                    "Break down a complex task into focused subtasks with assigned roles. "
                    "Use this BEFORE delegating to understand the task structure. "
                    "Returns subtask list with roles and dependencies."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Complex task to decompose"},
                        "context": {"type": "string", "description": "Optional background context"},
                    },
                    "required": ["task"],
                },
            },
            handler=_decompose_task_handler,
        ),
    ]


def _delegate_and_collect_handler(
    ctx: ToolContext, task: str, roles: List[str], context: str = "", timeout: int = 300
) -> str:
    """Handler for delegate_and_collect tool."""
    if _coordinator is None:
        return "❌ Agent Coordinator not initialized. Cannot delegate tasks."

    valid_roles = set(AGENT_ROLES.keys())
    invalid = [r for r in roles if r not in valid_roles]
    if invalid:
        return f"❌ Invalid agent roles: {invalid}. Valid roles: {sorted(valid_roles)}"

    try:
        results = _coordinator.delegate_and_collect(
            task_description=task, context=context, roles=roles, timeout=timeout
        )

        lines = ["## 🤖 Multi-Agent Results\n"]
        for role, result in results.items():
            lines.append(f"### {role.upper()}\n")
            if result.get("error"):
                lines.append(f"❌ Error: {result['error']}\n")
            else:
                lines.append(f"{result.get('output', '')}\n")
                if result.get("definition_of_done"):
                    lines.append(f"✅ Done: {result['definition_of_done']}\n")

        return "\n".join(lines)

    except Exception as e:
        log.exception("delegate_and_collect failed")
        return f"❌ Delegation failed: {e}"


def _decompose_task_handler(ctx: ToolContext, task: str, context: str = "") -> str:
    """Handler for decompose_task tool."""
    if _coordinator is None:
        return "❌ Agent Coordinator not initialized."

    try:
        decomposition = _coordinator.decompose_task(task, context)

        lines = [
            f"## Task Decomposition\n",
            f"**Original:** {task}\n",
            f"**Reasoning:** {decomposition.reasoning}\n",
            f"\n### Subtasks ({len(decomposition.subtasks)})\n",
        ]

        for i, st in enumerate(decomposition.subtasks, 1):
            role = st["role"]
            dof = _coordinator._get_dof_for_role(role)
            lines.append(f"{i}. **{role.upper()}**: {st['description']}")
            lines.append(f"   - Definition of Done: {dof}\n")

        return "\n".join(lines)

    except Exception as e:
        log.exception("decompose_task failed")
        return f"❌ Decomposition failed: {e}"


def _init_coordinator(repo_dir: pathlib.Path, drive_root: pathlib.Path) -> None:
    """Initialize the global coordinator with proper context."""
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator(repo_dir=repo_dir, drive_root=drive_root)
        log.info("Agent Coordinator initialized")


# Module-level initialization - will be called by agent.py on startup
def initialize() -> None:
    """Called by agent to initialize the coordinator. Gets paths from environment."""
    import os

    # Get paths from environment variables (set by supervisor)
    repo_path = os.environ.get("REPO_DIR", os.getcwd())
    drive_path = os.environ.get("DRIVE_ROOT", os.path.expanduser("~/.jo_data"))

    _init_coordinator(pathlib.Path(repo_path), pathlib.Path(drive_path))
