"""
Supervisor — Worker lifecycle management.

Multiprocessing workers, worker health, direct chat handling.
Queue operations moved to supervisor.queue.
"""

from __future__ import annotations
import logging

log = logging.getLogger(__name__)

import datetime
import json
import multiprocessing as mp
import os
import pathlib
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

from supervisor.state import load_state, append_jsonl
from supervisor import git_ops
from supervisor.telegram import send_with_budget


# ---------------------------------------------------------------------------
# Module-level config (set via init())
# ---------------------------------------------------------------------------
REPO_DIR: pathlib.Path = pathlib.Path.cwd()
DRIVE_ROOT: pathlib.Path = pathlib.Path.home() / ".jo_data"
MAX_WORKERS: int = 5
SOFT_TIMEOUT_SEC: int = 600
HARD_TIMEOUT_SEC: int = 1800
HEARTBEAT_STALE_SEC: int = 120
QUEUE_MAX_RETRIES: int = 1
TOTAL_BUDGET_LIMIT: float = 0.0
BRANCH_DEV: str = "dev"
BRANCH_STABLE: str = "stable"

_CTX = None
_LAST_SPAWN_TIME: float = 0.0  # grace period: don't count dead workers right after spawn
_SPAWN_GRACE_SEC: float = 90.0  # workers need up to ~60s to init on Colab (spawn + pip + Drive FUSE)

# On Linux/Colab, "spawn" re-imports __main__ (colab_launcher.py) in child processes.
# Since launcher has top-level side effects, this causes worker child crashes (exitcode=1).
# Use "fork" by default on Linux; allow override via env.
_DEFAULT_WORKER_START_METHOD = "fork" if sys.platform.startswith("linux") else "spawn"
_WORKER_START_METHOD = (
    str(os.environ.get("OUROBOROS_WORKER_START_METHOD", _DEFAULT_WORKER_START_METHOD) or _DEFAULT_WORKER_START_METHOD)
    .strip()
    .lower()
)
if _WORKER_START_METHOD not in {"fork", "spawn", "forkserver"}:
    _WORKER_START_METHOD = _DEFAULT_WORKER_START_METHOD


def _get_ctx():
    """Return multiprocessing context used for worker processes."""
    global _CTX
    if _CTX is None:
        _CTX = mp.get_context(_WORKER_START_METHOD)
    return _CTX


def init(
    repo_dir: pathlib.Path,
    drive_root: pathlib.Path,
    max_workers: int,
    soft_timeout: int,
    hard_timeout: int,
    total_budget_limit: float,
    branch_dev: str = "dev",
    branch_stable: str = "stable",
) -> None:
    global REPO_DIR, DRIVE_ROOT, MAX_WORKERS, SOFT_TIMEOUT_SEC, HARD_TIMEOUT_SEC
    global TOTAL_BUDGET_LIMIT, BRANCH_DEV, BRANCH_STABLE
    REPO_DIR = repo_dir
    DRIVE_ROOT = drive_root
    MAX_WORKERS = max_workers
    SOFT_TIMEOUT_SEC = soft_timeout
    HARD_TIMEOUT_SEC = hard_timeout
    TOTAL_BUDGET_LIMIT = total_budget_limit
    BRANCH_DEV = branch_dev
    BRANCH_STABLE = branch_stable

    # Initialize queue module
    from supervisor import queue

    queue.init(drive_root, soft_timeout, hard_timeout)
    queue.init_queue_refs(PENDING, RUNNING, QUEUE_SEQ_COUNTER_REF)


# ---------------------------------------------------------------------------
# Worker data structures
# ---------------------------------------------------------------------------


@dataclass
class Worker:
    wid: int
    proc: mp.Process
    in_q: Any
    busy_task_id: Optional[str] = None


_EVENT_Q = None


def get_event_q():
    """Get the current EVENT_Q, creating if needed."""
    global _EVENT_Q
    if _EVENT_Q is None:
        _EVENT_Q = _get_ctx().Queue()
    return _EVENT_Q


WORKERS: Dict[int, Worker] = {}
PENDING: List[Dict[str, Any]] = []
RUNNING: Dict[str, Dict[str, Any]] = {}
CRASH_TS: List[float] = []
QUEUE_SEQ_COUNTER_REF: Dict[str, int] = {"value": 0}

