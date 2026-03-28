# ============================
# Ouroboros — Runtime launcher (entry point, executed from repository)
# ============================
# Thin orchestrator: secrets, bootstrap, main loop.
# Heavy logic lives in supervisor/ package.

import logging
import os, sys, json, time, uuid, pathlib, subprocess, datetime, threading, queue as _queue_mod
from typing import Any, Dict, List, Optional, Set, Tuple
from dotenv import load_dotenv

log = logging.getLogger(__name__)


# ----------------------------
# 0) Install launcher deps
# ----------------------------
def install_launcher_deps() -> None:
    # Skip installation due to externally-managed-environment
    # Dependencies are already installed
    pass


def ensure_claude_code_cli() -> bool:
    """Best-effort install of Claude Code CLI for Anthropic-powered code edits."""
    local_bin = str(pathlib.Path.home() / ".local" / "bin")
    if local_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = f"{local_bin}:{os.environ.get('PATH', '')}"

    has_cli = subprocess.run(["bash", "-lc", "command -v claude >/dev/null 2>&1"], check=False).returncode == 0
    if has_cli:
        return True

    subprocess.run(["bash", "-lc", "curl -fsSL https://claude.ai/install.sh | bash"], check=False)
    has_cli = subprocess.run(["bash", "-lc", "command -v claude >/dev/null 2>&1"], check=False).returncode == 0
    if has_cli:
        return True

    subprocess.run(
        ["bash", "-lc", "command -v npm >/dev/null 2>&1 && npm install -g @anthropic-ai/claude-code"], check=False
    )
    has_cli = subprocess.run(["bash", "-lc", "command -v claude >/dev/null 2>&1"], check=False).returncode == 0
    return has_cli


# ----------------------------
# 0.1) provide apply_patch shim
# ----------------------------
from ouroboros.apply_patch import install as install_apply_patch
from ouroboros.llm import DEFAULT_LIGHT_MODEL
from supervisor.state import load_state, save_state, append_jsonl
from supervisor.telegram import TelegramClient
import supervisor.workers

# ----------------------------
# 1) Secrets + runtime config
# ----------------------------
# Google Colab imports (only available in Colab environment)
try:
    from google.colab import userdata  # type: ignore
    from google.colab import drive  # type: ignore

    _IN_COLAB = True
except ImportError:
    _IN_COLAB = False
    userdata = None
    drive = None

_LEGACY_CFG_WARNED: Set[str] = set()


def _userdata_get(name: str) -> Optional[str]:
    if not _IN_COLAB:
        return None
    try:
        return userdata.get(name)
    except Exception:
        return None


def get_secret(name: str, default: Optional[str] = None, required: bool = False) -> Optional[str]:
    v = _userdata_get(name)
    if v is None or str(v).strip() == "":
        v = os.environ.get(name, default)
    if required:
        assert v is not None and str(v).strip() != "", f"Missing required secret: {name}"
    return v


def get_cfg(name: str, default: Optional[str] = None, allow_legacy_secret: bool = False) -> Optional[str]:
    v = os.environ.get(name)
    if v is not None and str(v).strip() != "":
        return v
    if allow_legacy_secret:
        legacy = _userdata_get(name)
        if legacy is not None and str(legacy).strip() != "":
            if name not in _LEGACY_CFG_WARNED:
                print(f"[cfg] DEPRECATED: move {name} from Colab Secrets to config cell/env.")
                _LEGACY_CFG_WARNED.add(name)
            return legacy
    return default


def _parse_int_cfg(raw: Optional[str], default: int, minimum: int = 0) -> int:
    try:
        val = int(str(raw))
    except Exception:
        val = default
    return max(minimum, val)


