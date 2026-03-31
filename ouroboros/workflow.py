"""Workflow automation for repetitive tasks.

Inspired by Zotero Better Notes Actions & Tags:
action-based automation for common operations.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class WorkflowAction:
    """A single workflow action."""

    name: str
    description: str
    handler: Callable
    trigger: str  # on_task_complete, on_error, on_startup, manual
    enabled: bool = True


@dataclass
class WorkflowEngine:
    """Execute predefined actions on events.

    Automates repetitive tasks by running actions
    when specific triggers fire.

    Usage:
        engine = WorkflowEngine()
        engine.register("log_completion", log_task, trigger="on_task_complete")
        engine.trigger("on_task_complete", task_data)
    """

    actions: Dict[str, WorkflowAction] = field(default_factory=dict)
    _history: List[Dict[str, Any]] = field(default_factory=list)

    def register(
        self,
        name: str,
        handler: Callable,
        description: str = "",
        trigger: str = "manual",
    ) -> None:
        """Register a workflow action."""
        self.actions[name] = WorkflowAction(
            name=name,
            description=description,
            handler=handler,
            trigger=trigger,
        )

    def trigger(self, trigger: str, context: Optional[Dict[str, Any]] = None) -> List[Any]:
        """Trigger all actions matching a trigger event."""
        results = []

        for action in self.actions.values():
            if action.trigger == trigger and action.enabled:
                try:
                    result = action.handler(context or {})
                    results.append({"action": action.name, "result": result, "success": True})
                    self._history.append(
                        {
                            "action": action.name,
                            "trigger": trigger,
                            "success": True,
                        }
                    )
                except Exception as e:
                    log.warning(f"Workflow action '{action.name}' failed: {e}")
                    results.append({"action": action.name, "error": str(e), "success": False})
                    self._history.append(
                        {
                            "action": action.name,
                            "trigger": trigger,
                            "success": False,
                            "error": str(e),
                        }
                    )

        return results

    def run(self, name: str, context: Optional[Dict[str, Any]] = None) -> Any:
        """Run a specific action by name."""
        action = self.actions.get(name)
        if not action:
            raise ValueError(f"Unknown action: {name}")

        if not action.enabled:
            log.debug(f"Action '{name}' is disabled")
            return None

        return action.handler(context or {})

    def list_actions(self, trigger: Optional[str] = None) -> List[Dict[str, Any]]:
        """List registered actions."""
        actions = []
        for action in self.actions.values():
            if trigger is None or action.trigger == trigger:
                actions.append(
                    {
                        "name": action.name,
                        "description": action.description,
                        "trigger": action.trigger,
                        "enabled": action.enabled,
                    }
                )
        return actions

    def enable(self, name: str) -> None:
        """Enable an action."""
        if name in self.actions:
            self.actions[name].enabled = True

    def disable(self, name: str) -> None:
        """Disable an action."""
        if name in self.actions:
            self.actions[name].enabled = False

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent action history."""
        return self._history[-limit:]


# Global workflow engine
_engine: Optional[WorkflowEngine] = None


def get_engine() -> WorkflowEngine:
    """Get or create the global workflow engine."""
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
        _register_defaults(_engine)
    return _engine


def _register_defaults(engine: WorkflowEngine) -> None:
    """Register default workflow actions."""
    import json
    from pathlib import Path
    from ouroboros.utils import utc_now_iso

    def log_task_completion(context: dict) -> str:
        """Log task completion to events."""
        task_id = context.get("task_id", "unknown")
        log.info(f"Task {task_id} completed")
        return f"Logged completion of {task_id}"

    def update_scratchpad(context: dict) -> str:
        """Auto-update scratchpad after task."""
        summary = context.get("summary", "")
        if summary:
            from ouroboros.memory import Memory

            mem = Memory(drive_root=Path.home() / ".jo_data")
            current = mem.load_scratchpad()
            mem.save_scratchpad(current + f"\n- {utc_now_iso()}: {summary[:100]}")
        return "Scratchpad updated"

    def check_budget(context: dict) -> str:
        """Check budget after task."""
        cost = context.get("cost", 0)
        if cost > 1.0:
            log.warning(f"High cost task: ${cost:.2f}")
        return f"Budget checked: ${cost:.2f}"

    engine.register("log_completion", log_task_completion, "Log task completion", "on_task_complete")
    engine.register("update_scratchpad", update_scratchpad, "Auto-update scratchpad", "on_task_complete")
    engine.register("check_budget", check_budget, "Check budget after task", "on_task_complete")
