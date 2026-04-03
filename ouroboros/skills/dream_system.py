"""
Jo — Dream System.

Background memory consolidation engine inspired by Claude Code's autoDream.
Runs as a forked subagent that performs a reflective pass over memory files.

Three-Gate Trigger:
1. Time gate: 24 hours since last dream
2. Session gate: At least 5 sessions since last dream
3. Lock gate: Acquire consolidation lock (prevents concurrent dreams)

Four Phases:
1. Orient: Read MEMORY.md, skim existing topic files
2. Gather Recent Signal: Find new information worth persisting
3. Consolidate: Write/update memory files, convert dates, delete contradictions
4. Prune and Index: Keep MEMORY.md under limits, remove stale pointers
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class DreamPhase(Enum):
    ORIENT = "orient"
    GATHER = "gather"
    CONSOLIDATE = "consolidate"
    PRUNE = "prune"


@dataclass
class DreamState:
    """State of the dream system."""

    last_dream_time: float = 0.0
    sessions_since_dream: int = 0
    is_dreaming: bool = False
    current_phase: Optional[DreamPhase] = None
    total_dreams: int = 0
    last_dream_summary: str = ""


class DreamSystem:
    """Background memory consolidation engine."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.memory_dir = repo_dir / "memory"
        self.dream_state_path = self.memory_dir / "dream_state.json"
        self.memory_md_path = self.memory_dir / "MEMORY.md"
        self.state = self._load_state()

    def _load_state(self) -> DreamState:
        """Load dream state from file."""
        if self.dream_state_path.exists():
            try:
                data = json.loads(self.dream_state_path.read_text(encoding="utf-8"))
                return DreamState(**data)
            except Exception as e:
                log.debug(f"Failed to load dream state: {e}")
        return DreamState()

    def _save_state(self) -> None:
        """Save dream state to file."""
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.dream_state_path.write_text(
            json.dumps(
                {
                    "last_dream_time": self.state.last_dream_time,
                    "sessions_since_dream": self.state.sessions_since_dream,
                    "is_dreaming": self.state.is_dreaming,
                    "current_phase": self.state.current_phase.value if self.state.current_phase else None,
                    "total_dreams": self.state.total_dreams,
                    "last_dream_summary": self.state.last_dream_summary,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def record_session(self) -> None:
        """Record that a session has occurred."""
        self.state.sessions_since_dream += 1
        self._save_state()

    def should_dream(self) -> bool:
        """Check if all three gates pass for dreaming."""
        if self.state.is_dreaming:
            return False

        # Time gate: 24 hours since last dream
        time_gate_passed = (time.time() - self.state.last_dream_time) > 86400  # 24 hours

        # Session gate: At least 5 sessions since last dream
        session_gate_passed = self.state.sessions_since_dream >= 5

        # Lock gate: Must be able to acquire consolidation lock
        lock_gate_passed = self._acquire_consolidation_lock()

        return time_gate_passed and session_gate_passed and lock_gate_passed

    def _acquire_consolidation_lock(self) -> bool:
        """Acquire consolidation lock to prevent concurrent dreams."""
        lock_path = self.memory_dir / ".dream_lock"
        try:
            if lock_path.exists():
                lock_age = time.time() - lock_path.stat().st_mtime
                if lock_age < 3600:  # Lock is less than 1 hour old
                    return False
                # Stale lock, remove it
                lock_path.unlink()

            lock_path.write_text(str(time.time()), encoding="utf-8")
            return True
        except Exception:
            return False

    def _release_consolidation_lock(self) -> None:
        """Release consolidation lock."""
        lock_path = self.memory_dir / ".dream_lock"
        try:
            if lock_path.exists():
                lock_path.unlink()
        except Exception:
            pass

    def start_dream(self) -> bool:
        """Start the dream process if gates pass."""
        if not self.should_dream():
            return False

        self.state.is_dreaming = True
        self._save_state()
        return True

    def get_dream_prompt(self) -> str:
        """Get the prompt for the dream subagent."""
        return """You are performing a DREAM - a reflective pass over your memory files.

Your goal is to synthesize what you've learned recently into durable, well-organized memories so that future sessions can orient quickly.

## DREAM PHASES

### Phase 1: ORIENT
- Read MEMORY.md to understand current memory structure
- Skim existing topic files to identify what needs updating
- Note any contradictions or stale information

### Phase 2: GATHER RECENT SIGNAL
- Find new information worth persisting from recent sessions
- Prioritize: daily logs → drifted memories → recent chat history
- Look for patterns, decisions, and lessons learned

### Phase 3: CONSOLIDATE
- Write or update memory files with new information
- Convert relative dates to absolute dates
- Delete contradicted facts
- Merge duplicate information

### Phase 4: PRUNE AND INDEX
- Keep MEMORY.md under 200 lines AND ~25KB
- Remove stale pointers
- Resolve contradictions
- Update the index to reflect current state

## RULES
- You have READ-ONLY access to the codebase
- You can WRITE to memory files only
- Do not modify any code files
- Focus on durability and organization
- Be concise but comprehensive

Begin your dream now.
"""

    def complete_dream(self, summary: str = "") -> None:
        """Complete the dream process."""
        self.state.is_dreaming = False
        self.state.current_phase = None
        self.state.last_dream_time = time.time()
        self.state.sessions_since_dream = 0
        self.state.total_dreams += 1
        self.state.last_dream_summary = summary
        self._release_consolidation_lock()
        self._save_state()

    def get_status(self) -> Dict[str, Any]:
        """Get dream system status."""
        return {
            "is_dreaming": self.state.is_dreaming,
            "current_phase": self.state.current_phase.value if self.state.current_phase else None,
            "total_dreams": self.state.total_dreams,
            "last_dream_time": datetime.fromtimestamp(self.state.last_dream_time).isoformat()
            if self.state.last_dream_time > 0
            else "Never",
            "sessions_since_dream": self.state.sessions_since_dream,
            "time_since_last_dream_hours": round((time.time() - self.state.last_dream_time) / 3600, 1)
            if self.state.last_dream_time > 0
            else "N/A",
            "gates": {
                "time_gate": (time.time() - self.state.last_dream_time) > 86400,
                "session_gate": self.state.sessions_since_dream >= 5,
                "lock_gate": not (self.memory_dir / ".dream_lock").exists(),
            },
        }


# Global dream system instance
_system: Optional[DreamSystem] = None


def get_dream_system(repo_dir: Optional[pathlib.Path] = None) -> DreamSystem:
    """Get or create the global dream system."""
    global _system
    if _system is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _system = DreamSystem(repo_dir)
    return _system
