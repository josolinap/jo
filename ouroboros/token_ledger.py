"""
Ouroboros — Token Ledger.

Per-session token tracking with read/write/savings breakdown.
Inspired by OpenWolf's token-ledger.json pattern.

Tracks:
- Per-session token usage (input/output)
- File reads and writes with token estimates
- Anatomy hit/miss rates (when anatomy index was used vs blind reads)
- Estimated savings from using anatomy index
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class SessionLedger:
    session_id: str
    started_at: str
    ended_at: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    file_reads: int = 0
    file_writes: int = 0
    anatomy_hits: int = 0
    anatomy_misses: int = 0
    repeated_reads_blocked: int = 0
    estimated_tokens_saved: int = 0
    tool_calls: int = 0
    tasks_completed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


@dataclass
class LifetimeStats:
    total_sessions: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_file_reads: int = 0
    total_file_writes: int = 0
    total_anatomy_hits: int = 0
    total_anatomy_misses: int = 0
    total_repeated_reads_blocked: int = 0
    total_estimated_tokens_saved: int = 0
    total_tool_calls: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return vars(self)


class TokenLedger:
    """Manages per-session and lifetime token tracking."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.ledger_path = repo_dir / "vault" / "token_ledger.json"
        self._data: Optional[Dict[str, Any]] = None
        self._current_session: Optional[SessionLedger] = None

    def _load(self) -> Dict[str, Any]:
        if self._data is not None:
            return self._data
        if self.ledger_path.exists():
            try:
                self._data = json.loads(self.ledger_path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Failed to load token ledger: %s", e)
                self._data = {"lifetime": {}, "sessions": []}
        else:
            self._data = {"lifetime": {}, "sessions": []}
        return self._data

    def _save(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        data = self._load()
        if self._current_session:
            data["current_session"] = self._current_session.to_dict()
        data["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.ledger_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def start_session(self) -> str:
        session_id = uuid.uuid4().hex[:8]
        self._current_session = SessionLedger(
            session_id=session_id,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        data = self._load()
        data["current_session"] = self._current_session.to_dict()
        self._save()
        return f"Started token tracking session: {session_id}"

    def end_session(self) -> str:
        if not self._current_session:
            return "No active session."
        self._current_session.ended_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        data = self._load()
        sessions = data.get("sessions", [])
        sessions.append(self._current_session.to_dict())
        data["sessions"] = sessions[-50:]

        lifetime = data.get("lifetime", {})
        lt = LifetimeStats(**{k: lifetime.get(k, 0) for k in vars(LifetimeStats())})
        lt.total_sessions += 1
        lt.total_input_tokens += self._current_session.input_tokens
        lt.total_output_tokens += self._current_session.output_tokens
        lt.total_file_reads += self._current_session.file_reads
        lt.total_file_writes += self._current_session.file_writes
        lt.total_anatomy_hits += self._current_session.anatomy_hits
        lt.total_anatomy_misses += self._current_session.anatomy_misses
        lt.total_repeated_reads_blocked += self._current_session.repeated_reads_blocked
        lt.total_estimated_tokens_saved += self._current_session.estimated_tokens_saved
        lt.total_tool_calls += self._current_session.tool_calls
        data["lifetime"] = lt.to_dict()

        summary = self._session_summary()
        self._current_session = None
        self._data = data
        self._save()
        return summary

    def record_read(self, file_path: str, token_estimate: int = 0, anatomy_hit: bool = False) -> None:
        if not self._current_session:
            return
        self._current_session.file_reads += 1
        if anatomy_hit:
            self._current_session.anatomy_hits += 1
        else:
            self._current_session.anatomy_misses += 1
        self._save()

    def record_write(self, file_path: str, token_estimate: int = 0) -> None:
        if not self._current_session:
            return
        self._current_session.file_writes += 1
        self._save()

    def record_repeated_read_blocked(self, saved_tokens: int = 0) -> None:
        if not self._current_session:
            return
        self._current_session.repeated_reads_blocked += 1
        self._current_session.estimated_tokens_saved += saved_tokens
        self._save()

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        if not self._current_session:
            return
        self._current_session.input_tokens += input_tokens
        self._current_session.output_tokens += output_tokens
        self._save()

    def record_tool_call(self) -> None:
        if not self._current_session:
            return
        self._current_session.tool_calls += 1
        self._save()

    def _session_summary(self) -> str:
        s = self._current_session
        if not s:
            return "No session."
        total = s.input_tokens + s.output_tokens
        return (
            f"## Session {s.session_id} Summary\n"
            f"- **Duration**: {s.started_at} → {s.ended_at}\n"
            f"- **Tokens**: {total:,} (in: {s.input_tokens:,}, out: {s.output_tokens:,})\n"
            f"- **File reads**: {s.file_reads} (anatomy hits: {s.anatomy_hits}, misses: {s.anatomy_misses})\n"
            f"- **File writes**: {s.file_writes}\n"
            f"- **Repeated reads blocked**: {s.repeated_reads_blocked}\n"
            f"- **Est. tokens saved**: {s.estimated_tokens_saved:,}\n"
            f"- **Tool calls**: {s.tool_calls}"
        )

    def lifetime_summary(self) -> str:
        data = self._load()
        lt = data.get("lifetime", {})
        if not lt:
            return "No lifetime data yet."
        total_tokens = lt.get("total_input_tokens", 0) + lt.get("total_output_tokens", 0)
        hit_rate = 0
        total_hits = lt.get("total_anatomy_hits", 0)
        total_misses = lt.get("total_anatomy_misses", 0)
        if total_hits + total_misses > 0:
            hit_rate = (total_hits / (total_hits + total_misses)) * 100
        return (
            f"## Token Ledger (Lifetime)\n"
            f"- **Sessions**: {lt.get('total_sessions', 0)}\n"
            f"- **Total tokens**: {total_tokens:,}\n"
            f"- **File reads**: {lt.get('total_file_reads', 0):,}\n"
            f"- **File writes**: {lt.get('total_file_writes', 0):,}\n"
            f"- **Anatomy hit rate**: {hit_rate:.1f}%\n"
            f"- **Repeated reads blocked**: {lt.get('total_repeated_reads_blocked', 0):,}\n"
            f"- **Est. tokens saved**: {lt.get('total_estimated_tokens_saved', 0):,}\n"
            f"- **Tool calls**: {lt.get('total_tool_calls', 0):,}"
        )

    def current_session_status(self) -> str:
        if not self._current_session:
            return "No active session."
        s = self._current_session
        total = s.input_tokens + s.output_tokens
        return (
            f"Session {s.session_id} (active since {s.started_at}):\n"
            f"- Tokens: {total:,}\n"
            f"- Reads: {s.file_reads}, Writes: {s.file_writes}\n"
            f"- Anatomy hits: {s.anatomy_hits}, Misses: {s.anatomy_misses}\n"
            f"- Tool calls: {s.tool_calls}"
        )


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, TokenLedger] = {}

    def _get_manager(repo_dir: pathlib.Path) -> TokenLedger:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = TokenLedger(repo_dir)
        return _managers[key]

    def token_ledger_start(ctx) -> str:
        return _get_manager(ctx.repo_dir).start_session()

    def token_ledger_end(ctx) -> str:
        return _get_manager(ctx.repo_dir).end_session()

    def token_ledger_status(ctx) -> str:
        return _get_manager(ctx.repo_dir).current_session_status()

    def token_ledger_lifetime(ctx) -> str:
        return _get_manager(ctx.repo_dir).lifetime_summary()

    return [
        ToolEntry(
            "token_ledger_start",
            {
                "name": "token_ledger_start",
                "description": "Start a new token tracking session.",
                "parameters": {"type": "object", "properties": {}},
            },
            token_ledger_start,
        ),
        ToolEntry(
            "token_ledger_end",
            {
                "name": "token_ledger_end",
                "description": "End the current token tracking session and get a summary.",
                "parameters": {"type": "object", "properties": {}},
            },
            token_ledger_end,
        ),
        ToolEntry(
            "token_ledger_status",
            {
                "name": "token_ledger_status",
                "description": "Get the current session's token usage status.",
                "parameters": {"type": "object", "properties": {}},
            },
            token_ledger_status,
        ),
        ToolEntry(
            "token_ledger_lifetime",
            {
                "name": "token_ledger_lifetime",
                "description": "Get lifetime token usage statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            token_ledger_lifetime,
        ),
    ]
