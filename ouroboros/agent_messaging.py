"""Event emission helpers for the agent.

Extracted from agent.py (Principle 5: Minimalism).
Handles: progress, typing, heartbeat events.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any, Optional

from ouroboros.utils import utc_now_iso

log = logging.getLogger(__name__)


class MessageEmitter:
    """Handles all event emission to the supervisor."""

    def __init__(self, event_queue: Any = None) -> None:
        self._event_queue = event_queue

    def emit_progress(self, text: str, chat_id: Optional[int], last_progress_ts: float) -> float:
        """Emit progress event. Returns updated last_progress_ts."""
        new_ts = time.time()

        # Suppress progress messages to owner if configured
        if os.environ.get("OUROBOROS_SUPPRESS_PROGRESS", "1") == "1":
            log.debug(f"[Progress] {text}")
            return new_ts

        if self._event_queue is None or chat_id is None:
            return new_ts
        try:
            self._event_queue.put(
                {
                    "type": "send_message",
                    "chat_id": chat_id,
                    "text": f"💬 {text}",
                    "format": "markdown",
                    "is_progress": True,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit progress event", exc_info=True)
        return new_ts

    def emit_typing_start(self, chat_id: Optional[int]) -> None:
        """Emit typing indicator."""
        if self._event_queue is None or chat_id is None:
            return
        try:
            self._event_queue.put(
                {
                    "type": "typing_start",
                    "chat_id": chat_id,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit typing start event", exc_info=True)

    def emit_task_heartbeat(self, task_id: str, phase: str) -> None:
        """Emit task heartbeat."""
        if self._event_queue is None:
            return
        try:
            self._event_queue.put(
                {
                    "type": "task_heartbeat",
                    "task_id": task_id,
                    "phase": phase,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit task heartbeat event", exc_info=True)

    def start_heartbeat_loop(self, task_id: str) -> Optional[threading.Event]:
        """Start periodic heartbeat. Returns stop event."""
        if self._event_queue is None or not task_id.strip():
            return None
        interval = 30
        stop = threading.Event()
        self.emit_task_heartbeat(task_id, "start")

        def _loop() -> None:
            while not stop.wait(interval):
                self.emit_task_heartbeat(task_id, "running")

        threading.Thread(target=_loop, daemon=True).start()
        return stop
