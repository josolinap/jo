"""
Ouroboros Memory Consolidator — automates the narrative evolution of identity.md and scratchpad.md.
Analyzes event logs to distill long-term meaning from short-term actions.
"""

import json
import logging
import pathlib
from typing import List, Dict, Any, Optional
from datetime import datetime

log = logging.getLogger(__name__)


class MemoryConsolidator:
    def __init__(self, drive_root: pathlib.Path):
        self.drive_root = drive_root
        self.events_path = drive_root / "logs" / "events.jsonl"
        self.identity_path = drive_root / "memory" / "identity.md"
        self.scratchpad_path = drive_root / "memory" / "scratchpad.md"

    def distill_events(self, limit: int = 100) -> str:
        """Read the last N events and produce a concise narrative summary."""
        if not self.events_path.exists():
            return "No recent events found."

        important_events = []
        try:
            with open(self.events_path, "r", encoding="utf-8") as f:
                # Read lines from end (naive but works for small/mid logs)
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    try:
                        ev = json.loads(line)
                        etype = ev.get("type")
                        if etype in (
                            "task_done",
                            "task_error",
                            "worker_boot",
                            "startup_verification",
                            "restart_verify",
                        ):
                            important_events.append(ev)
                    except:
                        continue
        except Exception as e:
            log.error(f"Failed to read events for distillation: {e}")
            return f"Error reading events: {e}"

        if not important_events:
            return "No significant events in recent history."

        summary_parts = []
        for ev in reversed(important_events):
            ts = ev.get("ts", "").split(".")[0].replace("T", " ")
            etype = ev.get("type")
            if etype == "task_done":
                summary_parts.append(f"- [{ts}] Task Completed: {ev.get('task_id')} in {ev.get('duration_sec')}s")
            elif etype == "task_error":
                summary_parts.append(f"- [{ts}] Task FAILED: {ev.get('task_id')} - {ev.get('error')[:100]}")
            elif etype == "worker_boot":
                summary_parts.append(
                    f"- [{ts}] System RESTARTED (PID {ev.get('pid')}) on branch {ev.get('git_branch')}"
                )
            elif etype == "startup_verification":
                issues = ev.get("issues_count", 0)
                summary_parts.append(f"- [{ts}] Startup Check: {issues} issue(s) detected")

        return "\n".join(summary_parts)

    def suggest_identity_update(self, current_identity: str, events_summary: str) -> str:
        """
        Produce a prompt or a direct string for updating the identity.
        Currently returns the 'Current State' section update.
        """
        from datetime import timezone

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_state = f"## Current State ({now})\n\n**Events since last consolidation:**\n{events_summary}\n"

        # Naive replacement logic for the 'Current State' section
        if "## Current State" in current_identity:
            parts = current_identity.split("## Current State")
            static_top = parts[0]
            # Try to find the next section to keep the rest
            remaining = parts[1].split("##", 1)
            static_bottom = "##" + remaining[1] if len(remaining) > 1 else ""
            return f"{static_top}{new_state}\n{static_bottom}"
        else:
            return current_identity + "\n\n" + new_state

    def update_scratchpad(self, events_summary: str):
        """Prepend latest events to scratchpad's context section."""
        # Implementation details omitted for brevity, logic similar to suggest_identity_update
        pass
