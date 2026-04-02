"""
Event-Driven Traceability Layer - Jo's automatic knowledge sync.

This module implements automatic traceability between:
- Tool executions → verify_claim logging
- Task completions → learn_from_result
- Code commits → reflect_on_change
- Health check failures → journal alerts + dashboard

Phases:
1. Automatic verify_claim and learn_from_result (low risk)
2. Auto-reflection on commits
3. Auto-weave orphan tool documentation
4. Health-to-vault sync (Phase 4 - this file)
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

HEALTH_DASHBOARD_PATH = "vault/journal/health-dashboard.md"


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

    def on_health_alert(self, invariant_name: str, message: str, severity: str = "medium") -> None:
        """Called when a health invariant fails. Creates journal entry and updates dashboard."""
        if not self._enabled:
            return

        try:
            self._auto_health_alert(invariant_name, message, severity)
            self._update_health_dashboard(invariant_name, message, severity)
        except Exception as e:
            log.debug(f"Auto-health-alert failed: {e}")

    def _auto_verify_claim(self, tool_name: str, args: Dict[str, Any], result: str, error: Optional[str]) -> None:
        """Automatically log verification after tool execution."""
        from ouroboros.memory import Memory

        claim = f"tool:{tool_name}"
        method = tool_name
        outcome = "verified"

        if error:
            outcome = f"error: {error[:100]}"
        elif "⚠️" in result or "❌" in result or "failed" in result.lower():
            outcome = "warning"

        try:
            mem = Memory(drive_root=self.ctx.drive_root)
            mem.ensure_files()
            mem.track_verification(claim=claim, verification_method=method, result=outcome)
        except Exception as e:
            log.debug(f"_verify_claim failed: {e}")

    def _auto_learn_from_result(self, task_description: str, result: str, success: bool) -> None:
        """Automatically record lesson after task completion."""
        from ouroboros.vault_manager import VaultManager

        if len(task_description) < 10:
            return

        result_summary = result[:300] if result else "No result"
        status = "success" if success else "failure"
        title = f"Lesson: {task_description[:50]}"
        
        content = f"""
## Task
{task_description[:100]}

## Result
{result_summary}

## Status
{"✅ Success" if success else "❌ Failure"}

## Lesson
_What was learned from this task execution._
"""
        try:
            vault = VaultManager(self.ctx.repo_path("vault"))
            vault.create_note(
                title=title,
                folder="journal",
                content=content,
                tags=["lesson", status],
                type="lesson",
                status="reviewed",
            )
        except Exception as e:
            log.debug(f"_learn_from_result failed: {e}")

    def _auto_reflect_on_change(self, commit_message: str, files_changed: List[str]) -> None:
        """Automatically create reflection after commit."""
        if not commit_message or commit_message.startswith("Merge"):
            return

        files_str = ", ".join(files_changed[:5])
        if len(files_changed) > 5:
            files_str += f" (+{len(files_changed) - 5} more)"

        change_description = f"Commit: {commit_message[:80]}\nFiles: {files_str}"
        outcome = "Committed and pushed"
        
        from datetime import datetime
        identity_path = self.ctx.drive_path("memory/identity.md")
        now = datetime.now().isoformat()

        reflection = f"""
## Reflection - {now}

**Change:** {change_description}
**Outcome:** {outcome}

_This change reflects growth in capabilities._
"""
        try:
            if identity_path.exists():
                content = identity_path.read_text(encoding="utf-8")
                identity_path.write_text(content + reflection, encoding="utf-8")
            else:
                identity_path.parent.mkdir(parents=True, exist_ok=True)
                identity_path.write_text(f"# Identity\n{reflection}", encoding="utf-8")
        except Exception as e:
            log.debug(f"_reflect_on_change failed: {e}")

    def _auto_health_alert(self, invariant_name: str, message: str, severity: str = "medium") -> None:
        """Automatically create journal entry for health alerts."""
        from ouroboros.vault_manager import VaultManager

        severity_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }
        icon = severity_icons.get(severity, "⚪")

        title = f"Health Alert: {invariant_name}"
        content = f"""
## Alert {icon}

**Invariant:** {invariant_name}
**Severity:** {severity.upper()}
**Message:** {message}
**Time:** {datetime.now().isoformat()}

## Action Required

_This alert requires review and potential remediation._
"""
        try:
            vault = VaultManager(self.ctx.repo_path("vault"))
            vault.create_note(
                title=title,
                folder="journal",
                content=content,
                tags=["health", "alert", severity],
                type="alert",
                status="open",
            )
        except Exception as e:
            log.debug(f"_vault_create for health alert failed: {e}")

    def _update_health_dashboard(self, invariant_name: str, message: str, severity: str) -> None:
        """Update the health dashboard with new alert."""
        dashboard_path = Path(self.ctx.repo_path(HEALTH_DASHBOARD_PATH))

        severity_icons = {
            "critical": "🔴",
            "high": "🟠",
            "medium": "🟡",
            "low": "🟢",
        }
        icon = severity_icons.get(severity, "⚪")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

        new_entry = f"- {icon} **{timestamp}** [{severity.upper()}] {invariant_name}: {message[:100]}"

        try:
            if dashboard_path.exists():
                content = dashboard_path.read_text(encoding="utf-8")
                if "## Recent Alerts" in content:
                    lines = content.split("\n")
                    insert_idx = None
                    for i, line in enumerate(lines):
                        if line == "## Recent Alerts":
                            insert_idx = i + 2
                            break
                    if insert_idx:
                        lines.insert(insert_idx, new_entry)
                        content = "\n".join(lines)
                else:
                    content += f"\n\n{new_entry}"
            else:
                dashboard_path.parent.mkdir(parents=True, exist_ok=True)
                content = self._generate_health_dashboard(new_entry)

            dashboard_path.write_text(content, encoding="utf-8")
            log.debug(f"Health dashboard updated: {invariant_name}")
        except Exception as e:
            log.debug(f"Failed to update health dashboard: {e}")

    def _generate_health_dashboard(self, first_entry: str) -> str:
        """Generate initial health dashboard content."""
        return f"""# Health Dashboard

_Automatically maintained by traceability layer._

## Status

Current system health status. Check for recent alerts.

## Recent Alerts

{first_entry}

## System Health Checks

### Verification Tracking
_Track via verify_claim tool_

### Version Sync
_Checked automatically_

### Budget Drift
_Monitored via state_

### Memory Files
_health_auto_fix ensures integrity_

---
_Generated: {datetime.now().isoformat()}_
"""

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


def check_and_alert_health(ctx: Any, invariant_name: str, message: str, severity: str = "medium") -> None:
    """Utility function to check health and fire alert if needed."""
    layer = get_traceability_layer(ctx)
    layer.on_health_alert(invariant_name, message, severity)