# Lock for all mutations to PENDING, RUNNING, WORKERS shared collections.
# Canonical definition lives in queue.py; imported here for use by assign_tasks/kill_workers.
from supervisor.queue import _queue_lock


def get_running_task_ids() -> List[str]:
    """Return list of task IDs currently being processed by workers."""
    return [w.busy_task_id for w in WORKERS.values() if w.busy_task_id]


# ---------------------------------------------------------------------------
# Chat agent (direct mode)
# ---------------------------------------------------------------------------
_chat_agent = None


def _get_chat_agent():
    global _chat_agent
    if _chat_agent is None:
        sys.path.insert(0, str(REPO_DIR))
        from ouroboros.agent import make_agent

        _chat_agent = make_agent(
            repo_dir=str(REPO_DIR),
            drive_root=str(DRIVE_ROOT),
            event_queue=get_event_q(),
        )
    return _chat_agent


def handle_chat_direct(
    chat_id: int, text: str, image_data: Optional[Union[Tuple[str, str], Tuple[str, str, str]]] = None
) -> None:
    try:
        agent = _get_chat_agent()
        task = {
            "id": uuid.uuid4().hex[:8],
            "type": "task",
            "chat_id": chat_id,
            "text": text,
            "_is_direct_chat": True,
        }
        if image_data:
            # image_data is (base64, mime) or (base64, mime, caption)
            task["image_base64"] = image_data[0]
            task["image_mime"] = image_data[1]
            if len(image_data) > 2 and image_data[2]:
                task["image_caption"] = image_data[2]
                # Prefer caption as task text if text is empty
                if not text:
                    task["text"] = image_data[2]
        # Fallback for truly empty messages
        if not task["text"]:
            task["text"] = "(image attached)" if image_data else ""
        events = agent.handle_task(task)
        for e in events:
            get_event_q().put(e)
    except Exception as e:
        import traceback

        err_msg = f"⚠️ Error: {type(e).__name__}: {e}"
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "direct_chat_error",
                "error": repr(e),
                "traceback": str(traceback.format_exc())[:2000],
            },
        )
        try:
            from supervisor.telegram import get_tg

            get_tg().send_message(chat_id, err_msg)
        except Exception:
            log.debug("Suppressed exception", exc_info=True)


# ---------------------------------------------------------------------------
# Auto-resume after restart
# ---------------------------------------------------------------------------


def _validate_scratchpad(content: str) -> tuple[bool, str]:
    """Validate scratchpad content before auto-resume.

    Returns (is_valid, reason) tuple.
    """
    if not content:
        return False, "empty content"

    if len(content) > 1_000_000:
        return False, "exceeds 1MB limit"

    if "\x00" in content:
        return False, "contains null bytes (binary corruption)"

    stripped = content.strip()
    if not stripped:
        return False, "only whitespace"

    lines = stripped.splitlines()
    if len(lines) < 3:
        return False, "too few lines"

    has_header = any(ln.strip().startswith("#") for ln in lines)
    has_meaningful_content = any(len(ln.strip()) > 10 for ln in lines if not ln.strip().startswith("#"))

    if not has_header and not has_meaningful_content:
        return False, "no structure or meaningful content"

    return True, "valid"


