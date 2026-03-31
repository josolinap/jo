"""Hybrid checkpointing for state recovery.

Frequent lightweight deltas + periodic full checkpoints.
Supports Principle 1 (Continuity): unbroken memory across restarts.

Following Principle 5 (Minimalism): under 200 lines.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class HybridCheckpointer:
    """Hybrid checkpointing: frequent deltas + periodic full snapshots.

    Combines fast lightweight snapshots (every N steps) with
    periodic full checkpoints (every M minutes) for optimal
    recovery with minimal overhead.

    Usage:
        cp = HybridCheckpointer(fast_path="/tmp/deltas", cold_path="/tmp/full")
        await cp.checkpoint(state, step=42)
        restored = await cp.restore()
    """

    fast_path: Path = Path("/tmp/checkpoints/deltas")
    cold_path: Path = Path("/tmp/checkpoints/full")
    full_checkpoint_interval: int = 50
    _deltas: List[int] = field(default_factory=list)
    _steps_since_full: int = 0
    _last_full_state: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        """Create checkpoint directories."""
        self.fast_path.mkdir(parents=True, exist_ok=True)
        self.cold_path.mkdir(parents=True, exist_ok=True)

    async def checkpoint(self, state: Dict[str, Any], step: int) -> None:
        """Save checkpoint for current step.

        Args:
            state: Current state dict
            step: Current step number
        """
        # Compute delta from last state
        delta = self._compute_delta(state)

        # Save delta to fast store
        delta_path = self.fast_path / f"delta_{step}.json"
        try:
            delta_path.write_text(json.dumps({"step": step, "delta": delta, "ts": time.time()}), encoding="utf-8")
            self._deltas.append(step)
        except Exception as e:
            log.warning(f"Failed to save delta {step}: {e}")

        self._steps_since_full += 1

        # Periodic full checkpoint
        if self._steps_since_full >= self.full_checkpoint_interval:
            await self._save_full(state, step)

    async def _save_full(self, state: Dict[str, Any], step: int) -> None:
        """Save full checkpoint to cold store."""
        full_path = self.cold_path / "full_checkpoint.json"
        try:
            full_path.write_text(
                json.dumps({"state": state, "step": step, "ts": time.time()}),
                encoding="utf-8",
            )
            self._last_full_state = state

            # Clean up old deltas
            for delta_step in self._deltas:
                old_delta = self.fast_path / f"delta_{delta_step}.json"
                old_delta.unlink(missing_ok=True)
            self._deltas.clear()
            self._steps_since_full = 0

            log.info(f"Full checkpoint saved at step {step}")
        except Exception as e:
            log.warning(f"Failed to save full checkpoint: {e}")

    async def restore(self) -> Optional[Dict[str, Any]]:
        """Restore state from checkpoints.

        Returns:
            Restored state dict or None if no checkpoint exists
        """
        # Try to load full checkpoint
        full_path = self.cold_path / "full_checkpoint.json"
        if not full_path.exists():
            log.info("No checkpoint found")
            return None

        try:
            full_data = json.loads(full_path.read_text(encoding="utf-8"))
            state = full_data.get("state", {})
            base_step = full_data.get("step", 0)

            # Replay deltas
            delta_files = sorted(self.fast_path.glob("delta_*.json"))
            for delta_file in delta_files:
                try:
                    delta_data = json.loads(delta_file.read_text(encoding="utf-8"))
                    delta_step = delta_data.get("step", 0)
                    if delta_step > base_step:
                        state = self._apply_delta(state, delta_data.get("delta", {}))
                except Exception as e:
                    log.warning(f"Failed to replay delta {delta_file}: {e}")

            log.info(f"Restored state from step {base_step} + {len(delta_files)} deltas")
            return state
        except Exception as e:
            log.error(f"Failed to restore checkpoint: {e}")
            return None

    def _compute_delta(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Compute delta from last known state."""
        if self._last_full_state is None:
            return state

        delta = {}
        for key, value in state.items():
            if key not in self._last_full_state or self._last_full_state[key] != value:
                delta[key] = value
        return delta

    def _apply_delta(self, state: Dict[str, Any], delta: Dict[str, Any]) -> Dict[str, Any]:
        """Apply delta to state."""
        merged = dict(state)
        merged.update(delta)
        return merged

    def generate_briefing(self, state: Dict[str, Any]) -> str:
        """Generate compact briefing for cold restart.

        Following Principle 1 (Continuity): preserve narrative.
        """
        task = state.get("current_task", "unknown")
        completed = state.get("completed_subtasks", [])
        blocked = state.get("blocked_items", [])
        next_step = state.get("next_action", "continue")

        return (
            f"TASK: {task}\n"
            f"COMPLETED: {', '.join(str(c)[:50] for c in completed[:5])}\n"
            f"BLOCKED: {', '.join(str(b)[:50] for b in blocked[:3])}\n"
            f"NEXT: {next_step}\n"
        )

    def get_status(self) -> Dict[str, Any]:
        """Get checkpointer status."""
        return {
            "fast_path": str(self.fast_path),
            "cold_path": str(self.cold_path),
            "pending_deltas": len(self._deltas),
            "steps_since_full": self._steps_since_full,
            "has_full_checkpoint": (self.cold_path / "full_checkpoint.json").exists(),
        }
