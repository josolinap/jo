"""
Goal Manager — Autonomous goal pursuit for Jo.

Implements the /goal and /loop pattern:
- /goal: Set a high-level goal with a done-condition
- /loop: Continue working toward the goal across sessions

This is the key mechanism that moves Jo from Level 3 (can modify code when asked)
to Level 4 (autonomous evolution cycles) on the self-evolution spectrum.

Architecture (inspired by Claude Code /goal + /loop, Devin, and the Ralph loop):

1. User or Jo sets a goal via `goal_set(description, done_condition)`
2. Goal is persisted to memory/TASK.md (git-tracked, survives CI runs)
3. Each CI run, Jo calls `goal_resume()` to load the active goal
4. Jo works toward the goal using existing tools
5. Jo calls `goal_check_progress()` to evaluate if done-condition is met
6. When done-condition is met, Jo calls `goal_complete()`
7. If stuck (no progress after N attempts), Jo calls `goal_stuck()`

The done-condition is CRITICAL — it's the termination criterion.
Without it, Jo would loop forever. The done-condition is a simple
boolean expression that Jo evaluates:
- "tests pass and no bare except blocks"
- "vault has < 20 stub notes"
- "repo_pack tool exists and has > 30 tests"
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

TASK_FILE = pathlib.Path("memory/TASK.md")
GOAL_HISTORY = pathlib.Path("memory/goal_history.jsonl")


@dataclass
class Goal:
    """A single goal with done-condition."""
    description: str
    done_condition: str  # What does "done" look like?
    created_at: str
    status: str = "active"  # active | completed | abandoned | stuck
    attempts: int = 0
    max_attempts: int = 10
    last_progress: Optional[str] = None  # ISO timestamp of last progress
    subtasks: List[str] = field(default_factory=list)
    completed_subtasks: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def goal_set(description: str, done_condition: str, subtasks: Optional[List[str]] = None) -> str:
    """Set a new goal. Replaces any existing active goal.

    Args:
        description: What Jo should achieve (high-level)
        done_condition: How Jo knows it's done (evaluable condition)
        subtasks: Optional list of subtasks to break the goal into steps

    Returns:
        Confirmation message
    """
    # Abandon any existing goal
    if TASK_FILE.exists():
        old = _read_task_file()
        if old and old.get("status") == "active":
            _append_history({**old, "status": "abandoned", "abandoned_at": _now_iso()})

    goal = Goal(
        description=description,
        done_condition=done_condition,
        created_at=_now_iso(),
        subtasks=subtasks or [],
    )

    _write_task_file(goal)
    return f"✓ Goal set: {description}\nDone when: {done_condition}\nSubtasks: {len(goal.subtasks)}"


def goal_resume() -> str:
    """Load the active goal at session start. Called by Jo on each CI run.

    Returns:
        Goal description if active, or "No active goal" message.
    """
    if not TASK_FILE.exists():
        return "No active goal. Use goal_set to create one."

    goal_data = _read_task_file()
    if not goal_data:
        return "No active goal."

    goal = Goal(**goal_data)

    if goal.status != "active":
        return f"Goal status: {goal.status}. No active goal to resume."

    # Increment attempt counter
    goal.attempts += 1
    goal.last_progress = _now_iso()
    _write_task_file(goal)

    lines = [
        f"## Active Goal (attempt {goal.attempts}/{goal.max_attempts})",
        f"**Description**: {goal.description}",
        f"**Done when**: {goal.done_condition}",
        "",
    ]

    if goal.subtasks:
        lines.append("### Subtasks:")
        for i, sub in enumerate(goal.subtasks):
            status = "✓" if sub in goal.completed_subtasks else "○"
            lines.append(f"  {status} {sub}")
        lines.append("")

    if goal.notes:
        lines.append("### Notes:")
        for note in goal.notes[-5:]:  # Last 5 notes
            lines.append(f"  - {note}")
        lines.append("")

    lines.append(f"_Set at: {goal.created_at}_")

    return "\n".join(lines)


def goal_check_progress(evaluation: str, is_done: bool = False) -> str:
    """Evaluate progress toward the goal.

    Jo calls this after each attempt to record what happened.

    Args:
        evaluation: Jo's assessment of current progress
        is_done: True if Jo believes the done-condition is met

    Returns:
        Next steps message
    """
    if not TASK_FILE.exists():
        return "No active goal."

    goal_data = _read_task_file()
    if not goal_data:
        return "No active goal."

    goal = Goal(**goal_data)
    goal.notes.append(f"[{_now_iso()}] {evaluation}")
    goal.last_progress = _now_iso()

    if is_done:
        goal.status = "completed"
        _write_task_file(goal)
        _append_history({**asdict(goal), "completed_at": _now_iso()})
        return f"✓ Goal completed!\n{evaluation}\n\nUse goal_set to start a new goal."

    # Check if stuck
    if goal.attempts >= goal.max_attempts:
        goal.status = "stuck"
        _write_task_file(goal)
        _append_history({**asdict(goal), "stuck_at": _now_iso()})
        return (f"⚠️ Goal stuck after {goal.attempts} attempts.\n"
                f"Last evaluation: {evaluation}\n\n"
                f"Consider: abandoning the goal, breaking it into smaller subtasks, "
                f"or asking the owner for help.")

    _write_task_file(goal)
    remaining = goal.max_attempts - goal.attempts
    return (f"Progress recorded ({remaining} attempts remaining).\n"
            f"Continue working toward: {goal.description}")


def goal_complete_subtask(subtask: str) -> str:
    """Mark a subtask as completed.

    Args:
        subtask: The subtask text to mark as done

    Returns:
        Confirmation message
    """
    if not TASK_FILE.exists():
        return "No active goal."

    goal_data = _read_task_file()
    if not goal_data:
        return "No active goal."

    goal = Goal(**goal_data)

    if subtask not in goal.completed_subtasks:
        goal.completed_subtasks.append(subtask)
        goal.notes.append(f"[{_now_iso()}] Completed subtask: {subtask}")
        _write_task_file(goal)

    remaining = len(goal.subtasks) - len(goal.completed_subtasks)
    return f"✓ Subtask completed: {subtask}\n{remaining} subtasks remaining."


def goal_abandon(reason: str = "") -> str:
    """Abandon the current goal.

    Args:
        reason: Why the goal is being abandoned

    Returns:
        Confirmation message
    """
    if not TASK_FILE.exists():
        return "No active goal."

    goal_data = _read_task_file()
    if not goal_data:
        return "No active goal."

    goal = Goal(**goal_data)
    goal.status = "abandoned"
    goal.notes.append(f"[{_now_iso()}] Abandoned: {reason}")
    _write_task_file(goal)
    _append_history({**asdict(goal), "abandoned_at": _now_iso(), "reason": reason})

    return f"Goal abandoned: {goal.description}\nReason: {reason}"


def goal_status() -> str:
    """Get the current goal status without modifying it.

    Returns:
        Status summary
    """
    if not TASK_FILE.exists():
        return "No active goal."

    goal_data = _read_task_file()
    if not goal_data:
        return "No active goal."

    goal = Goal(**goal_data)
    completed = len(goal.completed_subtasks)
    total = len(goal.subtasks)

    return (f"Goal: {goal.description}\n"
            f"Status: {goal.status}\n"
            f"Attempts: {goal.attempts}/{goal.max_attempts}\n"
            f"Subtasks: {completed}/{total}\n"
            f"Done when: {goal.done_condition}")


# ═══════════════════════════════════════════════════════════════════════
# Internal helpers
# ═══════════════════════════════════════════════════════════════════════

def _read_task_file() -> Optional[Dict[str, Any]]:
    """Read goal from memory/TASK.md (JSON-embedded markdown)."""
    try:
        content = TASK_FILE.read_text(encoding="utf-8")
        # Extract JSON from markdown code block
        import re
        match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        # Try plain JSON
        return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def _write_task_file(goal: Goal) -> None:
    """Write goal to memory/TASK.md as markdown with embedded JSON."""
    TASK_FILE.parent.mkdir(parents=True, exist_ok=True)

    goal_json = json.dumps(asdict(goal), indent=2, ensure_ascii=False)

    content = f"""# Active Task

> This file tracks Jo's current autonomous goal. It persists across CI runs.

## Goal

**Description**: {goal.description}

**Done when**: {goal.done_condition}

**Status**: {goal.status}

**Attempts**: {goal.attempts}/{goal.max_attempts}

## Subtasks

"""

    for sub in goal.subtasks:
        status = "✓" if sub in goal.completed_subtasks else "○"
        content += f"- {status} {sub}\n"

    if goal.notes:
        content += "\n## Progress Log\n\n"
        for note in goal.notes[-10:]:  # Last 10 notes
            content += f"- {note}\n"

    content += f"\n## Goal Data (JSON)\n\n```json\n{goal_json}\n```\n"

    TASK_FILE.write_text(content, encoding="utf-8")


def _append_history(entry: Dict[str, Any]) -> None:
    """Append a goal to history."""
    GOAL_HISTORY.parent.mkdir(parents=True, exist_ok=True)
    with open(GOAL_HISTORY, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
