"""
Ouroboros — Tool Orchestrator.

Coordinates multiple tool calls with dependency tracking and execution ordering.
Inspired by claw-code's tool orchestration layer.

Features:
- Dependency graph between tool calls
- Parallel execution of independent tools
- Sequential execution when dependencies exist
- Result chaining (output of one tool feeds into another)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


class ToolCallStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ToolCall:
    call_id: str
    tool_name: str
    args: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    status: ToolCallStatus = ToolCallStatus.PENDING
    result: Optional[str] = None
    error: Optional[str] = None
    started_at: str = ""
    completed_at: str = ""
    duration_ms: int = 0


@dataclass
class OrchestrationPlan:
    calls: List[ToolCall]
    execution_order: List[List[str]]  # Groups of call_ids that can run in parallel
    total_calls: int = 0
    parallel_groups: int = 0


class ToolOrchestrator:
    """Orchestrates multiple tool calls with dependency tracking."""

    def __init__(self):
        self._calls: Dict[str, ToolCall] = {}
        self._execution_history: List[Dict[str, Any]] = []

    def add_call(
        self, call_id: str, tool_name: str, args: Dict[str, Any], depends_on: Optional[List[str]] = None
    ) -> None:
        self._calls[call_id] = ToolCall(
            call_id=call_id,
            tool_name=tool_name,
            args=args,
            depends_on=depends_on or [],
        )

    def build_plan(self) -> OrchestrationPlan:
        remaining = set(self._calls.keys())
        execution_order = []
        visited: Set[str] = set()

        while remaining:
            ready = []
            for call_id in remaining:
                deps = set(self._calls[call_id].depends_on)
                if deps <= visited:
                    ready.append(call_id)

            if not ready:
                log.warning("Circular dependency detected in tool calls")
                ready = list(remaining)

            execution_order.append(ready)
            visited.update(ready)
            remaining -= set(ready)

        return OrchestrationPlan(
            calls=list(self._calls.values()),
            execution_order=execution_order,
            total_calls=len(self._calls),
            parallel_groups=len(execution_order),
        )

    def get_ready_calls(self) -> List[ToolCall]:
        completed = {cid for cid, c in self._calls.items() if c.status == ToolCallStatus.COMPLETED}
        ready = []
        for call in self._calls.values():
            if call.status != ToolCallStatus.PENDING:
                continue
            if set(call.depends_on) <= completed:
                ready.append(call)
        return ready

    def mark_completed(self, call_id: str, result: str) -> None:
        if call_id in self._calls:
            self._calls[call_id].status = ToolCallStatus.COMPLETED
            self._calls[call_id].result = result
            self._calls[call_id].completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def mark_failed(self, call_id: str, error: str) -> None:
        if call_id in self._calls:
            self._calls[call_id].status = ToolCallStatus.FAILED
            self._calls[call_id].error = error
            self._calls[call_id].completed_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    def get_dependent_args(self, call_id: str) -> Dict[str, Any]:
        result_args = {}
        call = self._calls.get(call_id)
        if not call:
            return result_args
        for dep_id in call.depends_on:
            dep = self._calls.get(dep_id)
            if dep and dep.result:
                result_args[f"_{dep_id}_result"] = dep.result
        return result_args

    def plan_summary(self) -> str:
        plan = self.build_plan()
        lines = [
            f"## Orchestration Plan ({plan.total_calls} calls, {plan.parallel_groups} groups)",
        ]
        for i, group in enumerate(plan.execution_order):
            lines.append(f"\n### Group {i + 1} (parallel: {len(group)})")
            for call_id in group:
                call = self._calls[call_id]
                deps = f" (depends on: {', '.join(call.depends_on)})" if call.depends_on else ""
                lines.append(f"- `{call_id}`: {call.tool_name}{deps}")
        return "\n".join(lines)

    def status_summary(self) -> str:
        by_status = {}
        for call in self._calls.values():
            by_status.setdefault(call.status.value, []).append(call)

        lines = ["## Tool Call Status"]
        for status in ToolCallStatus:
            calls = by_status.get(status.value, [])
            if calls:
                lines.append(f"\n### {status.value.title()} ({len(calls)})")
                for c in calls[:10]:
                    lines.append(f"- `{c.call_id}`: {c.tool_name}")
        return "\n".join(lines)

    def reset(self) -> None:
        self._calls.clear()


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _orchestrators: Dict[str, ToolOrchestrator] = {}

    def _get_orchestrator(repo_dir) -> ToolOrchestrator:
        key = str(repo_dir)
        if key not in _orchestrators:
            _orchestrators[key] = ToolOrchestrator()
        return _orchestrators[key]

    def orchestrator_add(ctx, call_id: str, tool_name: str, depends_on: str = "") -> str:
        orch = _get_orchestrator(ctx.repo_dir)
        deps = [d.strip() for d in depends_on.split(",") if d.strip()] if depends_on else []
        orch.add_call(call_id, tool_name, {}, deps)
        return f"Added tool call '{call_id}' ({tool_name})"

    def orchestrator_plan(ctx) -> str:
        return _get_orchestrator(ctx.repo_dir).plan_summary()

    def orchestrator_status(ctx) -> str:
        return _get_orchestrator(ctx.repo_dir).status_summary()

    def orchestrator_reset(ctx) -> str:
        _get_orchestrator(ctx.repo_dir).reset()
        return "Orchestrator reset"

    return [
        ToolEntry(
            "orchestrator_add",
            {
                "name": "orchestrator_add",
                "description": "Add a tool call to the orchestration plan with optional dependencies.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "call_id": {"type": "string", "description": "Unique call identifier"},
                        "tool_name": {"type": "string", "description": "Tool to call"},
                        "depends_on": {
                            "type": "string",
                            "default": "",
                            "description": "Comma-separated call_ids this depends on",
                        },
                    },
                    "required": ["call_id", "tool_name"],
                },
            },
            orchestrator_add,
        ),
        ToolEntry(
            "orchestrator_plan",
            {
                "name": "orchestrator_plan",
                "description": "View the current orchestration plan with execution order.",
                "parameters": {"type": "object", "properties": {}},
            },
            orchestrator_plan,
        ),
        ToolEntry(
            "orchestrator_status",
            {
                "name": "orchestrator_status",
                "description": "Get status of all tool calls in the orchestration.",
                "parameters": {"type": "object", "properties": {}},
            },
            orchestrator_status,
        ),
        ToolEntry(
            "orchestrator_reset",
            {
                "name": "orchestrator_reset",
                "description": "Reset the orchestrator for a new batch of tool calls.",
                "parameters": {"type": "object", "properties": {}},
            },
            orchestrator_reset,
        ),
    ]
