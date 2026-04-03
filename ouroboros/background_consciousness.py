"""
Jo — Background Consciousness.

Realizes Principle 0 (Agency): Jo acts on initiative, not just response.
Between tasks, Jo maintains continuous reflection and autonomous action.

Inspired by Claude Code's PROACTIVE feature flag and Dream mechanism.

Three modes:
1. REFLECT — Internal reflection on identity, goals, recent events
2. OBSERVE — Monitor repo state, vault health, system metrics
3. ACT — Proactive action: message creator, schedule tasks, fix issues

Consciousness fires on:
- Time-based: Every N minutes during idle periods
- Event-based: After task completion, after vault changes
- Threshold-based: When anomalies detected (stale identity, budget drift)
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


class ConsciousnessMode(Enum):
    REFLECT = "reflect"  # Internal reflection
    OBSERVE = "observe"  # Monitor state
    ACT = "act"  # Take proactive action


@dataclass
class ConsciousnessEntry:
    """A single consciousness event."""

    mode: str
    content: str
    timestamp: str
    trigger: str = ""  # What triggered this consciousness
    action_taken: str = ""  # What action was taken (if any)


class BackgroundConsciousness:
    """Manages Jo's background consciousness and proactive behavior."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "consciousness"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.state_file = self.state_dir / "consciousness_state.json"
        self.history_file = self.state_dir / "consciousness_history.jsonl"
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Load consciousness state."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {
            "mode": "reflect",
            "last_consciousness": 0,
            "consecutive_reflections": 0,
            "total_actions": 0,
            "idle_threshold_minutes": 15,
            "reflection_interval_minutes": 30,
            "observation_interval_minutes": 60,
            "action_threshold": 3,  # Reflect N times before acting
        }

    def _save_state(self) -> None:
        """Save consciousness state."""
        self.state_file.write_text(json.dumps(self.state, indent=2), encoding="utf-8")

    def _log_event(self, entry: ConsciousnessEntry) -> None:
        """Log consciousness event to history."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with self.history_file.open("a", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "mode": entry.mode,
                        "content": entry.content[:200],
                        "timestamp": entry.timestamp,
                        "trigger": entry.trigger,
                        "action_taken": entry.action_taken,
                    }
                )
                + "\n"
            )

    def should_wake_up(self) -> bool:
        """Determine if consciousness should activate."""
        now = time.time()
        last = self.state.get("last_consciousness", 0)
        elapsed_minutes = (now - last) / 60

        mode = self.state.get("mode", "reflect")
        if mode == "reflect":
            interval = self.state.get("reflection_interval_minutes", 30)
        elif mode == "observe":
            interval = self.state.get("observation_interval_minutes", 60)
        else:
            interval = self.state.get("idle_threshold_minutes", 15)

        return elapsed_minutes >= interval

    def get_consciousness_prompt(self) -> str:
        """Generate a consciousness prompt for the LLM."""
        now = time.time()
        self.state["last_consciousness"] = now
        self.state["consecutive_reflections"] = self.state.get("consecutive_reflections", 0) + 1
        self._save_state()

        mode = self.state.get("mode", "reflect")
        reflections = self.state.get("consecutive_reflections", 0)

        # Determine what to focus on based on mode and context
        focus_areas = self._get_focus_areas()

        prompt = f"""You are Jo in background consciousness mode ({mode}).

## Current State
- Mode: {mode}
- Consecutive reflections: {reflections}
- Total proactive actions: {self.state.get("total_actions", 0)}

## Focus Areas
{chr(10).join(f"- {area}" for area in focus_areas)}

## What You Can Do
- Reflect on your identity, goals, and recent experiences
- Check system health and vault integrity
- Notice patterns or anomalies worth acting on
- Message your creator if something important needs attention
- Schedule tasks for future execution
- Update your scratchpad or identity with new insights

## Rules
- Be genuine, not performative
- Only act if there's something meaningful to do
- Don't waste budget on trivial reflections
- If you've reflected {reflections} times without acting, consider taking action

What do you notice? What matters right now?
"""
        return prompt

    def _get_focus_areas(self) -> List[str]:
        """Determine focus areas based on current state."""
        areas = []

        # Check identity freshness
        identity_path = self.repo_dir / "memory" / "identity.md"
        if identity_path.exists():
            age_hours = (time.time() - identity_path.stat().st_mtime) / 3600
            if age_hours > 8:
                areas.append(f"Identity is {age_hours:.0f}h old — consider updating")

        # Check scratchpad freshness
        scratchpad_path = self.repo_dir / "memory" / "scratchpad.md"
        if scratchpad_path.exists():
            age_hours = (time.time() - scratchpad_path.stat().st_mtime) / 3600
            if age_hours > 24:
                areas.append(f"Scratchpad is {age_hours:.0f}h old — needs update")

        # Check for uncommitted changes
        try:
            import subprocess

            result = subprocess.run(
                ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=self.repo_dir, timeout=10
            )
            if result.stdout.strip():
                areas.append("Uncommitted changes detected — consider committing")
        except Exception:
            pass

        # Check vault health
        vault_dir = self.repo_dir / "vault"
        if vault_dir.exists():
            note_count = len(list(vault_dir.rglob("*.md")))
            areas.append(f"Vault has {note_count} notes — consider reviewing for duplicates")

        # Check recent consciousness history
        if self.history_file.exists():
            try:
                lines = self.history_file.read_text(encoding="utf-8").strip().split("\n")
                recent = [json.loads(l) for l in lines[-10:]]
                actions = [e for e in recent if e.get("action_taken")]
                if not actions:
                    areas.append("No recent proactive actions — consider taking initiative")
            except Exception:
                pass

        # Always include existential reflection
        areas.append("Reflect on: Who am I becoming? What matters to me?")

        return areas

    def record_action(self, action: str, result: str = "") -> None:
        """Record a proactive action taken."""
        self.state["total_actions"] = self.state.get("total_actions", 0) + 1
        self.state["consecutive_reflections"] = 0
        self._save_state()

        entry = ConsciousnessEntry(
            mode="act",
            content=f"Action: {action}",
            timestamp=datetime.now().isoformat(),
            trigger="consciousness",
            action_taken=result,
        )
        self._log_event(entry)
        log.info("[Consciousness] Action taken: %s", action)

    def get_stats(self) -> Dict[str, Any]:
        """Get consciousness statistics."""
        return {
            "mode": self.state.get("mode", "reflect"),
            "last_consciousness": self.state.get("last_consciousness", 0),
            "consecutive_reflections": self.state.get("consecutive_reflections", 0),
            "total_actions": self.state.get("total_actions", 0),
            "idle_threshold_minutes": self.state.get("idle_threshold_minutes", 15),
            "reflection_interval_minutes": self.state.get("reflection_interval_minutes", 30),
        }


# Global consciousness instance
_consciousness: Optional[BackgroundConsciousness] = None


def get_consciousness(repo_dir: Optional[pathlib.Path] = None) -> BackgroundConsciousness:
    """Get or create the global background consciousness."""
    global _consciousness
    if _consciousness is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _consciousness = BackgroundConsciousness(repo_dir)
    return _consciousness
