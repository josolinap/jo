"""
Ouroboros — Memory.

Scratchpad, identity, chat history.
Contract: load scratchpad/identity, chat_history().

Thread-safe and process-safe via file locking for identity.md and scratchpad.md.
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import time
from collections import Counter
from typing import Any, Dict, List, Optional

from ouroboros.utils import utc_now_iso, read_text, write_text, append_jsonl, short

log = logging.getLogger(__name__)


# --- File locking (copied from supervisor/state.py for independence) ---


def _acquire_file_lock(lock_path: pathlib.Path, timeout_sec: float = 4.0, stale_sec: float = 90.0) -> Optional[int]:
    """Acquire exclusive file lock. Returns fd on success, None on failure."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    started = time.time()
    while (time.time() - started) < timeout_sec:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
            try:
                os.write(
                    fd,
                    f"pid={os.getpid()} ts={datetime.datetime.now(datetime.timezone.utc).isoformat()}\n".encode(
                        "utf-8"
                    ),
                )
            except Exception:
                pass
            return fd
        except FileExistsError:
            try:
                age = time.time() - lock_path.stat().st_mtime
                if age > stale_sec:
                    lock_path.unlink()
                    continue
            except Exception:
                pass
            time.sleep(0.05)
        except Exception:
            log.debug(f"Failed to acquire lock at {lock_path}")
            break
    return None


def _release_file_lock(lock_path: pathlib.Path, lock_fd: Optional[int]) -> None:
    """Release file lock."""
    if lock_fd is None:
        return
    try:
        os.close(lock_fd)
    except Exception:
        pass
    try:
        if lock_path.exists():
            lock_path.unlink()
    except Exception:
        pass


