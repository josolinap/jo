"""Evolution history and state management for the agent.

Extracted from agent.py (Principle 5: Minimalism).
Handles: scratchpad updates, evolution history, archive logic.
"""

from __future__ import annotations

import datetime
import logging
from typing import Any, Dict

from ouroboros.memory import Memory

log = logging.getLogger(__name__)


class EvolutionHistory:
    """Manages evolution history and scratchpad updates."""

    def __init__(self, env: Any) -> None:
        self.env = env

    def _load_state_fn(self) -> Dict[str, Any]:
        """Load state - imported lazily to avoid circular imports."""
        from supervisor.state import load_state

        return load_state()

    def _save_state_fn(self, st: Dict[str, Any]) -> None:
        """Save state - imported lazily."""
        from supervisor.state import save_state

        save_state(st)

    def auto_update_scratchpad_after_task(
        self,
        task: Dict[str, Any],
        response_text: str,
        llm_trace: Dict[str, Any],
    ) -> None:
        """Auto-log evolution/review results with success tracking and archive/forget."""
        try:
            task_type = task.get("type", "unknown")
            task_id = task.get("id", "")

            # Count commits made during this task
            commit_tools = {"repo_write_commit", "repo_commit_push", "commit"}
            commit_count = sum(
                1
                for tc in llm_trace.get("tool_calls", [])
                if isinstance(tc, dict) and tc.get("tool", "").lower() in commit_tools
            )

            cost = sum(float(tc.get("cost", 0)) for tc in llm_trace.get("tool_calls", []) if isinstance(tc, dict))

            # Determine success: made commits AND has meaningful response
            success = commit_count > 0 and len(response_text.strip()) > 100

            # Get current cycle
            try:
                st = self._load_state_fn()
                cycle = int(st.get("evolution_cycle", 0))
            except Exception:
                cycle = 0

            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Extract summary from response (first 300 chars)
            summary = response_text[:300].replace("#", "").replace("*", "").replace("\n", " ").strip()
            if len(response_text) > 300:
                summary += "..."

            # Build history entry
            history_entry = {
                "task_id": task_id,
                "cycle": cycle,
                "timestamp": timestamp,
                "commits": commit_count,
                "success": success,
                "archived": False,
                "summary": summary,
                "cost": round(cost, 4),
            }

            # Update state with history
            self._update_evolution_history(history_entry, success)

            # Update scratchpad with human-readable entry
            mem = Memory(self.env.drive_root, self.env.repo_dir)
            current = mem.load_scratchpad()

            status_emoji = "✅" if success else "❌"
            status_text = "stable" if success else "failed"

            new_section = f"""
## {task_type.title()} #{task_id} ({cycle}) {status_emoji} [{status_text}]
- {timestamp}
- Commits: {commit_count}
- Cost: ${cost:.4f}
- Summary: {summary}
"""

            # Append to scratchpad
            updated = current + new_section
            lines = updated.splitlines()

            # Prune: keep last 50 evolution entries (~200 lines)
            if len(lines) > 200:
                lines = lines[-200:]
                updated = "\n".join(lines)

            mem.save_scratchpad(updated)
            log.info(f"Auto-updated scratchpad after {task_type} task {task_id} (success={success})")

            # Auto-archive if stable (success + no failures for 3 cycles)
            self._try_archive_stable_evolution()

        except Exception as e:
            log.warning("Failed to auto-update scratchpad: %s", e)

    def _update_evolution_history(self, entry: Dict[str, Any], success: bool) -> None:
        """Update evolution history in state with archive/forget logic."""
        try:
            st = self._load_state_fn()
            history = st.get("evolution_history", [])

            # Add new entry at the beginning
            history.insert(0, entry)

            # Prune: keep last 30 entries
            MAX_HISTORY = 30
            if len(history) > MAX_HISTORY:
                # Move entries older than 7 days to archived (they're "forgotten" from active view)
                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                pruned = []
                for h in history:
                    try:
                        ts = datetime.datetime.fromisoformat(h.get("timestamp", ""))
                        if ts > cutoff:
                            pruned.append(h)
                    except Exception:
                        pruned.append(h)
                history = pruned[:MAX_HISTORY]

            st["evolution_history"] = history

            # Update consecutive failures counter
            if success:
                st["evolution_consecutive_failures"] = 0
            else:
                st["evolution_consecutive_failures"] = int(st.get("evolution_consecutive_failures", 0)) + 1
                failures = st["evolution_consecutive_failures"]
                if failures >= 2:
                    log.warning(
                        f"EVOLUTION HEALTH ALERT: {failures} consecutive failures. "
                        f"Consider pausing evolution mode and reviewing recent commits."
                    )

            self._save_state_fn(st)

        except Exception as e:
            log.warning("Failed to update evolution history: %s", e)

    def _try_archive_stable_evolution(self) -> None:
        """Archive evolutions that have been stable (3+ successful, no recent failures)."""
        try:
            st = self._load_state_fn()
            history = st.get("evolution_history", [])
            consecutive_success = 0

            for entry in history:
                if entry.get("archived"):
                    continue
                if entry.get("success"):
                    consecutive_success += 1
                else:
                    break

            # Archive if 3+ consecutive successful evolutions
            if consecutive_success >= 3:
                archived_count = 0
                for entry in history:
                    if entry.get("success") and not entry.get("archived"):
                        entry["archived"] = True
                        archived_count += 1
                        if archived_count >= consecutive_success - 1:  # Keep latest
                            break

                st["evolution_history"] = history
                self._save_state_fn(st)
                log.info(f"Archived {archived_count} stable evolution entries")

        except Exception as e:
            log.warning("Failed to archive stable evolutions: %s", e)