def auto_resume_after_restart() -> None:
    """If recent restart detected, notify owner and optionally auto-resume work.

    Checks: owner registration, recent restart events, pending_restart_verify.
    Always sends online notification if owner exists and restart detected.
    Auto-resumes scratchpad-based work if scratchpad has substantial content.
    """
    try:
        st = load_state()
        chat_id = st.get("owner_chat_id")
        if not chat_id:
            return

        # Check for recent restart - multiple detection methods
        recent_restart = False

        # Method 1: Check for pending_restart_verify.json (may have been claimed/deleted)
        restart_verify_path = DRIVE_ROOT / "state" / "pending_restart_verify.json"
        if restart_verify_path.exists():
            recent_restart = True

        # Method 2: Check for any claimed verify files (evidence of recent restart)
        if not recent_restart:
            state_dir = DRIVE_ROOT / "state"
            if state_dir.exists():
                for f in state_dir.iterdir():
                    if f.name.startswith("pending_restart_verify.claimed"):
                        try:
                            import time as time_module

                            age = time_module.time() - f.stat().st_mtime
                            if age < 300:  # Within last 5 minutes
                                recent_restart = True
                                break
                        except Exception:
                            pass

        # Method 3: Check supervisor.jsonl for recent launcher_start (within last 10 minutes)
        if not recent_restart:
            sup_log = DRIVE_ROOT / "logs" / "supervisor.jsonl"
            if sup_log.exists():
                try:
                    import time as time_module

                    current_time = time_module.time()
                    lines = sup_log.read_text(encoding="utf-8").strip().split("\n")
                    for line in reversed(lines[-50:]):
                        if not line.strip():
                            continue
                        try:
                            evt = json.loads(line)
                            evt_type = evt.get("type", "")
                            if evt_type in ("launcher_start", "restart", "bootstrap"):
                                evt_ts = evt.get("ts", "")
                                # Rough check: if recent (within last 10 min based on log position)
                                if "T" in evt_ts:
                                    recent_restart = True
                                    break
                        except Exception:
                            continue
                    # If we can't parse but file is recent, assume restart happened
                    if not recent_restart:
                        sup_age = current_time - sup_log.stat().st_mtime
                        if sup_age < 600:  # File modified within 10 minutes
                            recent_restart = True
                except Exception:
                    log.debug("Suppressed exception checking supervisor log", exc_info=True)

        if not recent_restart:
            log.debug("No recent restart detected, skipping auto-resume")
            return

        # Always notify owner that we're back online (separated from auto-resume)
        log.info(f"Restart detected for chat_id={chat_id}, sending online notification")
        try:
            send_with_budget(int(chat_id), "✅ Owner registered. Jo online.")
        except Exception as e:
            log.warning(f"Failed to send online notification: {e}")

        # Check if scratchpad is valid for auto-resume
        scratchpad_path = DRIVE_ROOT / "memory" / "scratchpad.md"
        if not scratchpad_path.exists():
            log.debug("No scratchpad found, skipping auto-resume")
            append_jsonl(
                DRIVE_ROOT / "logs" / "supervisor.jsonl",
                {
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "restart_online_notified",
                },
            )
            return

        try:
            scratchpad = scratchpad_path.read_text(encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed to read scratchpad: {e}, skipping auto-resume")
            append_jsonl(
                DRIVE_ROOT / "logs" / "supervisor.jsonl",
                {
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "restart_online_notified",
                },
            )
            return

        is_valid, reason = _validate_scratchpad(scratchpad)
        if not is_valid:
            log.debug(f"Scratchpad validation failed: {reason}, skipping auto-resume")
            append_jsonl(
                DRIVE_ROOT / "logs" / "supervisor.jsonl",
                {
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "restart_online_notified",
                    "scratchpad_validation": reason,
                },
            )
            return

        stripped = scratchpad.strip()
        content_lines = [
            ln.strip()
            for ln in stripped.splitlines()
            if ln.strip() and not ln.strip().startswith("#") and ln.strip() != "- (empty)"
        ]
        content_lines = [ln for ln in content_lines if not ln.startswith("UpdatedAt:")]

        if len(content_lines) < 2:
            log.debug("Scratchpad too empty for auto-resume")
            append_jsonl(
                DRIVE_ROOT / "logs" / "supervisor.jsonl",
                {
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "restart_online_notified",
                },
            )
            return

        # Auto-resume: inject synthetic message with retry logic
        log.info(f"Auto-resuming after restart for chat_id={chat_id}")

        def _do_resume():
            try:
                time.sleep(3)  # Let everything initialize
                agent = _get_chat_agent()

                # Wait for agent to be ready (with timeout)
                max_wait = 10
                waited = 0
                while agent._busy and waited < max_wait:
                    time.sleep(1)
                    waited += 1

                if agent._busy:
                    log.warning("Agent still busy after wait, attempting resume anyway")

                handle_chat_direct(
                    int(chat_id),
                    "[auto-resume after restart] Continue your work. Read scratchpad and identity — they contain context of what you were doing.",
                    None,
                )
            except Exception as e:
                log.error(f"Auto-resume failed: {e}", exc_info=True)

        import threading

        threading.Thread(target=_do_resume, daemon=True).start()

        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "auto_resume_triggered",
            },
        )
    except Exception as e:
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "auto_resume_error",
                "error": repr(e),
            },
        )
        log.error(f"Auto-resume failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Worker process
# ---------------------------------------------------------------------------


def worker_main(wid: int, in_q: Any, out_q: Any, repo_dir: str, drive_root: str) -> None:
    import sys as _sys
    import traceback as _tb
    import pathlib as _pathlib

    _sys.path.insert(0, repo_dir)
    _drive = _pathlib.Path(drive_root)
    try:
        from ouroboros.agent import make_agent

        agent = make_agent(repo_dir=repo_dir, drive_root=drive_root, event_queue=out_q)
    except Exception as _e:
        _log_worker_crash(wid, _drive, "make_agent", _e, _tb.format_exc())
        return
    while True:
        try:
            task = in_q.get()
            if task is None or task.get("type") == "shutdown":
                break
            events = agent.handle_task(task)
            for e in events:
                e2 = dict(e)
                e2["worker_id"] = wid
                out_q.put(e2)
        except Exception as _e:
            _log_worker_crash(wid, _drive, "handle_task", _e, _tb.format_exc())


def _log_worker_crash(wid: int, drive_root: pathlib.Path, phase: str, exc: Exception, tb: str) -> None:
    """Best-effort: write crash info to supervisor.jsonl from inside worker process."""
    import os as _os

    try:
        path = drive_root / "logs" / "supervisor.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = json.dumps(
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "worker_crash",
                "worker_id": wid,
                "pid": _os.getpid(),
                "phase": phase,
                "error": repr(exc),
                "traceback": str(tb)[:3000],
            },
            ensure_ascii=False,
        )
        with path.open("a", encoding="utf-8") as f:
            f.write(entry + "\n")
    except Exception:
        log.debug("Suppressed exception", exc_info=True)


