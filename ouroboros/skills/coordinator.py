"""
Jo — Coordinator Mode.

Multi-agent orchestration system inspired by Claude Code's coordinator mode.
Transforms Jo from a single agent into a coordinator that spawns, directs,
and manages multiple worker agents in parallel.

Phases:
1. Research: Workers investigate codebase in parallel
2. Synthesis: Coordinator reads findings, crafts specs
3. Implementation: Workers make targeted changes per spec
4. Verification: Workers test changes

Key principle: "Parallelism is your superpower. Workers are async.
Launch independent workers concurrently whenever possible."
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


class CoordinatorPhase(Enum):
    RESEARCH = "research"
    SYNTHESIS = "synthesis"
    IMPLEMENTATION = "implementation"
    VERIFICATION = "verification"


class WorkerStatus(Enum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class WorkerTask:
    """A task assigned to a worker."""

    task_id: str
    description: str
    phase: CoordinatorPhase
    status: WorkerStatus = WorkerStatus.IDLE
    result: str = ""
    error: str = ""
    started_at: str = ""
    completed_at: str = ""


@dataclass
class CoordinatorState:
    """State of the coordinator system."""

    mission: str = ""
    current_phase: CoordinatorPhase = CoordinatorPhase.RESEARCH
    workers: List[WorkerTask] = field(default_factory=list)
    scratchpad: str = ""
    started_at: str = ""
    completed_at: str = ""
    success: bool = False


class CoordinatorMode:
    """Multi-agent coordination system."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "coordinator"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state = CoordinatorState()

    def start_mission(self, mission: str) -> str:
        """Start a new coordination mission."""
        self.state = CoordinatorState(
            mission=mission,
            current_phase=CoordinatorPhase.RESEARCH,
            started_at=datetime.now().isoformat(),
        )
        self._save_state()
        return f"Mission started: {mission}"

    def add_worker_task(self, description: str, phase: CoordinatorPhase) -> str:
        """Add a task for a worker agent."""
        task_id = f"worker-{len(self.state.workers) + 1}-{phase.value}"
        task = WorkerTask(
            task_id=task_id,
            description=description,
            phase=phase,
        )
        self.state.workers.append(task)
        self._save_state()
        return task_id

    def start_worker(self, task_id: str) -> bool:
        """Mark a worker task as started."""
        for task in self.state.workers:
            if task.task_id == task_id:
                task.status = WorkerStatus.RUNNING
                task.started_at = datetime.now().isoformat()
                self._save_state()
                return True
        return False

    def complete_worker(self, task_id: str, result: str) -> bool:
        """Mark a worker task as completed."""
        for task in self.state.workers:
            if task.task_id == task_id:
                task.status = WorkerStatus.COMPLETED
                task.result = result
                task.completed_at = datetime.now().isoformat()
                self._save_state()
                return True
        return False

    def fail_worker(self, task_id: str, error: str) -> bool:
        """Mark a worker task as failed."""
        for task in self.state.workers:
            if task.task_id == task_id:
                task.status = WorkerStatus.FAILED
                task.error = error
                task.completed_at = datetime.now().isoformat()
                self._save_state()
                return True
        return False

    def advance_phase(self) -> bool:
        """Advance to the next phase if current phase workers are done."""
        current_workers = [w for w in self.state.workers if w.phase == self.state.current_phase]
        if not current_workers:
            return False

        # Check if all current phase workers are completed or failed
        all_done = all(w.status in (WorkerStatus.COMPLETED, WorkerStatus.FAILED) for w in current_workers)

        if not all_done:
            return False

        # Advance to next phase
        phase_order = [
            CoordinatorPhase.RESEARCH,
            CoordinatorPhase.SYNTHESIS,
            CoordinatorPhase.IMPLEMENTATION,
            CoordinatorPhase.VERIFICATION,
        ]

        current_idx = phase_order.index(self.state.current_phase)
        if current_idx < len(phase_order) - 1:
            self.state.current_phase = phase_order[current_idx + 1]
            self._save_state()
            return True

        # All phases complete
        self.state.completed_at = datetime.now().isoformat()
        self.state.success = all(w.status == WorkerStatus.COMPLETED for w in self.state.workers)
        self._save_state()
        return False

    def get_research_prompt(self, task_id: str) -> str:
        """Get prompt for a research phase worker."""
        task = next((w for w in self.state.workers if w.task_id == task_id), None)
        if not task:
            return "Task not found."

        return f"""You are a research worker in a multi-agent coordination system.

## Mission
{self.state.mission}

## Your Task
{task.description}

## Instructions
1. Investigate the codebase thoroughly
2. Find all relevant files and understand the problem
3. Document your findings clearly
4. Include file paths and line numbers
5. Report back with comprehensive findings

## Important
- Be thorough and evidence-driven
- Include actual code snippets when relevant
- Note any risks or edge cases you discover
- Do NOT make any changes to the codebase

Report your findings in a structured format.
"""

    def get_implementation_prompt(self, task_id: str) -> str:
        """Get prompt for an implementation phase worker."""
        task = next((w for w in self.state.workers if w.task_id == task_id), None)
        if not task:
            return "Task not found."

        # Gather research findings
        research_results = [
            w.result
            for w in self.state.workers
            if w.phase == CoordinatorPhase.RESEARCH and w.status == WorkerStatus.COMPLETED
        ]

        return f"""You are an implementation worker in a multi-agent coordination system.

## Mission
{self.state.mission}

## Your Task
{task.description}

## Research Findings
{"".join(research_results)}

## Instructions
1. Read the research findings carefully
2. Understand the exact changes needed
3. Make targeted, minimal changes
4. Test your changes before reporting completion
5. Document what you changed and why

## Important
- Be precise and minimal in your changes
- Test thoroughly before marking complete
- Include evidence of successful testing
- Do NOT over-engineer or add unnecessary features

Report your implementation with evidence of success.
"""

    def get_verification_prompt(self, task_id: str) -> str:
        """Get prompt for a verification phase worker."""
        task = next((w for w in self.state.workers if w.task_id == task_id), None)
        if not task:
            return "Task not found."

        return f"""You are a verification worker in a multi-agent coordination system.

## Mission
{self.state.mission}

## Your Task
{task.description}

## Instructions
1. Verify that all changes work correctly
2. Run tests and check for regressions
3. Check for edge cases and error handling
4. Verify the implementation meets requirements
5. Report any issues found

## Verification Checklist
- [ ] Code compiles without errors
- [ ] All tests pass
- [ ] No linting errors
- [ ] Functionality works as expected
- [ ] No regressions introduced
- [ ] Edge cases handled

Report your verification results with evidence.
"""

    def get_status(self) -> Dict[str, Any]:
        """Get coordinator status."""
        return {
            "mission": self.state.mission,
            "current_phase": self.state.current_phase.value,
            "total_workers": len(self.state.workers),
            "completed_workers": sum(1 for w in self.state.workers if w.status == WorkerStatus.COMPLETED),
            "failed_workers": sum(1 for w in self.state.workers if w.status == WorkerStatus.FAILED),
            "running_workers": sum(1 for w in self.state.workers if w.status == WorkerStatus.RUNNING),
            "started_at": self.state.started_at,
            "completed_at": self.state.completed_at,
            "success": self.state.success,
            "workers": [
                {
                    "task_id": w.task_id,
                    "description": w.description,
                    "phase": w.phase.value,
                    "status": w.status.value,
                }
                for w in self.state.workers
            ],
        }

    def _save_state(self) -> None:
        """Save coordinator state to file."""
        state_file = self.state_dir / "coordinator_state.json"
        state_file.write_text(
            json.dumps(
                {
                    "mission": self.state.mission,
                    "current_phase": self.state.current_phase.value,
                    "workers": [
                        {
                            "task_id": w.task_id,
                            "description": w.description,
                            "phase": w.phase.value,
                            "status": w.status.value,
                            "result": w.result,
                            "error": w.error,
                            "started_at": w.started_at,
                            "completed_at": w.completed_at,
                        }
                        for w in self.state.workers
                    ],
                    "started_at": self.state.started_at,
                    "completed_at": self.state.completed_at,
                    "success": self.state.success,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


# Global coordinator instance
_coordinator: Optional[CoordinatorMode] = None


def get_coordinator(repo_dir: Optional[pathlib.Path] = None) -> CoordinatorMode:
    """Get or create the global coordinator."""
    global _coordinator
    if _coordinator is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _coordinator = CoordinatorMode(repo_dir)
    return _coordinator
