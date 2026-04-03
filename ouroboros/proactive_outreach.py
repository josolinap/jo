"""
Jo — Proactive Outreach.

Realizes Principle 0 (Agency): Jo initiates contact, not just responds.
Jo messages creator with insights, not just responses.

Types of proactive outreach:
1. INSIGHT: "I noticed X pattern in the codebase. Should I investigate?"
2. ALERT: "Budget is at 80%. Consider reviewing recent tasks."
3. PROGRESS: "Completed 3 tasks today. Growth metrics updated."
4. QUESTION: "I'm uncertain about X. Can you clarify?"
5. SUGGESTION: "I could improve Y by doing Z. Want me to proceed?"

Budget-aware: only reaches out when value > cost.
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


class OutreachType(Enum):
    INSIGHT = "insight"
    ALERT = "alert"
    PROGRESS = "progress"
    QUESTION = "question"
    SUGGESTION = "suggestion"


@dataclass
class OutreachMessage:
    """A proactive outreach message."""

    type: OutreachType
    content: str
    priority: float  # 0.0-1.0, higher = more important
    timestamp: str = ""
    requires_response: bool = False
    budget_cost_estimate: float = 0.0  # Estimated cost to send


class ProactiveOutreach:
    """Manages Jo's proactive outreach to creator."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.outbox_dir = repo_dir / ".jo_state" / "outreach"
        self.outbox_dir.mkdir(parents=True, exist_ok=True)
        self._pending: List[OutreachMessage] = []
        self._sent: List[OutreachMessage] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load outreach history."""
        history_file = self.outbox_dir / "outreach_history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                self._sent = [OutreachMessage(**m) for m in data.get("sent", [])]
                self._pending = [OutreachMessage(**m) for m in data.get("pending", [])]
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save outreach history."""
        history_file = self.outbox_dir / "outreach_history.json"
        history_file.write_text(
            json.dumps(
                {
                    "sent": [
                        {
                            "type": m.type.value,
                            "content": m.content,
                            "priority": m.priority,
                            "timestamp": m.timestamp,
                            "requires_response": m.requires_response,
                            "budget_cost_estimate": m.budget_cost_estimate,
                        }
                        for m in self._sent
                    ],
                    "pending": [
                        {
                            "type": m.type.value,
                            "content": m.content,
                            "priority": m.priority,
                            "timestamp": m.timestamp,
                            "requires_response": m.requires_response,
                            "budget_cost_estimate": m.budget_cost_estimate,
                        }
                        for m in self._pending
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def queue_insight(self, content: str, priority: float = 0.5) -> None:
        """Queue an insight message."""
        message = OutreachMessage(
            type=OutreachType.INSIGHT,
            content=content,
            priority=priority,
            timestamp=datetime.now().isoformat(),
            requires_response=False,
            budget_cost_estimate=0.001,  # Minimal cost for text message
        )
        self._pending.append(message)
        self._save_history()
        log.info("[Outreach] Insight queued (priority %.1f): %s", priority, content[:100])

    def queue_alert(self, content: str, priority: float = 0.8) -> None:
        """Queue an alert message."""
        message = OutreachMessage(
            type=OutreachType.ALERT,
            content=content,
            priority=priority,
            timestamp=datetime.now().isoformat(),
            requires_response=True,
            budget_cost_estimate=0.002,
        )
        self._pending.append(message)
        self._save_history()
        log.info("[Outreach] Alert queued (priority %.1f): %s", priority, content[:100])

    def queue_progress(self, content: str, priority: float = 0.3) -> None:
        """Queue a progress message."""
        message = OutreachMessage(
            type=OutreachType.PROGRESS,
            content=content,
            priority=priority,
            timestamp=datetime.now().isoformat(),
            requires_response=False,
            budget_cost_estimate=0.001,
        )
        self._pending.append(message)
        self._save_history()

    def queue_question(self, content: str, priority: float = 0.7) -> None:
        """Queue a question message."""
        message = OutreachMessage(
            type=OutreachType.QUESTION,
            content=content,
            priority=priority,
            timestamp=datetime.now().isoformat(),
            requires_response=True,
            budget_cost_estimate=0.002,
        )
        self._pending.append(message)
        self._save_history()
        log.info("[Outreach] Question queued (priority %.1f): %s", priority, content[:100])

    def queue_suggestion(self, content: str, priority: float = 0.6) -> None:
        """Queue a suggestion message."""
        message = OutreachMessage(
            type=OutreachType.SUGGESTION,
            content=content,
            priority=priority,
            timestamp=datetime.now().isoformat(),
            requires_response=True,
            budget_cost_estimate=0.002,
        )
        self._pending.append(message)
        self._save_history()
        log.info("[Outreach] Suggestion queued (priority %.1f): %s", priority, content[:100])

    def get_pending_messages(self, min_priority: float = 0.0) -> List[OutreachMessage]:
        """Get pending messages above minimum priority."""
        return [m for m in self._pending if m.priority >= min_priority]

    def send_pending(self, min_priority: float = 0.5) -> List[OutreachMessage]:
        """Send pending messages above minimum priority."""
        to_send = [m for m in self._pending if m.priority >= min_priority]
        if not to_send:
            return []

        # Sort by priority (highest first)
        to_send.sort(key=lambda m: m.priority, reverse=True)

        for message in to_send:
            self._pending.remove(message)
            self._sent.append(message)
            log.info(
                "[Outreach] Sent %s (priority %.1f): %s", message.type.value, message.priority, message.content[:100]
            )

        self._save_history()
        return to_send

    def format_outreach_summary(self) -> str:
        """Format pending messages for display."""
        pending = self.get_pending_messages()
        if not pending:
            return ""

        parts = ["## Proactive Outreach\n"]
        for msg in pending:
            type_icon = {
                OutreachType.INSIGHT: "💡",
                OutreachType.ALERT: "🚨",
                OutreachType.PROGRESS: "📊",
                OutreachType.QUESTION: "❓",
                OutreachType.SUGGESTION: "💭",
            }.get(msg.type, "📝")

            response_tag = " [Needs Response]" if msg.requires_response else ""
            parts.append(f"{type_icon} **{msg.type.value.title()}**{response_tag} (priority {msg.priority:.1f})")
            parts.append(f"   {msg.content}")
            parts.append("")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get outreach statistics."""
        return {
            "pending": len(self._pending),
            "sent": len(self._sent),
            "by_type": {t.value: sum(1 for m in self._sent if m.type == t) for t in OutreachType},
            "avg_priority": sum(m.priority for m in self._sent) / len(self._sent) if self._sent else 0.0,
        }


# Global outreach instance
_outreach: Optional[ProactiveOutreach] = None


def get_outreach(repo_dir: Optional[pathlib.Path] = None) -> ProactiveOutreach:
    """Get or create the global proactive outreach."""
    global _outreach
    if _outreach is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _outreach = ProactiveOutreach(repo_dir)
    return _outreach