def _first_worker_boot_event_since(offset_bytes: int) -> Optional[Dict[str, Any]]:
    """Read first worker_boot event written after the given file offset."""
    path = DRIVE_ROOT / "logs" / "events.jsonl"
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            safe_offset = offset_bytes if 0 <= offset_bytes <= size else 0
            f.seek(safe_offset)
            data = f.read().decode("utf-8", errors="replace")
    except Exception:
        log.debug("Suppressed exception", exc_info=True)
        return None

    for line in data.splitlines():
        raw = line.strip()
        if not raw:
            continue
        try:
            evt = json.loads(raw)
        except Exception:
            log.debug("Suppressed exception in loop", exc_info=True)
            continue
        if isinstance(evt, dict) and str(evt.get("type") or "") == "worker_boot":
            return evt
    return None


def _verify_worker_sha_after_spawn(events_offset: int, timeout_sec: float = 90.0) -> None:
    """Verify that newly spawned workers booted with expected current_sha."""
    st = load_state()
    expected_sha = str(st.get("current_sha") or "").strip()
    if not expected_sha:
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "worker_sha_verify_skipped",
                "reason": "missing_current_sha",
            },
        )
        return

    deadline = time.time() + max(float(timeout_sec), 1.0)
    boot_evt = None
    while time.time() < deadline:
        boot_evt = _first_worker_boot_event_since(events_offset)
        if boot_evt is not None:
            break
        time.sleep(0.25)

    if boot_evt is None:
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "worker_sha_verify_timeout",
                "expected_sha": expected_sha,
            },
        )
        return

    observed_sha = str(boot_evt.get("git_sha") or "").strip()
    ok = bool(observed_sha and observed_sha == expected_sha)
    append_jsonl(
        DRIVE_ROOT / "logs" / "supervisor.jsonl",
        {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "type": "worker_sha_verify",
            "ok": ok,
            "expected_sha": expected_sha,
            "observed_sha": observed_sha,
            "worker_pid": boot_evt.get("pid"),
        },
    )
    if not ok and st.get("owner_chat_id"):
        send_with_budget(
            int(st["owner_chat_id"]),
            f"⚠️ Worker SHA mismatch after spawn: expected {expected_sha[:8]}, got {(observed_sha or 'unknown')[:8]}",
        )


