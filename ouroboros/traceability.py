"""
Event-Driven Traceability Layer - Jo's automatic knowledge sync.

This module implements automatic traceability between:
- Tool executions → verify_claim logging
- Task completions → learn_from_result
- Code commits → reflect_on_change
- Health check failures → journal alerts

Phases:
1. Automatic verify_claim and learn_from_result (low risk)
2. Auto-reflection on commits
3. Auto-weave orphan tool documentation
4. Health-to-vault sync
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class TraceabilityLayer:
    """
    Event-driven traceability that automatically syncs events to the knowledge graph.

    Registered handlers fire after events occur, calling appropriate weavers.
    """

    def __init__(self, ctx: Any):
        self.ctx = ctx
        self._enabled = True
        self._pending_events: List[Dict[str, Any]] = []

    def on_tool_invoked(self, tool_name: str, args: Dict[str, Any], result: str, error: Optional[str] = None) -> None:
        """Called after every tool execution. Logs verification."""
        if not self._enabled:
            return

        if tool_name.startswith("_") or tool_name in ("verify_claim", "learn_from_result", "reflect_on_change"):
            return

        try:
            self._auto_verify_claim(tool_name, args, result, error)
        except Exception as e:
            log.debug(f"Auto-verify failed for {tool_name}: {e}")

    def on_task_completed(self, task_id: str, task_description: str, result: str, success: bool) -> None:
        """Called when a scheduled task completes. Records lesson."""
        if not self._enabled:
            return

        try:
            self._auto_learn_from_result(task_description, result, success)
        except Exception as e:
            log.debug(f"Auto-learn failed for task {task_id}: {e}")

    def on_code_committed(self, commit_message: str, files_changed: List[str]) -> None:
        """Called after code commit. Creates reflection."""
        if not self._enabled:
            return

        try:
            self._auto_reflect_on_change(commit_message, files_changed)
        except Exception as e:
            log.debug(f"Auto-reflect failed after commit: {e}")

    def on_health_alert(self, invariant_name: str, message: str, severity: str) -> None:
        """Called when a health invariant fails. Creates journal entry."""
        if not self._enabled:
            return

        if severity not in ("high", "critical"):
            return

        try:
            self._auto_health_alert(invariant_name, message)
        except Exception as e:
            log.debug(f"Auto-health-alert failed: {e}")

    def _auto_verify_claim(self, tool_name: str, args: Dict[str, Any], result: str, error: Optional[str]) -> None:
        """Automatically log verification after tool execution."""
        from ouroboros.tools.control import _verify_claim

        claim = f"tool:{tool_name}"
        method = tool_name
        outcome = "verified"

        if error:
            outcome = f"error: {error[:100]}"
        elif "⚠️" in result or "❌" in result or "failed" in result.lower():
            outcome = "warning"

        try:
            _verify_claim(
                self.ctx,
                claim=claim,
                verification_method=method,
                result=outcome,
            )
        except Exception as e:
            log.debug(f"_verify_claim failed: {e}")

    def _auto_learn_from_result(self, task_description: str, result: str, success: bool) -> None:
        """Automatically record lesson after task completion."""
        from ouroboros.tools.connection_weavers import _learn_from_result

        if len(task_description) < 10:
            return

        result_summary = result[:300] if result else "No result"
        try:
            _learn_from_result(
                self.ctx,
                task=task_description[:100],
                result=result_summary,
                success=success,
            )
        except Exception as e:
            log.debug(f"_learn_from_result failed: {e}")

    def _auto_reflect_on_change(self, commit_message: str, files_changed: List[str]) -> None:
        """Automatically create reflection after commit."""
        from ouroboros.tools.connection_weavers import _reflect_on_change

        if not commit_message or commit_message.startswith("Merge"):
            return

        files_str = ", ".join(files_changed[:5])
        if len(files_changed) > 5:
            files_str += f" (+{len(files_changed) - 5} more)"

        change_desc = f"Commit: {commit_message[:80]}\nFiles: {files_str}"

        try:
            _reflect_on_change(
                self.ctx,
                change_description=change_desc,
                outcome="Committed and pushed",
            )
        except Exception as e:
            log.debug(f"_reflect_on_change failed: {e}")

    def _auto_health_alert(self, invariant_name: str, message: str) -> None:
        """Automatically create journal entry for health alerts."""
        from ouroboros.tools.vault import _vault_create

        title = f"Health Alert: {invariant_name}"
        content = f"""
## Alert

**Invariant:** {invariant_name}
**Message:** {message}

## Action Required

_This alert requires review and potential remediation._

"""
        try:
            _vault_create(
                self.ctx,
                title=title,
                folder="journal",
                content=content,
                tags="health, alert, incident",
                type="alert",
                status="open",
            )
        except Exception as e:
            log.debug(f"_vault_create for health alert failed: {e}")

    def disable(self) -> None:
        """Temporarily disable automatic traceability."""
        self._enabled = False

    def enable(self) -> None:
        """Re-enable automatic traceability."""
        self._enabled = True


def get_traceability_layer(ctx: Any) -> TraceabilityLayer:
    """Get or create traceability layer for context."""
    if not hasattr(ctx, "_traceability"):
        ctx._traceability = TraceabilityLayer(ctx)
    return ctx._traceability
