"""
Jo — Dead Letter Queue for Failed Tasks.

Inspired by AWS SQS and message queue best practices.
Preserves failed tasks for later analysis instead of losing them.

Problem: When tasks fail, they disappear. No way to analyze why they failed
or retry them later.

Solution: Failed tasks are moved to a dead letter queue with full context:
- Original task content
- Error messages and stack traces
- Tool calls attempted
- Timestamp and session info

This enables:
- Post-mortem analysis of failure patterns
- Manual retry of important tasks
- Training data for improving Jo's reliability
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class DeadLetterTask:
    """A failed task in the dead letter queue."""

    id: str
    original_task: Dict[str, Any]
    error_message: str
    error_traceback: str = ""
    tool_calls_attempted: List[Dict[str, Any]] = field(default_factory=list)
    session_id: str = ""
    failed_at: str = ""
    retry_count: int = 0
    max_retries: int = 3
    tags: List[str] = field(default_factory=list)


class DeadLetterQueue:
    """Manages failed tasks for later analysis and retry."""

    def __init__(self, repo_dir: pathlib.Path, max_size: int = 100):
        self.repo_dir = repo_dir
        self.max_size = max_size
        self.dlq_dir = repo_dir / ".jo_state" / "dead_letter_queue"
        self.dlq_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: List[DeadLetterTask] = []
        self._load_tasks()

    def _load_tasks(self) -> None:
        """Load dead letter tasks from disk."""
        tasks_file = self.dlq_dir / "tasks.json"
        if tasks_file.exists():
            try:
                data = json.loads(tasks_file.read_text(encoding="utf-8"))
                self._tasks = [DeadLetterTask(**t) for t in data]
            except Exception:
                pass

    def _save_tasks(self) -> None:
        """Save dead letter tasks to disk."""
        tasks_file = self.dlq_dir / "tasks.json"
        tasks_file.write_text(
            json.dumps(
                [
                    {
                        "id": t.id,
                        "original_task": t.original_task,
                        "error_message": t.error_message,
                        "error_traceback": t.error_traceback,
                        "tool_calls_attempted": t.tool_calls_attempted,
                        "session_id": t.session_id,
                        "failed_at": t.failed_at,
                        "retry_count": t.retry_count,
                        "max_retries": t.max_retries,
                        "tags": t.tags,
                    }
                    for t in self._tasks
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    def add_failed_task(
        self,
        task: Dict[str, Any],
        error_message: str,
        error_traceback: str = "",
        tool_calls: List[Dict[str, Any]] = None,
        session_id: str = "",
        tags: List[str] = None,
    ) -> str:
        """Add a failed task to the dead letter queue."""
        task_id = f"dlq-{int(time.time())}-{len(self._tasks)}"
        dead_task = DeadLetterTask(
            id=task_id,
            original_task=task,
            error_message=error_message[:1000],  # Truncate long errors
            error_traceback=error_traceback[:2000],
            tool_calls_attempted=tool_calls or [],
            session_id=session_id,
            failed_at=datetime.now().isoformat(),
            tags=tags or [],
        )
        self._tasks.append(dead_task)

        # Trim if over max size (keep most recent)
        if len(self._tasks) > self.max_size:
            self._tasks = self._tasks[-self.max_size :]

        self._save_tasks()
        log.warning("[DeadLetterQueue] Added failed task %s: %s", task_id, error_message[:100])
        return task_id

    def get_tasks(self, limit: int = 20, tag_filter: Optional[str] = None) -> List[DeadLetterTask]:
        """Get failed tasks, optionally filtered by tag."""
        tasks = self._tasks
        if tag_filter:
            tasks = [t for t in tasks if tag_filter in t.tags]
        return tasks[-limit:]

    def retry_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task for retry (increments retry count)."""
        for task in self._tasks:
            if task.id == task_id:
                if task.retry_count >= task.max_retries:
                    log.warning("[DeadLetterQueue] Task %s exceeded max retries (%d)", task_id, task.max_retries)
                    return None

                task.retry_count += 1
                self._save_tasks()
                log.info(
                    "[DeadLetterQueue] Retrying task %s (attempt %d/%d)", task_id, task.retry_count, task.max_retries
                )
                return task.original_task

        return None

    def remove_task(self, task_id: str) -> bool:
        """Remove a task from the dead letter queue."""
        before = len(self._tasks)
        self._tasks = [t for t in self._tasks if t.id != task_id]
        if len(self._tasks) < before:
            self._save_tasks()
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """Get dead letter queue statistics."""
        by_error = {}
        by_tag = {}
        for task in self._tasks:
            # Group by error type
            error_type = task.error_message[:50]
            by_error[error_type] = by_error.get(error_type, 0) + 1

            # Group by tags
            for tag in task.tags:
                by_tag[tag] = by_tag.get(tag, 0) + 1

        return {
            "total_failed_tasks": len(self._tasks),
            "max_size": self.max_size,
            "by_error_type": by_error,
            "by_tag": by_tag,
            "retryable": sum(1 for t in self._tasks if t.retry_count < t.max_retries),
            "exhausted": sum(1 for t in self._tasks if t.retry_count >= t.max_retries),
        }


# Global dead letter queue instance
_dlq: Optional[DeadLetterQueue] = None


def get_dead_letter_queue(repo_dir: Optional[pathlib.Path] = None) -> DeadLetterQueue:
    """Get or create the global dead letter queue."""
    global _dlq
    if _dlq is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _dlq = DeadLetterQueue(repo_dir)
    return _dlq