def spawn_workers(n: int = 0) -> None:
    global _CTX, _EVENT_Q
    # Force fresh context to ensure workers use latest code
    _CTX = mp.get_context(_WORKER_START_METHOD)
    _EVENT_Q = _CTX.Queue()
    events_path = DRIVE_ROOT / "logs" / "events.jsonl"
    try:
        events_offset = int(events_path.stat().st_size)
    except Exception:
        events_offset = 0

    # --- Snapshot SHA *before* spawning (fixes race condition) ---
    # Reading SHA here guarantees workers always get the SHA that matches
    # the code on disk at spawn time, not a potentially-stale Drive value.
    spawn_sha = git_ops.get_current_sha(REPO_DIR)

    count = n or MAX_WORKERS
    append_jsonl(
        DRIVE_ROOT / "logs" / "supervisor.jsonl",
        {
            "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "type": "worker_spawn_start",
            "start_method": _WORKER_START_METHOD,
            "count": count,
            "spawn_sha": spawn_sha or "unknown",
        },
    )
    WORKERS.clear()
    for i in range(count):
        in_q = _CTX.Queue()
        # Inject expected SHA into worker environment so the worker can
        # self-verify on boot without needing to call back to Drive state.
        worker_env = dict(os.environ)
        if spawn_sha:
            worker_env["OUROBOROS_EXPECTED_SHA"] = spawn_sha
        proc = _CTX.Process(
            target=worker_main,
            args=(i, in_q, _EVENT_Q, str(REPO_DIR), str(DRIVE_ROOT)),
        )
        # mp.Process doesn't support env kwarg directly; set on the object
        # before start() via Process._popen on some platforms.  The portable
        # approach used here is to relay via os.environ inside worker_main.
        if spawn_sha:
            os.environ["OUROBOROS_EXPECTED_SHA"] = spawn_sha
        proc.daemon = True
        proc.start()
        WORKERS[i] = Worker(wid=i, proc=proc, in_q=in_q, busy_task_id=None)
    global _LAST_SPAWN_TIME
    _LAST_SPAWN_TIME = time.time()
    # Run SHA verification in background to avoid blocking the main loop for up to 90s
    threading.Thread(target=_verify_worker_sha_after_spawn, args=(events_offset,), daemon=True).start()


def kill_workers() -> None:
    from supervisor import queue

    with _queue_lock:
        cleared_running = len(RUNNING)
        for w in WORKERS.values():
            if w.proc.is_alive():
                w.proc.terminate()
        for w in WORKERS.values():
            w.proc.join(timeout=5)
        WORKERS.clear()
        RUNNING.clear()
    queue.persist_queue_snapshot(reason="kill_workers")
    if cleared_running:
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "running_cleared_on_kill",
                "count": cleared_running,
            },
        )


def respawn_worker(wid: int) -> None:
    global _LAST_SPAWN_TIME
    ctx = _get_ctx()
    in_q = ctx.Queue()
    # Snapshot SHA before respawn too so the replacement worker gets a
    # consistent expected SHA (same fix as spawn_workers).
    respawn_sha = git_ops.get_current_sha(REPO_DIR)
    if respawn_sha:
        os.environ["OUROBOROS_EXPECTED_SHA"] = respawn_sha
    proc = ctx.Process(target=worker_main, args=(wid, in_q, get_event_q(), str(REPO_DIR), str(DRIVE_ROOT)))
    proc.daemon = True
    proc.start()
    WORKERS[wid] = Worker(wid=wid, proc=proc, in_q=in_q, busy_task_id=None)
    # Give freshly respawned workers the same init grace as startup workers.
    _LAST_SPAWN_TIME = time.time()


