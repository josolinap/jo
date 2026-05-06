"""
Work Checkpoint — per-work-item checkpointing for parallel execution.

Manages state for up to 12+ concurrent works with:
- Per-work save/restore
- Intermediate result persistence
- Auto-archival of completed works
- Crash recovery from last checkpoint
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class WorkCheckpoint:
    work_id: str
    perspective: str
    status: str = "pending"  # pending/running/checkpointed/done/failed
    progress: float = 0.0
    current_step: str = ""
    result: Optional[str] = None
    error: Optional[str] = None
    checkpoints: List[Dict] = field(default_factory=list)
    started_at: Optional[float] = None
    updated_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class WorkCheckpointManager:
    """Manages checkpoints for up to 12+ concurrent works."""

    MAX_WORKS = 12
    CHECKPOINT_INTERVAL = 30  # seconds between auto-checkpoints

    def __init__(self, checkpoint_dir: Optional[Path] = None):
        if checkpoint_dir is None:
            checkpoint_dir = Path(os.environ.get("JO_CHECKPOINT_DIR", "~/.jo_data/checkpoints"))
        self.checkpoint_dir = checkpoint_dir.expanduser()
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        (self.checkpoint_dir / "archive").mkdir(exist_ok=True)
        self.works: Dict[str, WorkCheckpoint] = {}
        self._load_existing()

    def create_work(self, work_id: str, perspective: str) -> WorkCheckpoint:
        """Create a new work item with checkpoint tracking."""
        if len(self.works) >= self.MAX_WORKS:
            self._archive_completed()

        checkpoint = WorkCheckpoint(
            work_id=work_id,
            perspective=perspective,
            started_at=time.time(),
            updated_at=time.time(),
        )
        self.works[work_id] = checkpoint
        self._save_checkpoint(checkpoint)
        return checkpoint

    def update_work(self, work_id: str, **kwargs) -> WorkCheckpoint:
        """Update a work item's state."""
        work = self.works.get(work_id)
        if not work:
            raise KeyError(f"Work {work_id} not found")

        for key, value in kwargs.items():
            if hasattr(work, key):
                setattr(work, key, value)
        work.updated_at = time.time()

        work.checkpoints.append(
            {
                "ts": time.time(),
                "status": work.status,
                "progress": work.progress,
                "step": work.current_step,
            }
        )
        # Keep only last 10 checkpoints per work
        work.checkpoints = work.checkpoints[-10:]

        self._save_checkpoint(work)
        return work

    def save_intermediate(self, work_id: str, step: str, data: Any) -> None:
        """Save intermediate result for a work item."""
        work = self.works.get(work_id)
        if not work:
            return

        checkpoint_file = self.checkpoint_dir / f"{work_id}_{step}.json"
        checkpoint_file.write_text(
            json.dumps(
                {
                    "work_id": work_id,
                    "step": step,
                    "data": data,
                    "ts": time.time(),
                }
            )
        )

        work.current_step = step
        work.status = "checkpointed"
        self._save_checkpoint(work)

    def restore_work(self, work_id: str) -> Optional[WorkCheckpoint]:
        """Restore a work item from its last checkpoint."""
        checkpoint_file = self.checkpoint_dir / f"{work_id}.json"
        if not checkpoint_file.exists():
            return None

        data = json.loads(checkpoint_file.read_text())
        work = WorkCheckpoint(**data)
        self.works[work_id] = work
        return work

    def get_all_status(self) -> Dict[str, Any]:
        """Get status of all concurrent works."""
        return {
            "total": len(self.works),
            "pending": sum(1 for w in self.works.values() if w.status == "pending"),
            "running": sum(1 for w in self.works.values() if w.status == "running"),
            "done": sum(1 for w in self.works.values() if w.status == "done"),
            "failed": sum(1 for w in self.works.values() if w.status == "failed"),
            "checkpointed": sum(1 for w in self.works.values() if w.status == "checkpointed"),
            "works": {
                wid: {
                    "perspective": w.perspective,
                    "status": w.status,
                    "progress": w.progress,
                    "step": w.current_step,
                }
                for wid, w in self.works.items()
            },
        }

    def get_completed_results(self) -> Dict[str, str]:
        """Get results from all completed works."""
        return {w.work_id: w.result for w in self.works.values() if w.status == "done" and w.result}

    def format_status_report(self) -> str:
        """Format a human-readable status report."""
        status = self.get_all_status()
        lines = [
            "## Parallel Works Status",
            f"- Total: {status['total']}",
            f"- Running: {status['running']}",
            f"- Done: {status['done']}",
            f"- Failed: {status['failed']}",
            f"- Checkpointed: {status['checkpointed']}",
        ]

        for wid, info in status.get("works", {}).items():
            icon = {"done": "✅", "failed": "❌", "running": "🔄", "pending": "⏳", "checkpointed": "💾"}.get(
                info["status"], "❓"
            )
            lines.append(f"  {icon} {info['perspective']}: {info['status']} ({info['progress']:.0%})")

        return "\n".join(lines)

    def _save_checkpoint(self, work: WorkCheckpoint) -> None:
        """Persist work checkpoint to disk."""
        checkpoint_file = self.checkpoint_dir / f"{work.work_id}.json"
        data = {
            "work_id": work.work_id,
            "perspective": work.perspective,
            "status": work.status,
            "progress": work.progress,
            "current_step": work.current_step,
            "result": work.result,
            "error": work.error,
            "checkpoints": work.checkpoints[-10:],
            "started_at": work.started_at,
            "updated_at": work.updated_at,
            "metadata": work.metadata,
        }
        # Atomic write
        tmp_file = checkpoint_file.with_suffix(".tmp")
        tmp_file.write_text(json.dumps(data, indent=2))
        os.replace(str(tmp_file), str(checkpoint_file))

    def _load_existing(self) -> None:
        """Load existing checkpoints from disk."""
        for f in self.checkpoint_dir.glob("*.json"):
            if "_" not in f.stem:  # Skip intermediate checkpoints
                try:
                    data = json.loads(f.read_text())
                    work = WorkCheckpoint(**data)
                    self.works[work.work_id] = work
                except Exception:
                    log.warning(f"Failed to load checkpoint: {f}")

    def _archive_completed(self) -> None:
        """Archive oldest completed works to make room."""
        completed = [w for w in self.works.values() if w.status in ("done", "failed")]
        completed.sort(key=lambda w: w.updated_at or 0)

        for work in completed[:4]:  # Archive 4 oldest
            archive_file = self.checkpoint_dir / "archive" / f"{work.work_id}.json"
            archive_file.write_text(
                json.dumps(
                    {
                        "work_id": work.work_id,
                        "perspective": work.perspective,
                        "status": work.status,
                        "result": work.result[:2000] if work.result else None,
                        "error": work.error,
                        "completed_at": work.updated_at,
                    }
                )
            )
            # Remove from active and delete checkpoint file
            del self.works[work.work_id]
            checkpoint_file = self.checkpoint_dir / f"{work.work_id}.json"
            if checkpoint_file.exists():
                checkpoint_file.unlink()

        log.info(f"[Checkpoint] Archived {min(4, len(completed))} completed works")


# Singleton instance
_manager: Optional[WorkCheckpointManager] = None


def get_checkpoint_manager(checkpoint_dir: Optional[Path] = None) -> WorkCheckpointManager:
    """Get or create the singleton checkpoint manager."""
    global _manager
    if _manager is None:
        _manager = WorkCheckpointManager(checkpoint_dir)
    return _manager


def reset_checkpoint_manager() -> None:
    """Reset the singleton (for testing)."""
    global _manager
    _manager = None