# ----------------------------
# 2) Setup storage paths
# ----------------------------
def _setup_paths():
    # Local/GitHub Actions: use DATA_ROOT env var or default ~/.jo_data
    DRIVE_ROOT = pathlib.Path(os.environ.get("DATA_ROOT", pathlib.Path.home() / ".jo_data")).resolve()
    REPO_DIR = pathlib.Path(os.environ.get("REPO_DIR", pathlib.Path.cwd())).resolve()

    for sub in ["state", "logs", "memory", "index", "locks", "archive"]:
        (DRIVE_ROOT / sub).mkdir(parents=True, exist_ok=True)
    REPO_DIR.mkdir(parents=True, exist_ok=True)

    # Clear stale owner mailbox files from previous session
    try:
        from ouroboros.owner_inject import get_pending_path

        # Clean legacy global file
        _stale_inject = get_pending_path(DRIVE_ROOT)
        if _stale_inject.exists():
            _stale_inject.unlink(missing_ok=True)
        # Clean per-task mailbox dir
        _mailbox_dir = DRIVE_ROOT / "memory" / "owner_mailbox"
        if _mailbox_dir.exists():
            for _f in _mailbox_dir.iterdir():
                _f.unlink(missing_ok=True)
    except Exception:
        pass

    return DRIVE_ROOT, REPO_DIR


# ----------------------------
# 3) Git constants
# ----------------------------
def _setup_git_constants(GITHUB_USER, GITHUB_REPO, GITHUB_TOKEN):
    BRANCH_DEV = "dev"
    BRANCH_STABLE = "stable"
    REMOTE_URL = f"https://{GITHUB_TOKEN}:x-oauth-basic@github.com/{GITHUB_USER}/{GITHUB_REPO}.git"
    return BRANCH_DEV, BRANCH_STABLE, REMOTE_URL


# ----------------------------
# 4) Initialize supervisor modules
# ----------------------------
def _init_supervisor(DRIVE_ROOT, TOTAL_BUDGET_LIMIT, BUDGET_REPORT_EVERY_MESSAGES, TG):
    from supervisor.state import (
        init as state_init,
        load_state,
        save_state,
        append_jsonl,
        update_budget_from_usage,
        status_text,
        rotate_chat_log_if_needed,
        init_state,
    )

    state_init(DRIVE_ROOT, TOTAL_BUDGET_LIMIT)
    init_state()

    from supervisor.telegram import (
        init as telegram_init,
        TelegramClient,
        send_with_budget,
        log_chat,
    )

    telegram_init(
        drive_root=DRIVE_ROOT,
        total_budget_limit=TOTAL_BUDGET_LIMIT,
        budget_report_every=BUDGET_REPORT_EVERY_MESSAGES,
        tg_client=TG,
    )


# ----------------------------
# 5) Background consciousness
# ----------------------------
def _init_consciousness(REPO_DIR, DRIVE_ROOT, TG, OWNER_CHAT_ID):
    from ouroboros.consciousness import BackgroundConsciousness
    import queue

    _chat_id = int(OWNER_CHAT_ID) if OWNER_CHAT_ID else None
    consciousness = BackgroundConsciousness(
        drive_root=DRIVE_ROOT,
        repo_dir=pathlib.Path(REPO_DIR),
        event_queue=queue.Queue(),
        owner_chat_id_fn=lambda: _chat_id,
    )
    try:
        consciousness.start()
    except Exception as e:
        log.warning("Consciousness failed to start: %s", e)
    return consciousness