def assign_tasks() -> None:
    from supervisor import queue
    from supervisor.state import budget_remaining, EVOLUTION_BUDGET_RESERVE

    with _queue_lock:
        for w in WORKERS.values():
            if w.busy_task_id is None and PENDING:
                # Find first suitable task (skip over-budget evolution tasks)
                chosen_idx = None
                for i, candidate in enumerate(PENDING):
                    if (
                        str(candidate.get("type") or "") == "evolution"
                        and budget_remaining(load_state()) < EVOLUTION_BUDGET_RESERVE
                    ):
                        continue
                    chosen_idx = i
                    break
                if chosen_idx is None:
                    # Only over-budget evolution tasks remain — clean them out
                    PENDING[:] = [t for t in PENDING if str(t.get("type") or "") != "evolution"]
                    queue.persist_queue_snapshot(reason="evolution_dropped_budget")
                    continue
                task = PENDING.pop(chosen_idx)
                w.busy_task_id = task["id"]
                w.in_q.put(task)
                now_ts = time.time()
                RUNNING[task["id"]] = {
                    "task": dict(task),
                    "worker_id": w.wid,
                    "started_at": now_ts,
                    "last_heartbeat_at": now_ts,
                    "soft_sent": False,
                    "attempt": int(task.get("_attempt") or 1),
                }
                task_type = str(task.get("type") or "")
                if task_type in ("evolution", "review"):
                    st = load_state()
                    if st.get("owner_chat_id"):
                        emoji = "🧬" if task_type == "evolution" else "🔎"
                        send_with_budget(
                            int(st["owner_chat_id"]),
                            f"{emoji} {task_type.capitalize()} task {task['id']} started.",
                        )
                queue.persist_queue_snapshot(reason="assign_task")


# ---------------------------------------------------------------------------
# Health + crash storm
# ---------------------------------------------------------------------------


def ensure_workers_healthy() -> None:
    from supervisor import queue

    # Grace period: skip health check right after spawn — workers need time to initialize
    if (time.time() - _LAST_SPAWN_TIME) < _SPAWN_GRACE_SEC:
        return
    busy_crashes = 0
    dead_detections = 0
    for wid, w in list(WORKERS.items()):
        if not w.proc.is_alive():
            dead_detections += 1
            if w.busy_task_id is not None:
                busy_crashes += 1
            append_jsonl(
                DRIVE_ROOT / "logs" / "supervisor.jsonl",
                {
                    "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "type": "worker_dead_detected",
                    "worker_id": wid,
                    "exitcode": w.proc.exitcode,
                    "busy_task_id": w.busy_task_id,
                },
            )
            if w.busy_task_id and w.busy_task_id in RUNNING:
                meta = RUNNING.pop(w.busy_task_id) or {}
                task = meta.get("task") if isinstance(meta, dict) else None
                if isinstance(task, dict):
                    queue.enqueue_task(task, front=True)
            respawn_worker(wid)
            queue.persist_queue_snapshot(reason="worker_respawn_after_crash")

    now = time.time()
    alive_now = sum(1 for w in WORKERS.values() if w.proc.is_alive())
    if dead_detections:
        # Count only meaningful failures:
        # - any crash while a task was running, or
        # - all workers dead at once.
        if busy_crashes > 0 or alive_now == 0:
            CRASH_TS.extend([now] * max(1, dead_detections))
        else:
            # Idle worker deaths with at least one healthy worker are degraded mode,
            # not a crash storm condition.
            CRASH_TS.clear()

    CRASH_TS[:] = [t for t in CRASH_TS if (now - t) < 60.0]
    if len(CRASH_TS) >= 3:
        # Log crash storm but DON'T execv restart — that creates infinite loops.
        # Instead: kill dead workers, notify owner, continue with direct-chat (threading).
        st = load_state()
        append_jsonl(
            DRIVE_ROOT / "logs" / "supervisor.jsonl",
            {
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "type": "crash_storm_detected",
                "crash_count": len(CRASH_TS),
                "worker_count": len(WORKERS),
            },
        )
        if st.get("owner_chat_id"):
            send_with_budget(
                int(st["owner_chat_id"]),
                "⚠️ Frequent worker crashes. Multiprocessing workers disabled, "
                "continuing in direct-chat mode (threading).",
            )
        # Kill all workers — direct chat via handle_chat_direct still works
        kill_workers()
        CRASH_TS.clear()