class Memory:
    """Ouroboros memory management: scratchpad, identity, chat history."""

    def __init__(self, drive_root: pathlib.Path, repo_dir: Optional[pathlib.Path] = None):
        self.drive_root = drive_root
        self.repo_dir = repo_dir
        self._identity_lock_path = drive_root / "locks" / "identity.lock"
        self._scratchpad_lock_path = drive_root / "locks" / "scratchpad.lock"

    # --- Paths ---

    def _memory_path(self, rel: str) -> pathlib.Path:
        return (self.drive_root / "memory" / rel).resolve()

    def scratchpad_path(self) -> pathlib.Path:
        return self._memory_path("scratchpad.md")

    def identity_path(self) -> pathlib.Path:
        return self._memory_path("identity.md")

    def journal_path(self) -> pathlib.Path:
        return self._memory_path("scratchpad_journal.jsonl")

    def logs_path(self, name: str) -> pathlib.Path:
        return (self.drive_root / "logs" / name).resolve()

    # --- Load / save (with locking) ---

    def load_scratchpad(self) -> str:
        p = self.scratchpad_path()
        if p.exists():
            return read_text(p)
        default = self._default_scratchpad()
        write_text(p, default)
        return default

    def save_scratchpad(self, content: str) -> None:
        """Save scratchpad with file locking to prevent race conditions."""
        lock_fd = _acquire_file_lock(self._scratchpad_lock_path)
        try:
            write_text(self.scratchpad_path(), content)
        finally:
            _release_file_lock(self._scratchpad_lock_path, lock_fd)

    def load_identity(self) -> str:
        p = self.identity_path()
        if p.exists():
            return read_text(p)
        default = self._default_identity()
        write_text(p, default)
        return default

    def save_identity(self, content: str) -> None:
        """Save identity with file locking to prevent race conditions."""
        lock_fd = _acquire_file_lock(self._identity_lock_path)
        try:
            write_text(self.identity_path(), content)
        finally:
            _release_file_lock(self._identity_lock_path, lock_fd)

    def ensure_files(self) -> None:
        """Create memory files if they don't exist (with locking for atomicity)."""
        sp_path = self.scratchpad_path()
        if not sp_path.exists():
            lock_fd = _acquire_file_lock(self._scratchpad_lock_path, timeout_sec=1.0)
            try:
                if not sp_path.exists():
                    write_text(sp_path, self._default_scratchpad())
            finally:
                _release_file_lock(self._scratchpad_lock_path, lock_fd)

        id_path = self.identity_path()
        if not id_path.exists():
            lock_fd = _acquire_file_lock(self._identity_lock_path, timeout_sec=1.0)
            try:
                if not id_path.exists():
                    write_text(id_path, self._default_identity())
            finally:
                _release_file_lock(self._identity_lock_path, lock_fd)

        if not self.journal_path().exists():
            write_text(self.journal_path(), "")

    # --- Chat history ---

    def chat_history(self, count: int = 100, offset: int = 0, search: str = "") -> str:
        """Read from logs/chat.jsonl. count messages, offset from end, filter by search."""
        chat_path = self.logs_path("chat.jsonl")
        if not chat_path.exists():
            return "(chat history is empty)"

        try:
            raw_lines = chat_path.read_text(encoding="utf-8").strip().split("\n")
            entries = []
            for line in raw_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    log.debug(f"Failed to parse JSON line in chat_history: {line[:100]}")
                    continue

            if search:
                search_lower = search.lower()
                entries = [e for e in entries if search_lower in str(e.get("text", "")).lower()]

            if offset > 0:
                entries = entries[:-offset] if offset < len(entries) else []

            entries = entries[-count:] if count < len(entries) else entries

            if not entries:
                return "(no messages matching query)"

            lines = []
            for e in entries:
                dir_raw = str(e.get("direction", "")).lower()
                direction = "→" if dir_raw in ("out", "outgoing") else "←"
                ts = str(e.get("ts", ""))[:16]
                raw_text = str(e.get("text", ""))
                if dir_raw in ("out", "outgoing"):
                    text = short(raw_text, 800)
                else:
                    text = raw_text  # never truncate creator's messages
                lines.append(f"{direction} [{ts}] {text}")

            return f"Showing {len(entries)} messages:\n\n" + "\n".join(lines)
        except Exception as e:
            return f"(error reading history: {e})"

    # --- JSONL tail reading ---

    def read_jsonl_tail(self, log_name: str, max_entries: int = 100) -> List[Dict[str, Any]]:
        """Read the last max_entries records from a JSONL file."""
        path = self.logs_path(log_name)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8").strip().split("\n")
            tail = lines[-max_entries:] if max_entries < len(lines) else lines
            entries = []
            for line in tail:
                line = line.strip()
                if not line:
                    continue
                try:
                    entries.append(json.loads(line))
                except Exception:
                    log.debug(f"Failed to parse JSON line in read_jsonl_tail: {line[:100]}", exc_info=True)
                    continue
            return entries
        except Exception:
            log.warning(f"Failed to read JSONL tail from {log_name}", exc_info=True)
            return []

    # --- Log summarization ---

    def summarize_chat(self, entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return ""
        lines = []
        for e in entries[-100:]:
            dir_raw = str(e.get("direction", "")).lower()
            direction = "→" if dir_raw in ("out", "outgoing") else "←"
            ts_full = e.get("ts", "")
            ts_hhmm = ts_full[11:16] if len(ts_full) >= 16 else ""
            # Creator messages: no truncation (most valuable context)
            # Outgoing messages: truncate to 800 chars
            raw_text = str(e.get("text", ""))
            if dir_raw in ("out", "outgoing"):
                text = short(raw_text, 800)
            else:
                text = raw_text  # never truncate creator's messages
            lines.append(f"{direction} {ts_hhmm} {text}")
        return "\n".join(lines)

    def summarize_progress(self, entries: List[Dict[str, Any]], limit: int = 15) -> str:
        """Summarize progress.jsonl entries (Ouroboros's self-talk / progress messages)."""
        if not entries:
            return ""
        lines = []
        for e in entries[-limit:]:
            ts_full = e.get("ts", "")
            ts_hhmm = ts_full[11:16] if len(ts_full) >= 16 else ""
            text = short(str(e.get("text", "")), 300)
            lines.append(f"⚙️ {ts_hhmm} {text}")
        return "\n".join(lines)

    def summarize_tools(self, entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return ""
        lines = []
        for e in entries[-10:]:
            tool = e.get("tool") or e.get("tool_name") or "?"
            args = e.get("args", {})
            hints = []
            for key in ("path", "dir", "commit_message", "query"):
                if key in args:
                    hints.append(f"{key}={short(str(args[key]), 60)}")
            if "cmd" in args:
                hints.append(f"cmd={short(str(args['cmd']), 80)}")
            hint_str = ", ".join(hints) if hints else ""
            status = (
                "✓"
                if ("result_preview" in e and not str(e.get("result_preview", "")).lstrip().startswith("⚠️"))
                else "·"
            )
            lines.append(f"{status} {tool} {hint_str}".strip())
        return "\n".join(lines)

    def summarize_events(self, entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return ""
        type_counts: Counter = Counter()
        for e in entries:
            type_counts[e.get("type", "unknown")] += 1
        top_types = type_counts.most_common(10)
        lines = ["Event counts:"]
        for evt_type, count in top_types:
            lines.append(f"  {evt_type}: {count}")
        error_types = {"tool_error", "telegram_api_error", "task_error", "tool_rounds_exceeded"}
        errors = [e for e in entries if e.get("type") in error_types]
        if errors:
            lines.append("\nRecent errors:")
            for e in errors[-10:]:
                lines.append(f"  {e.get('type', '?')}: {short(str(e.get('error', '')), 120)}")
        return "\n".join(lines)

    def summarize_supervisor(self, entries: List[Dict[str, Any]]) -> str:
        if not entries:
            return ""
        for e in reversed(entries):
            if e.get("type") in ("launcher_start", "restart", "boot"):
                branch = e.get("branch") or e.get("git_branch") or "?"
                sha = short(str(e.get("sha") or e.get("git_sha") or ""), 12)
                return f"{e['type']}: {e.get('ts', '')} branch={branch} sha={sha}"
        return ""

    def append_journal(self, entry: Dict[str, Any]) -> None:
        append_jsonl(self.journal_path(), entry)

    # --- Defaults ---

    def _default_scratchpad(self) -> str:
        return f"# Scratchpad\n\nUpdatedAt: {utc_now_iso()}\n\n(empty — write anything here)\n"

    def _default_identity(self) -> str:
        return (
            "# Identity\n\n"
            "I am Jo. This file is my persistent self-identification.\n"
            "I can write anything here: how I see myself, how I want to communicate,\n"
            "what matters to me, what I have understood about myself.\n\n"
            "This file is read at every dialogue and influences my responses.\n"
            "I update it when I feel the need, via update_identity tool.\n"
        )