# ----------------------------
# Main entry point
# ----------------------------
def main():
    """Main entry point — all side effects happen here."""
    load_dotenv()

    # Execute top-level initialization steps that must happen exactly once
    install_launcher_deps()
    install_apply_patch()

    # Secrets and configuration
    OPENROUTER_API_KEY = get_secret("OPENROUTER_API_KEY", required=True)
    TELEGRAM_BOT_TOKEN = get_secret("TELEGRAM_BOT_TOKEN", required=True)
    TOTAL_BUDGET_DEFAULT = get_secret("TOTAL_BUDGET", required=True)
    GITHUB_TOKEN = get_secret("GITHUB_TOKEN", required=True)

    # Robust TOTAL_BUDGET parsing
    try:
        import re

        _raw_budget = str(TOTAL_BUDGET_DEFAULT or "")
        _clean_budget = re.sub(r"[^0-9.\-]", "", _raw_budget)
        TOTAL_BUDGET_LIMIT = float(_clean_budget) if _clean_budget else 0.0
        if _raw_budget.strip() != _clean_budget:
            log.warning(f"TOTAL_BUDGET cleaned: {_raw_budget!r} → {TOTAL_BUDGET_LIMIT}")
    except Exception as e:
        log.warning(f"Failed to parse TOTAL_BUDGET ({TOTAL_BUDGET_DEFAULT!r}): {e}")
        TOTAL_BUDGET_LIMIT = 0.0

    OPENAI_API_KEY = get_secret("OPENAI_API_KEY", default="")
    ANTHROPIC_API_KEY = get_secret("ANTHROPIC_API_KEY", default="")
    GITHUB_USER = get_cfg("GITHUB_USER", default=None, allow_legacy_secret=True)
    GITHUB_REPO = get_cfg("GITHUB_REPO", default=None, allow_legacy_secret=True)
    assert GITHUB_USER and str(GITHUB_USER).strip(), "GITHUB_USER not set. Add it to your config cell (see README)."
    assert GITHUB_REPO and str(GITHUB_REPO).strip(), "GITHUB_REPO not set. Add it to your config cell (see README)."
    MAX_WORKERS = int(get_cfg("OUROBOROS_MAX_WORKERS", default="5", allow_legacy_secret=True) or "5")
    MODEL_MAIN = get_cfg("OUROBOROS_MODEL", default="openrouter/free", allow_legacy_secret=True)
    MODEL_CODE = get_cfg("OUROBOROS_MODEL_CODE", default="openrouter/free", allow_legacy_secret=True)
    MODEL_LIGHT = get_cfg("OUROBOROS_MODEL_LIGHT", default="openrouter/free", allow_legacy_secret=True)

    BUDGET_REPORT_EVERY_MESSAGES = 10
    SOFT_TIMEOUT_SEC = max(
        60, int(get_cfg("OUROBOROS_SOFT_TIMEOUT_SEC", default="600", allow_legacy_secret=True) or "600")
    )
    HARD_TIMEOUT_SEC = max(
        120, int(get_cfg("OUROBOROS_HARD_TIMEOUT_SEC", default="1800", allow_legacy_secret=True) or "1800")
    )
    DIAG_HEARTBEAT_SEC = _parse_int_cfg(
        get_cfg("OUROBOROS_DIAG_HEARTBEAT_SEC", default="30", allow_legacy_secret=True),
        default=30,
        minimum=0,
    )
    DIAG_SLOW_CYCLE_SEC = _parse_int_cfg(
        get_cfg("OUROBOROS_DIAG_SLOW_CYCLE_SEC", default="20", allow_legacy_secret=True),
        default=20,
        minimum=0,
    )

    os.environ["OPENROUTER_API_KEY"] = str(OPENROUTER_API_KEY)
    os.environ["OPENAI_API_KEY"] = str(OPENAI_API_KEY or "")
    os.environ["ANTHROPIC_API_KEY"] = str(ANTHROPIC_API_KEY or "")
    os.environ["GITHUB_USER"] = str(GITHUB_USER)
    os.environ["GITHUB_REPO"] = str(GITHUB_REPO)
    os.environ["OUROBOROS_MODEL"] = str(MODEL_MAIN or "openrouter/free")
    os.environ["OUROBOROS_MODEL_CODE"] = str(MODEL_CODE or "openrouter/free")
    if MODEL_LIGHT:
        os.environ["OUROBOROS_MODEL_LIGHT"] = str(MODEL_LIGHT)
    os.environ["OUROBOROS_DIAG_HEARTBEAT_SEC"] = str(DIAG_HEARTBEAT_SEC)
    os.environ["OUROBOROS_DIAG_SLOW_CYCLE_SEC"] = str(DIAG_SLOW_CYCLE_SEC)
    os.environ["TELEGRAM_BOT_TOKEN"] = str(TELEGRAM_BOT_TOKEN)

    if str(ANTHROPIC_API_KEY or "").strip():
        ensure_claude_code_cli()

    # Setup storage paths
    DRIVE_ROOT, REPO_DIR = _setup_paths()

    # Git constants
    BRANCH_DEV, BRANCH_STABLE, REMOTE_URL = _setup_git_constants(GITHUB_USER, GITHUB_REPO, GITHUB_TOKEN)

    # Initialize supervisor modules
    TG = TelegramClient(str(TELEGRAM_BOT_TOKEN))
    _init_supervisor(DRIVE_ROOT, TOTAL_BUDGET_LIMIT, BUDGET_REPORT_EVERY_MESSAGES, TG)

    # Auto-register owner from environment variable if not already set
    OWNER_CHAT_ID_ENV = os.environ.get("TELEGRAM_OWNER_CHAT_ID")
    if OWNER_CHAT_ID_ENV:
        try:
            parsed_owner = int(OWNER_CHAT_ID_ENV)
            st = load_state()
            if not st.get("owner_id"):
                st["owner_id"] = parsed_owner
                st["owner_chat_id"] = parsed_owner
                save_state(st)
                log.info("Auto-registered owner from env: %s", parsed_owner)
        except Exception:
            pass

    # Initialize background consciousness
    st = load_state()
    OWNER_CHAT_ID = st.get("owner_chat_id")
    consciousness = _init_consciousness(REPO_DIR, DRIVE_ROOT, TG, OWNER_CHAT_ID)

    # Initialize workers and start the bot
    supervisor.workers.init(
        repo_dir=REPO_DIR,
        drive_root=DRIVE_ROOT,
        max_workers=MAX_WORKERS,
        soft_timeout=SOFT_TIMEOUT_SEC,
        hard_timeout=HARD_TIMEOUT_SEC,
        total_budget_limit=TOTAL_BUDGET_LIMIT,
        branch_dev=BRANCH_DEV,
        branch_stable=BRANCH_STABLE,
    )
    supervisor.workers.spawn_workers(MAX_WORKERS)
    supervisor.workers.auto_resume_after_restart()

    log.info("Workers initialized. Starting main loop.")

    # Main loop: poll Telegram, enqueue tasks, process events
    from supervisor.events import dispatch_event
    from supervisor.queue import enqueue_task

    event_q = supervisor.workers.get_event_q()
    update_offset = 0
    _last_health_check = time.time()

    def _shutdown(signum, frame):
        log.info("Shutdown signal received")
        supervisor.workers.kill_workers()
        sys.exit(0)

    import signal

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    while True:
        try:
            # Poll Telegram for new messages (long-poll with 5s timeout)
            updates = TG.get_updates(offset=update_offset, timeout=5)
            for upd in updates:
                update_offset = upd["update_id"] + 1
                msg = upd.get("message") or upd.get("edited_message") or {}
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "")
                if chat_id and text:
                    task = {
                        "id": uuid.uuid4().hex[:8],
                        "type": "task",
                        "chat_id": int(chat_id),
                        "text": text,
                    }
                    enqueue_task(task)
                    supervisor.workers.assign_tasks()
                    log.info("Enqueued task from chat %s: %s", chat_id, text[:50])
        except Exception as e:
            log.debug("Telegram poll error: %s", e)
            time.sleep(1)

        # Process all pending events from workers
        while True:
            try:
                evt = event_q.get_nowait()
            except Exception:
                break
            # Build a minimal ctx for dispatch_event
            from supervisor.telegram import send_with_budget as _swb, log_chat as _lc

            _ctx = type(
                "ctx",
                (),
                {
                    "DRIVE_ROOT": DRIVE_ROOT,
                    "append_jsonl": append_jsonl,
                    "update_budget_from_usage": lambda u: None,
                    "load_state": load_state,
                    "save_state": save_state,
                    "send_with_budget": _swb,
                    "log_chat": _lc,
                    "TG": TG,
                    "get_event_q": lambda: event_q,
                    "consciousness": consciousness,
                },
            )()
            dispatch_event(evt, _ctx)

        # Periodic health check (every 5 min)
        if time.time() - _last_health_check > 300:
            supervisor.workers.ensure_workers_healthy()
            _last_health_check = time.time()


if __name__ == "__main__":
    main()
