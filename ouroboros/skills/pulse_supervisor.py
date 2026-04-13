"""
Jo — Pulse Supervisor.

Inspired by aidevops' autonomous pulse - runs every 2 minutes to:
- Merge ready PRs
- Dispatch workers
- Kill stuck processes
- Detect orphaned work
- Advance missions
- Sync state with GitHub
"""

from __future__ import annotations

import json
import logging
import pathlib
import subprocess
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class PulseState(Enum):
    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"


@dataclass
class PulseConfig:
    """Configuration for the pulse supervisor."""

    interval_sec: int = 120  # 2 minutes
    auto_merge_threshold: int = 2  # Auto-merge after N ready PRs
    stuck_detection_minutes: int = 30
    max_retries: int = 3
    enable_auto_merge: bool = True
    enable_mission_advance: bool = True
    github_token: Optional[str] = None


@dataclass
class PulseMetrics:
    """Metrics collected by the pulse."""

    runs: int = 0
    prs_merged: int = 0
    workers_dispatched: int = 0
    stuck_killed: int = 0
    missions_advanced: int = 0
    errors: int = 0
    last_run: Optional[datetime] = None


@dataclass
class Mission:
    """A multi-day autonomous project."""

    mission_id: str
    goal: str
    milestones: List[str] = field(default_factory=list)
    current_milestone: int = 0
    status: str = "pending"  # pending, running, completed, failed
    budget_spent: float = 0.0
    budget_limit: float = 100.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class PulseSupervisor:
    """
    Autonomous supervisor that runs every 2 minutes.

    Inspired by aidevops' pulse system:
    - Checks for ready PRs and auto-merges
    - Dispatches pending workers
    - Detects and kills stuck processes
    - Advances active missions
    - Triages quality findings
    """

    def __init__(
        self,
        repo_dir: pathlib.Path,
        drive_root: pathlib.Path,
        config: Optional[PulseConfig] = None,
    ):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self.config = config or PulseConfig()
        self.state = PulseState.STOPPED
        self.metrics = PulseMetrics()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Mission tracking
        self.missions: Dict[str, Mission] = {}
        self.missions_file = drive_root / "logs" / "missions.json"
        self._load_missions()

        # Callbacks
        self.on_dispatch: Optional[Callable[[], None]] = None
        self.on_merge: Optional[Callable[[str], None]] = None
        self.on_mission_advance: Optional[Callable[[str], None]] = None

    def start(self) -> str:
        """Start the pulse supervisor."""
        if self.state == PulseState.RUNNING:
            return "Pulse supervisor already running"

        self._stop_event.clear()
        self.state = PulseState.RUNNING
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

        return f"Pulse supervisor started (interval: {self.config.interval_sec}s)"

    def stop(self) -> str:
        """Stop the pulse supervisor."""
        if self.state == PulseState.STOPPED:
            return "Pulse supervisor not running"

        self._stop_event.set()
        self.state = PulseState.STOPPED

        if self._thread:
            self._thread.join(timeout=5)

        return "Pulse supervisor stopped"

    def pause(self) -> str:
        """Pause the pulse supervisor."""
        if self.state != PulseState.RUNNING:
            return "Pulse supervisor not running"
        self.state = PulseState.PAUSED
        return "Pulse supervisor paused"

    def resume(self) -> str:
        """Resume the pulse supervisor."""
        if self.state != PulseState.PAUSED:
            return "Pulse supervisor not paused"
        self.state = PulseState.RUNNING
        return "Pulse supervisor resumed"

    def _run_loop(self) -> None:
        """Main pulse loop."""
        while not self._stop_event.is_set():
            if self.state == PulseState.RUNNING:
                try:
                    self._pulse()
                except Exception as e:
                    log.error(f"Pulse error: {e}")
                    self.metrics.errors += 1

            self._stop_event.wait(self.config.interval_sec)

    def _pulse(self) -> None:
        """Execute one pulse iteration."""
        self.metrics.runs += 1
        self.metrics.last_run = datetime.now()

        log.info("Running pulse check...")

        # Check and merge ready PRs
        if self.config.enable_auto_merge:
            self._check_prs()

        # Dispatch pending workers
        self._dispatch_workers()

        # Kill stuck processes
        self._check_stuck_processes()

        # Advance missions
        if self.config.enable_mission_advance:
            self._advance_missions()

        # Sync state
        self._sync_state()

        log.info(f"Pulse complete. Metrics: {self.metrics}")

    def _check_prs(self) -> None:
        """Check for PRs ready to merge."""
        # Check local git state for mergeable branches
        try:
            result = subprocess.run(
                ["git", "branch", "--format=%(refname:short)"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )

            branches = result.stdout.strip().split("\n")
            dev_branch = self.repo_dir.name  # or config branch

            # Check for branches ready to merge to dev
            for branch in branches:
                if branch.startswith("pr-") or branch.startswith("worker-"):
                    # Check if branch is ahead of dev
                    mergeable = self._check_mergeable(branch)
                    if mergeable and self.config.enable_auto_merge:
                        self._merge_branch(branch)

        except Exception as e:
            log.warning(f"PR check failed: {e}")

    def _check_mergeable(self, branch: str) -> bool:
        """Check if branch can be merged."""
        try:
            result = subprocess.run(
                ["git", "merge-base", "--is-ancestor", branch, "dev"],
                cwd=str(self.repo_dir),
                capture_output=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def _merge_branch(self, branch: str) -> bool:
        """Merge a branch into dev."""
        try:
            # First, fetch and checkout dev
            subprocess.run(
                ["git", "fetch", "origin", "dev"],
                cwd=str(self.repo_dir),
                capture_output=True,
                timeout=30,
            )

            # Checkout dev and merge
            subprocess.run(
                ["git", "checkout", "dev"],
                cwd=str(self.repo_dir),
                capture_output=True,
                timeout=10,
            )

            result = subprocess.run(
                ["git", "merge", "--no-ff", branch, "-m", f"Merge {branch}"],
                cwd=str(self.repo_dir),
                capture_output=True,
                timeout=30,
            )

            if result.returncode == 0:
                # Push the merge
                push_result = subprocess.run(
                    ["git", "push", "origin", "dev"],
                    cwd=str(self.repo_dir),
                    capture_output=True,
                    timeout=30,
                )

                if push_result.returncode == 0:
                    self.metrics.prs_merged += 1
                    # Delete the branch
                    subprocess.run(
                        ["git", "branch", "-d", branch],
                        cwd=str(self.repo_dir),
                        capture_output=True,
                        timeout=10,
                    )
                    return True

        except Exception as e:
            log.warning(f"Merge failed for {branch}: {e}")

        return False

    def _dispatch_workers(self) -> None:
        """Dispatch pending workers."""
        # Check for pending tasks in the queue
        queue_file = self.drive_root / "logs" / "task_queue.json"

        if not queue_file.exists():
            return

        try:
            tasks = json.loads(queue_file.read_text())
            pending = [t for t in tasks if t.get("status") == "pending"]

            if pending and self.on_dispatch:
                self.on_dispatch()
                self.metrics.workers_dispatched += 1

        except Exception as e:
            log.warning(f"Worker dispatch check failed: {e}")

    def _check_stuck_processes(self) -> None:
        """Check for and kill stuck processes."""
        # Check for workers that haven't reported in too long
        state_file = self.drive_root / "state" / "state.json"

        if not state_file.exists():
            return

        try:
            state = json.loads(state_file.read_text())
            workers = state.get("workers", {})

            now = datetime.now()
            stale_threshold = timedelta(minutes=self.config.stuck_detection_minutes)

            for worker_id, worker_data in workers.items():
                last_heartbeat = worker_data.get("last_heartbeat")
                if last_heartbeat:
                    last_ts = datetime.fromisoformat(last_heartbeat)
                    if now - last_ts > stale_threshold:
                        # Worker is stuck - mark it
                        log.warning(f"Detected stuck worker: {worker_id}")
                        self.metrics.stuck_killed += 1

        except Exception as e:
            log.warning(f"Stuck process check failed: {e}")

    def _advance_missions(self) -> None:
        """Advance active missions."""
        for mission_id, mission in self.missions.items():
            if mission.status != "running":
                continue

            # Check if current milestone is complete
            if self._is_milestone_complete(mission):
                if mission.current_milestone < len(mission.milestones) - 1:
                    mission.current_milestone += 1
                    self.metrics.missions_advanced += 1

                    if self.on_mission_advance:
                        self.on_mission_advance(mission_id)

        self._save_missions()

    def _is_milestone_complete(self, mission: Mission) -> bool:
        """Check if current milestone is complete."""
        # Check task DAG for completion
        dag_file = self.repo_dir / ".jo_state" / "task_dag" / "state.json"

        if not dag_file.exists():
            return False

        try:
            dag = json.loads(dag_file.read_text())
            tasks = dag.get("tasks", {})

            # Check if all tasks for current milestone are done
            milestone = mission.milestones[mission.current_milestone]
            for task in tasks.values():
                if task.get("milestone") == milestone:
                    if task.get("status") not in ("completed", "failed"):
                        return False

            return True

        except Exception:
            return False

    def _sync_state(self) -> None:
        """Sync state with external systems."""
        # Save metrics
        metrics_file = self.drive_root / "logs" / "pulse_metrics.json"
        metrics_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "runs": self.metrics.runs,
            "prs_merged": self.metrics.prs_merged,
            "workers_dispatched": self.metrics.workers_dispatched,
            "stuck_killed": self.metrics.stuck_killed,
            "missions_advanced": self.metrics.missions_advanced,
            "errors": self.metrics.errors,
            "last_run": self.metrics.last_run.isoformat() if self.metrics.last_run else None,
        }

        metrics_file.write_text(json.dumps(data, indent=2))

    def create_mission(
        self,
        goal: str,
        milestones: List[str],
        budget_limit: float = 100.0,
    ) -> str:
        """Create a new mission."""
        mission_id = f"mission-{len(self.missions) + 1}"
        mission = Mission(
            mission_id=mission_id,
            goal=goal,
            milestones=milestones,
            budget_limit=budget_limit,
            status="pending",
        )
        self.missions[mission_id] = mission
        self._save_missions()
        return mission_id

    def start_mission(self, mission_id: str) -> str:
        """Start a mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return f"Mission '{mission_id}' not found"

        mission.status = "running"
        mission.started_at = datetime.now().isoformat()
        self._save_missions()
        return f"Mission '{mission_id}' started"

    def get_mission_status(self, mission_id: str) -> str:
        """Get status of a mission."""
        mission = self.missions.get(mission_id)
        if not mission:
            return f"Mission '{mission_id}' not found"

        lines = [
            f"## Mission: {mission.goal}",
            f"Status: {mission.status}",
            f"Milestone: {mission.current_milestone + 1}/{len(mission.milestones)}",
            f"Budget: ${mission.budget_spent:.2f}/${mission.budget_limit:.2f}",
        ]

        if mission.current_milestone < len(mission.milestones):
            lines.append(f"\nCurrent: {mission.milestones[mission.current_milestone]}")

        return "\n".join(lines)

    def get_status(self) -> str:
        """Get pulse supervisor status."""
        lines = [
            f"## Pulse Supervisor",
            f"State: {self.state.value}",
            f"Interval: {self.config.interval_sec}s",
            f"Metrics:",
            f"- Runs: {self.metrics.runs}",
            f"- PRs merged: {self.metrics.prs_merged}",
            f"- Workers dispatched: {self.metrics.workers_dispatched}",
            f"- Stuck killed: {self.metrics.stuck_killed}",
            f"- Missions advanced: {self.metrics.missions_advanced}",
            f"- Errors: {self.metrics.errors}",
        ]

        if self.metrics.last_run:
            lines.append(f"- Last run: {self.metrics.last_run.isoformat()}")

        return "\n".join(lines)

    def _load_missions(self) -> None:
        """Load missions from file."""
        if not self.missions_file.exists():
            return

        try:
            data = json.loads(self.missions_file.read_text())
            for mid, mdata in data.items():
                self.missions[mid] = Mission(
                    mission_id=mdata["mission_id"],
                    goal=mdata["goal"],
                    milestones=mdata.get("milestones", []),
                    current_milestone=mdata.get("current_milestone", 0),
                    status=mdata.get("status", "pending"),
                    budget_spent=mdata.get("budget_spent", 0.0),
                    budget_limit=mdata.get("budget_limit", 100.0),
                    started_at=mdata.get("started_at"),
                    completed_at=mdata.get("completed_at"),
                )
        except Exception as e:
            log.warning(f"Failed to load missions: {e}")

    def _save_missions(self) -> None:
        """Save missions to file."""
        self.missions_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            mid: {
                "mission_id": m.mission_id,
                "goal": m.goal,
                "milestones": m.milestones,
                "current_milestone": m.current_milestone,
                "status": m.status,
                "budget_spent": m.budget_spent,
                "budget_limit": m.budget_limit,
                "started_at": m.started_at,
                "completed_at": m.completed_at,
            }
            for mid, m in self.missions.items()
        }

        self.missions_file.write_text(json.dumps(data, indent=2))


# Singleton instance
_pulse_supervisor: Optional[PulseSupervisor] = None


def get_pulse_supervisor(
    repo_dir: pathlib.Path,
    drive_root: pathlib.Path,
    config: Optional[PulseConfig] = None,
) -> PulseSupervisor:
    """Get or create the pulse supervisor."""
    global _pulse_supervisor
    if _pulse_supervisor is None:
        _pulse_supervisor = PulseSupervisor(repo_dir, drive_root, config)
    return _pulse_supervisor
