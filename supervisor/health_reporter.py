"""
Ouroboros Health Reporter — generates "Heartbeat" summaries of system status.
Distills performance, budget, and anomalies into a concise narrative for the owner.
"""

import json
import logging
import pathlib
import datetime
from typing import Dict, Any

log = logging.getLogger(__name__)


class HealthReporter:
    def __init__(self, drive_root: pathlib.Path):
        self.drive_root = drive_root
        self.state_path = drive_root / "state" / "state.json"
        self.events_path = drive_root / "logs" / "events.jsonl"

    def generate_heartbeat(self) -> str:
        """Produce a markdown summary of current health and recent efficiency."""
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                st = json.load(f)

            budget_used = st.get("budget_used", 0)
            budget_limit = st.get("budget_limit", 100)
            status = "✅ HEALTHY" if budget_used < budget_limit * 0.9 else "⚠️ BUDGET WARNING"

            active_workers = len(st.get("running_tasks", {}))
            pending_tasks = len(st.get("task_queue", []))

            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

            summary = [
                f"### System Heartbeat ({now})",
                f"**Status**: {status}",
                f"**Budget**: ${budget_used:.4f} / ${budget_limit:.2f}",
                f"**Workers**: {active_workers} active, {pending_tasks} pending",
                "",
            ]

            # Brief success rate summary from last 100 events
            stats = self._calc_stats(limit=100)
            summary.append(f"**Recent Efficiency**: {stats['success_rate']}% success rate ({stats['total']} tasks)")

            return "\n".join(summary)
        except Exception as e:
            log.error(f"HealthReporter failed: {e}")
            return f"Error generating heartbeat: {e}"

    def _calc_stats(self, limit: int = 100) -> Dict[str, Any]:
        if not self.events_path.exists():
            return {"success_rate": 0, "total": 0}

        successes = 0
        total = 0
        try:
            with open(self.events_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                for line in reversed(lines[-limit:]):
                    try:
                        ev = json.loads(line)
                        if ev.get("type") == "task_done":
                            successes += 1
                            total += 1
                        elif ev.get("type") == "task_error":
                            total += 1
                    except (json.JSONDecodeError, KeyError) as e:
                        log.debug("Failed to parse event: %s", e)
                        continue
        except (OSError, IOError) as e:
            log.debug("Failed to read events file: %s", e)

        rate = int((successes / total * 100) if total > 0 else 0)
        return {"success_rate": rate, "total": total}
