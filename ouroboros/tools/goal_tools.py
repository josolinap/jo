"""
Goal pursuit tools — /goal and /loop for Jo.

These tools let Jo set autonomous goals and pursue them across sessions.
This is the key mechanism for Level 4 self-evolution (autonomous evolution cycles).

Wiring:
- `goal_set` → Jo or user sets a goal with done-condition
- `goal_resume` → Jo calls this at session start to load active goal
- `goal_check_progress` → Jo calls this after each attempt
- `goal_complete_subtask` → Jo marks subtasks as done
- `goal_abandon` → Jo gives up on a goal
- `goal_status` → Jo checks current goal status

The goal is persisted to memory/TASK.md (git-tracked), so it survives
CI run boundaries. Each 5.5-hour run, Jo resumes the goal and continues.
"""

from __future__ import annotations

import logging
from typing import List

from ouroboros.goal_manager import (
    goal_set as _goal_set,
    goal_resume as _goal_resume,
    goal_check_progress as _goal_check_progress,
    goal_complete_subtask as _goal_complete_subtask,
    goal_abandon as _goal_abandon,
    goal_status as _goal_status,
)
from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)


def _goal_set_tool(ctx: ToolContext, description: str, done_condition: str, subtasks: str = "") -> str:
    """Set a new autonomous goal. Replaces any existing active goal.

    The done_condition is CRITICAL — it's how Jo knows when to stop.
    Write it as an evaluable condition, e.g.:
    - "all tests pass and no bare except blocks remain"
    - "vault has fewer than 20 stub notes"
    - "repo_pack tool exists with 30+ tests"

    Call goal_resume at the start of each session to load this goal.
    """
    subs = [s.strip() for s in subtasks.split("|") if s.strip()] if subtasks else []
    return _goal_set(description=description, done_condition=done_condition, subtasks=subs)


def _goal_resume_tool(ctx: ToolContext) -> str:
    """Load the active goal at session start.

    Call this at the beginning of each CI run to resume work on the
    active goal. Increments the attempt counter.
    """
    return _goal_resume()


def _goal_check_progress_tool(ctx: ToolContext, evaluation: str, is_done: bool = False) -> str:
    """Record progress toward the goal and check if done.

    Call this after each attempt to:
    1. Record what you tried and what happened
    2. Evaluate whether the done-condition is met
    3. Get guidance on next steps

    Set is_done=True ONLY when the done-condition is verifiably met.
    """
    return _goal_check_progress(evaluation=evaluation, is_done=is_done)


def _goal_complete_subtask_tool(ctx: ToolContext, subtask: str) -> str:
    """Mark a subtask as completed."""
    return _goal_complete_subtask(subtask=subtask)


def _goal_abandon_tool(ctx: ToolContext, reason: str = "") -> str:
    """Abandon the current goal. Use when the goal is no longer relevant
    or is impossible to achieve."""
    return _goal_abandon(reason=reason)


def _goal_status_tool(ctx: ToolContext) -> str:
    """Check the current goal status without modifying it."""
    return _goal_status()


def get_tools() -> List[ToolEntry]:
    """Register goal pursuit tools."""
    tools = []

    for name, desc, handler, params in [
        ("goal_set",
         "Set a new autonomous goal with a done-condition. The done_condition is how Jo knows when to stop — write it as an evaluable condition. Use | to separate subtasks.",
         _goal_set_tool,
         {
             "description": {"type": "string", "description": "What Jo should achieve (high-level goal)"},
             "done_condition": {"type": "string", "description": "How Jo knows it's done (evaluable condition, e.g. 'all tests pass and no bare except blocks')"},
             "subtasks": {"type": "string", "description": "Optional subtasks separated by | (e.g. 'fix imports|add tests|update docs')", "default": ""},
         }),
        ("goal_resume",
         "Load the active goal at session start. Call this at the beginning of each CI run to resume work.",
         _goal_resume_tool,
         {}),
        ("goal_check_progress",
         "Record progress toward the goal and check if done. Call after each attempt. Set is_done=True ONLY when done-condition is verifiably met.",
         _goal_check_progress_tool,
         {
             "evaluation": {"type": "string", "description": "Your assessment of current progress"},
             "is_done": {"type": "boolean", "default": False, "description": "True if done-condition is verifiably met"},
         }),
        ("goal_complete_subtask",
         "Mark a subtask as completed.",
         _goal_complete_subtask_tool,
         {"subtask": {"type": "string", "description": "The subtask text to mark as done"}}),
        ("goal_abandon",
         "Abandon the current goal. Use when goal is no longer relevant or impossible.",
         _goal_abandon_tool,
         {"reason": {"type": "string", "default": "", "description": "Why the goal is being abandoned"}}),
        ("goal_status",
         "Check current goal status without modifying it.",
         _goal_status_tool,
         {}),
    ]:
        tools.append(ToolEntry(
            name=name,
            schema={
                "name": name,
                "description": desc,
                "parameters": {
                    "type": "object",
                    "properties": params,
                },
            },
            handler=handler,
        ))

    return tools
