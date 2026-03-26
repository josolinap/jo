"""
Ouroboros agent core — thin orchestrator.

Delegates to: loop.py (LLM tool loop), tools/ (tool schemas/execution),
llm.py (LLM calls), memory.py (scratchpad/identity),
context.py (context building), review.py (code collection/metrics).
"""

from __future__ import annotations

import datetime
import json
import logging
import os
import pathlib
import queue
import subprocess
import threading
import time
import traceback
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

from ouroboros.utils import (
    utc_now_iso,
    read_text,
    append_jsonl,
    safe_relpath,
    truncate_for_log,
    get_git_info,
    sanitize_task_for_event,
)
from ouroboros.llm import LLMClient
from ouroboros.tools import ToolRegistry
from ouroboros.tools.registry import ToolContext
from ouroboros.memory import Memory
from ouroboros.context import build_llm_messages
from ouroboros.loop import run_llm_loop
from ouroboros.pipeline import get_pipeline, PipelineContext
from ouroboros.synthesis import synthesize_task
from ouroboros.eval import evaluate_task


# ---------------------------------------------------------------------------
# Module-level guard for one-time worker boot logging
# ---------------------------------------------------------------------------
_worker_boot_logged = False
_worker_boot_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Environment + Paths
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Env:
    repo_dir: pathlib.Path
    drive_root: pathlib.Path
    branch_dev: str = "dev"

    def repo_path(self, rel: str) -> pathlib.Path:
        return (self.repo_dir / safe_relpath(rel)).resolve()

    def drive_path(self, rel: str) -> pathlib.Path:
        return (self.drive_root / safe_relpath(rel)).resolve()


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------


class OuroborosAgent:
    """One agent instance per worker process. Mostly stateless; long-term state lives on Drive."""

    def __init__(self, env: Env, event_queue: Any = None):
        self.env = env
        self._pending_events: List[Dict[str, Any]] = []
        self._event_queue: Any = event_queue
        self._current_chat_id: Optional[int] = None
        self._current_task_type: Optional[str] = None

        # Message injection: owner can send messages while agent is busy
        self._incoming_messages: queue.Queue = queue.Queue()
        self._busy = False
        self._last_progress_ts: float = 0.0
        self._task_started_ts: float = 0.0

        # SSOT modules
        self.llm = LLMClient()
        self.tools = ToolRegistry(repo_dir=env.repo_dir, drive_root=env.drive_root)
        self.memory = Memory(drive_root=env.drive_root, repo_dir=env.repo_dir)

        # Initialize multi-agent coordinator
        from ouroboros.tools.agent_coordinator import initialize as init_coordinator

        init_coordinator()

        self._log_worker_boot_once()
        self._start_hot_reload_manager()

    def inject_message(self, text: str) -> None:
        """Thread-safe: inject owner message into the active conversation."""
        self._incoming_messages.put(text)

    def _start_hot_reload_manager(self, check_interval: int = 60) -> None:
        """Start smart reload detection - hybrid hot reload + vault notification.

        This replaces the simple SHA watchdog with intelligent change detection:
        - If vault/docs change: notify model, no restart, preserve context
        - If code changes: exit for clean restart as before

        The expected SHA is read from ``OUROBOROS_EXPECTED_SHA`` env var.
        """
        from ouroboros.hot_reload import HotReloadManager

        initial_sha = os.environ.get("OUROBOROS_EXPECTED_SHA", "").strip()
        if not initial_sha:
            log.debug("Hot reload manager: OUROBOROS_EXPECTED_SHA not set — inactive.")
            return

        def on_vault_change(notification: str) -> None:
            """Called when vault/docs change - notify the model."""
            try:
                self._incoming_messages.put(f"[System] {notification}")
                log.info("Vault change notification sent to model")
            except Exception as e:
                log.debug(f"Failed to notify model of vault change: {e}")

        self._hot_reload = HotReloadManager(
            repo_dir=self.env.repo_dir,
            drive_root=self.env.drive_root,
            initial_sha=initial_sha,
            check_interval=check_interval,
            on_vault_change=on_vault_change,
        )
        self._hot_reload.start()
        log.debug("Hot reload manager started (interval=%ds, initial_sha=%s)", check_interval, initial_sha[:8])

    def _log_worker_boot_once(self) -> None:
        global _worker_boot_logged
        try:
            with _worker_boot_lock:
                if _worker_boot_logged:
                    return
                _worker_boot_logged = True
            git_branch, git_sha = get_git_info(self.env.repo_dir)
            append_jsonl(
                self.env.drive_path("logs") / "events.jsonl",
                {
                    "ts": utc_now_iso(),
                    "type": "worker_boot",
                    "pid": os.getpid(),
                    "git_branch": git_branch,
                    "git_sha": git_sha,
                },
            )
            self._verify_restart(git_sha)
            self._verify_system_state(git_sha)
        except Exception:
            log.warning("Worker boot logging failed", exc_info=True)
            return

    def _verify_restart(self, git_sha: str) -> None:
        """Best-effort restart verification."""
        try:
            pending_path = self.env.drive_path("state") / "pending_restart_verify.json"
            claim_path = pending_path.with_name(f"pending_restart_verify.claimed.{os.getpid()}.json")
            try:
                os.rename(str(pending_path), str(claim_path))
            except (FileNotFoundError, Exception):
                return
            try:
                claim_data = json.loads(read_text(claim_path))
                expected_sha = str(claim_data.get("expected_sha", "")).strip()
                ok = bool(expected_sha and expected_sha == git_sha)
                append_jsonl(
                    self.env.drive_path("logs") / "events.jsonl",
                    {
                        "ts": utc_now_iso(),
                        "type": "restart_verify",
                        "pid": os.getpid(),
                        "ok": ok,
                        "expected_sha": expected_sha,
                        "observed_sha": git_sha,
                    },
                )
            except Exception:
                log.debug("Failed to log restart verify event", exc_info=True)
                pass
            try:
                claim_path.unlink()
            except Exception:
                log.debug("Failed to delete restart verify claim file", exc_info=True)
                pass
        except Exception:
            log.debug("Restart verification failed", exc_info=True)
            pass

    def _check_uncommitted_changes(self) -> Tuple[dict, int]:
        """Check for uncommitted changes and attempt auto-rescue commit & push."""
        import re
        import subprocess

        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=str(self.env.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
                check=True,
            )
            dirty_files = [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
            # Filter out noise: tilde files, backup files, temp files
            dirty_files = [
                f for f in dirty_files if not (f.startswith("?? ~") or f.startswith("?? .") or "~" in f or ".tmp" in f)
            ]
            if dirty_files:
                # Auto-rescue: commit and push
                auto_committed = False
                try:
                    # Only stage tracked files (not secrets/notebooks)
                    subprocess.run(["git", "add", "-u"], cwd=str(self.env.repo_dir), timeout=10, check=True)
                    subprocess.run(
                        ["git", "commit", "-m", "auto-rescue: uncommitted changes detected on startup"],
                        cwd=str(self.env.repo_dir),
                        timeout=30,
                        check=True,
                    )
                    # Validate branch name
                    if not re.match(r"^[a-zA-Z0-9_/-]+$", self.env.branch_dev):
                        raise ValueError(f"Invalid branch name: {self.env.branch_dev}")
                    # Pull with rebase before push
                    subprocess.run(
                        ["git", "pull", "--rebase", "origin", self.env.branch_dev],
                        cwd=str(self.env.repo_dir),
                        timeout=60,
                        check=True,
                    )
                    # Push
                    try:
                        subprocess.run(
                            ["git", "push", "origin", self.env.branch_dev],
                            cwd=str(self.env.repo_dir),
                            timeout=60,
                            check=True,
                        )
                        auto_committed = True
                        log.warning(f"Auto-rescued {len(dirty_files)} uncommitted files on startup")
                    except subprocess.CalledProcessError:
                        # If push fails, undo the commit
                        subprocess.run(["git", "reset", "HEAD~1"], cwd=str(self.env.repo_dir), timeout=10, check=True)
                        raise
                except Exception as e:
                    log.warning(f"Failed to auto-rescue uncommitted changes: {e}", exc_info=True)
                return {
                    "status": "warning",
                    "files": dirty_files[:20],
                    "auto_committed": auto_committed,
                }, 1
            else:
                return {"status": "ok"}, 0
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0

    def _check_version_sync(self) -> Tuple[dict, int]:
        """Check VERSION file sync with git tags and pyproject.toml."""
        import subprocess
        import re

        try:
            version_file = read_text(self.env.repo_path("VERSION")).strip()
            issue_count = 0
            result_data = {"version_file": version_file}

            # Check pyproject.toml version
            pyproject_path = self.env.repo_path("pyproject.toml")
            pyproject_content = read_text(pyproject_path)
            match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', pyproject_content, re.MULTILINE)
            if match:
                pyproject_version = match.group(1)
                result_data["pyproject_version"] = pyproject_version
                if version_file != pyproject_version:
                    result_data["status"] = "warning"
                    issue_count += 1

            # Check README.md version (Bible P7: VERSION == README version)
            try:
                readme_content = read_text(self.env.repo_path("README.md"))
                readme_match = re.search(r"\*\*Version:\*\*\s*(\d+\.\d+\.\d+)", readme_content)
                if readme_match:
                    readme_version = readme_match.group(1)
                    result_data["readme_version"] = readme_version
                    if version_file != readme_version:
                        result_data["status"] = "warning"
                        issue_count += 1
            except Exception:
                log.debug("Failed to check README.md version", exc_info=True)

            # Check git tags
            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(self.env.repo_dir),
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                result_data["status"] = "warning"
                result_data["message"] = "no_tags"
                return result_data, issue_count
            else:
                latest_tag = result.stdout.strip().lstrip("v")
                result_data["latest_tag"] = latest_tag
                if version_file != latest_tag:
                    result_data["status"] = "warning"
                    issue_count += 1

            if issue_count == 0:
                result_data["status"] = "ok"

            return result_data, issue_count
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0

    def _check_budget(self) -> Tuple[dict, int]:
        """Check budget remaining with warning thresholds."""
        try:
            state_path = self.env.drive_path("state") / "state.json"
            state_data = json.loads(read_text(state_path))
            total_budget_str = os.environ.get("TOTAL_BUDGET", "")

            # Handle unset or zero budget gracefully
            if not total_budget_str or float(total_budget_str) == 0:
                return {"status": "unconfigured"}, 0
            else:
                total_budget = float(total_budget_str)
                spent = float(state_data.get("spent_usd", 0))
                remaining = max(0, total_budget - spent)

                if remaining < 10:
                    status = "emergency"
                    issues = 1
                elif remaining < 50:
                    status = "critical"
                    issues = 1
                elif remaining < 100:
                    status = "warning"
                    issues = 0
                else:
                    status = "ok"
                    issues = 0

                return {
                    "status": status,
                    "remaining_usd": round(remaining, 2),
                    "total_usd": total_budget,
                    "spent_usd": round(spent, 2),
                }, issues
        except Exception as e:
            return {"status": "error", "error": str(e)}, 0

    def _verify_system_state(self, git_sha: str) -> None:
        """Bible Principle 1: verify system state on every startup.

        Checks:
        - Uncommitted changes (auto-rescue commit & push)
        - VERSION file sync with git tags
        - Budget remaining (warning thresholds)
        """
        checks = {}
        issues = 0
        drive_logs = self.env.drive_path("logs")

        # 1. Uncommitted changes
        checks["uncommitted_changes"], issue_count = self._check_uncommitted_changes()
        issues += issue_count

        # 2. VERSION vs git tag
        checks["version_sync"], issue_count = self._check_version_sync()
        issues += issue_count

        # 3. Budget check
        checks["budget"], issue_count = self._check_budget()
        issues += issue_count

        # Log verification result
        event = {
            "ts": utc_now_iso(),
            "type": "startup_verification",
            "checks": checks,
            "issues_count": issues,
            "git_sha": git_sha,
        }
        append_jsonl(drive_logs / "events.jsonl", event)

        if issues > 0:
            log.warning(f"Startup verification found {issues} issue(s): {checks}")

    # =====================================================================
    # Main entry point
    # =====================================================================

    def _prepare_task_context(self, task: Dict[str, Any]) -> Tuple[ToolContext, List[Dict[str, Any]], Dict[str, Any]]:
        """Set up ToolContext, build messages, return (ctx, messages, cap_info)."""
        drive_logs = self.env.drive_path("logs")
        sanitized_task = sanitize_task_for_event(task, drive_logs)
        append_jsonl(
            drive_logs / "events.jsonl", {"ts": utc_now_iso(), "type": "task_received", "task": sanitized_task}
        )

        # Set tool context for this task
        ctx = ToolContext(
            repo_dir=self.env.repo_dir,
            drive_root=self.env.drive_root,
            branch_dev=self.env.branch_dev,
            pending_events=self._pending_events,
            current_chat_id=self._current_chat_id,
            current_task_type=self._current_task_type,
            emit_progress_fn=self._emit_progress,
            task_depth=int(task.get("depth", 0)),
            is_direct_chat=bool(task.get("_is_direct_chat")),
        )
        self.tools.set_context(ctx)

        # Typing indicator via event queue (no direct Telegram API)
        self._emit_typing_start()

        # --- Build context (delegated to context.py) ---
        messages, cap_info = build_llm_messages(
            env=self.env,
            memory=self.memory,
            task=task,
            review_context_builder=self._build_review_context,
        )

        if cap_info.get("trimmed_sections"):
            try:
                append_jsonl(
                    drive_logs / "events.jsonl",
                    {
                        "ts": utc_now_iso(),
                        "type": "context_soft_cap_trim",
                        "task_id": task.get("id"),
                        **cap_info,
                    },
                )
            except Exception:
                log.warning("Failed to log context soft cap trim event", exc_info=True)
                pass

        # Read budget remaining for cost guard
        budget_remaining = None
        try:
            state_path = self.env.drive_path("state") / "state.json"
            state_data = json.loads(read_text(state_path))
            total_budget = float(os.environ.get("TOTAL_BUDGET", "1"))
            spent = float(state_data.get("spent_usd", 0))
            if total_budget > 0:
                budget_remaining = max(0, total_budget - spent)
        except Exception:
            log.debug("Failed to read budget state", exc_info=True)

        cap_info["budget_remaining"] = budget_remaining
        return ctx, messages, cap_info

    def handle_task(self, task: Dict[str, Any]) -> List[Dict[str, Any]]:
        self._busy = True
        start_time = time.time()
        self._task_started_ts = start_time
        self._last_progress_ts = start_time
        self._pending_events = []
        self._current_chat_id = int(task.get("chat_id") or 0) or None
        self._current_task_type = str(task.get("type") or "")

        drive_logs = self.env.drive_path("logs")
        heartbeat_stop = self._start_task_heartbeat_loop(str(task.get("id") or ""))

        try:
            # --- Prepare task context ---
            ctx, messages, cap_info = self._prepare_task_context(task)
            budget_remaining = cap_info.get("budget_remaining")

            # --- Pipeline: DIAGNOSE and PLAN phases (only if enabled) ---
            pipeline = get_pipeline()
            pipeline_ctx = None
            task_text = task.get("text", "") or str(task.get("content", ""))
            if pipeline.is_enabled():
                pipeline_ctx = PipelineContext(task=task_text)
                pipeline.run_diagnose(pipeline_ctx)
                pipeline.run_plan(pipeline_ctx)

            # --- Semantic tool routing (from RuVector SONA) ---
            try:
                from ouroboros.tool_router import classify_task
                from ouroboros.temporal_learning import get_learner

                routed_task_type = classify_task(task_text)
                learner = get_learner(repo_dir=self.env.repo_dir)
                if learner:
                    available = [s["function"]["name"] for s in self.tools.schemas()]
                    suggested = learner.suggest_tools(routed_task_type, available, top_n=5)
                    if suggested:
                        log.info("[Router] Task type: %s, suggested tools: %s", routed_task_type, suggested[:3])
            except Exception:
                log.debug("Tool routing failed", exc_info=True)

            # --- LLM loop (delegated to loop.py) ---
            usage: Dict[str, Any] = {}
            llm_trace: Dict[str, Any] = {"assistant_notes": [], "tool_calls": []}

            # Set initial reasoning effort based on task type
            task_type_str = str(task.get("type") or "").lower()
            if task_type_str in ("evolution", "review"):
                initial_effort = "high"
            else:
                initial_effort = "medium"

            try:
                text, usage, llm_trace = run_llm_loop(
                    messages=messages,
                    tools=self.tools,
                    llm=self.llm,
                    drive_logs=drive_logs,
                    emit_progress=self._emit_progress,
                    incoming_messages=self._incoming_messages,
                    task_type=task_type_str,
                    task_id=str(task.get("id") or ""),
                    budget_remaining_usd=budget_remaining,
                    event_queue=self._event_queue,
                    initial_effort=initial_effort,
                    drive_root=self.env.drive_root,
                )
            except Exception as e:
                tb = traceback.format_exc()
                append_jsonl(
                    drive_logs / "events.jsonl",
                    {
                        "ts": utc_now_iso(),
                        "type": "task_error",
                        "task_id": task.get("id"),
                        "error": repr(e),
                        "traceback": truncate_for_log(tb, 2000),
                    },
                )
                text = f"⚠️ Error during processing: {type(e).__name__}: {e}"

            # Empty response guard
            if not isinstance(text, str) or not text.strip():
                text = "⚠️ Model returned an empty response. Try rephrasing your request."

            # --- Run synthesis and eval on final output ---
            # Get changed files from git
            changed_files = []
            try:
                branch, status = get_git_info(self.env.repo_dir)
                for line in status.split("\n"):
                    if line.startswith("M ") or line.startswith("A "):
                        changed_files.append(line[2:].strip())
            except Exception:
                log.debug("Failed to parse git diff for changed files", exc_info=True)

            synth_report = synthesize_task(task_text, text, changed_files, self.env.repo_dir)
            eval_report = evaluate_task(task_text, text, changed_files, self.env.repo_dir)

            if synth_report or eval_report:
                parts = [text]
                if eval_report:
                    parts.append(eval_report)
                if synth_report:
                    parts.append(synth_report)
                text = "\n\n".join(parts)

            # Emit events for supervisor
            self._emit_task_results(task, text, usage, llm_trace, start_time, drive_logs)

            # Auto-update scratchpad for evolution/review tasks
            if task.get("type") in ("evolution", "review"):
                self._auto_update_scratchpad_after_task(task, text, llm_trace)

            # Record episodic memory and temporal learning outcome
            try:
                from ouroboros.episodic_memory import get_episodic_memory
                from ouroboros.temporal_learning import get_learner

                success = "error" not in text.lower()[:100] and "⚠" not in text[:20]
                if eval_report:
                    # If eval found quality issues, mark as partial success
                    success = success and "quality issue" not in eval_report.lower()
                tools_used = []
                for tc in llm_trace.get("tool_calls", []):
                    if isinstance(tc, dict):
                        name = tc.get("name", tc.get("function", {}).get("name", ""))
                        if name:
                            tools_used.append(name)

                # Episodic memory
                em = get_episodic_memory(repo_dir=self.env.repo_dir)
                em.record(
                    decision=task_text[:200],
                    action=f"Used {len(tools_used)} tools in {len(llm_trace.get('assistant_notes', []))} rounds",
                    outcome=text[:200],
                    context=task_type_str or "general",
                    success=success,
                    tools_used=tools_used,
                )

                # Temporal learning outcome
                learner = get_learner(repo_dir=self.env.repo_dir)
                if learner:
                    learner.record_sequence_outcome(
                        success=success,
                        task_type=task_type_str or "general",
                        round_count=len(llm_trace.get("assistant_notes", [])),
                    )

                    # Evolve confirmed patterns into vault skills
                    try:
                        from ouroboros.instinct_evolver import get_evolver

                        evolver = get_evolver(repo_dir=self.env.repo_dir)
                        evolved = evolver.evolve_from_learner(learner, self.env.repo_dir)
                        if evolved:
                            log.info("[Instinct] Evolved %d patterns: %s", len(evolved), evolved)
                    except Exception:
                        log.debug("Instinct evolution failed", exc_info=True)
            except Exception:
                log.debug("Post-task learning block failed", exc_info=True)

            # Checkpoint verification for evolution tasks
            if task.get("type") in ("evolution", "review") and changed_files:
                try:
                    from ouroboros.checkpoint import run_checkpoint_gate, checkpoint_report

                    gate = run_checkpoint_gate(self.env.repo_dir, changed_files)
                    if not gate.passed:
                        report = checkpoint_report(gate)
                        log.warning("[Checkpoint] Evolution gate FAILED: %s", report[:200])
                        # Append checkpoint report to response
                        text = text + "\n\n" + report
                except Exception:
                    log.debug("Checkpoint verification failed", exc_info=True)

            # Delta evaluation for evolution tasks
            if task.get("type") in ("evolution", "review"):
                try:
                    from ouroboros.delta_eval import DeltaEvaluator

                    evaluator = DeltaEvaluator(
                        history_path=self.env.drive_path("delta_history.json") if self.env.drive_root else None
                    )

                    # Get actual line counts from git diff
                    lines_added = 0
                    lines_removed = 0
                    try:
                        import subprocess as _sp

                        diff_result = _sp.run(
                            ["git", "diff", "--stat", "HEAD~1"],
                            cwd=str(self.env.repo_dir),
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if diff_result.returncode == 0:
                            for dline in diff_result.stdout.split("\n"):
                                if "insertion" in dline:
                                    parts = dline.strip().split(",")
                                    for p in parts:
                                        p = p.strip()
                                        if "insertion" in p:
                                            lines_added = int("".join(c for c in p if c.isdigit()) or "0")
                                        if "deletion" in p:
                                            lines_removed = int("".join(c for c in p if c.isdigit()) or "0")
                    except Exception:
                        log.debug("Failed to parse git diff stats", exc_info=True)

                    # Run actual tests to get real pass/fail count
                    tests_passing = 0
                    tests_failing = 0
                    try:
                        import subprocess as _sp2

                        test_result = _sp2.run(
                            ["python", "-m", "pytest", "tests/", "-q", "--tb=no"],
                            cwd=str(self.env.repo_dir),
                            capture_output=True,
                            text=True,
                            timeout=60,
                        )
                        output = test_result.stdout + test_result.stderr
                        for tline in output.split("\n"):
                            if " passed" in tline:
                                tests_passing = int("".join(c for c in tline.split(" passed")[0] if c.isdigit()) or "0")
                            if " failed" in tline:
                                tests_failing = int("".join(c for c in tline.split(" failed")[0] if c.isdigit()) or "0")
                    except Exception:
                        log.debug("Failed to run tests for delta eval", exc_info=True)

                    result = evaluator.evaluate_change(
                        lines_added=lines_added,
                        lines_removed=lines_removed,
                        tests_passing=tests_passing,
                        tests_failing=tests_failing,
                        tools_added=0,
                        tools_removed=0,
                        context=task_text[:100],
                    )
                    if not result.is_improvement:
                        log.warning("[Delta] Evolution quality: %.4f (not improving)", result.total_delta)
                except Exception:
                    log.debug("Delta evaluation failed", exc_info=True)

            return list(self._pending_events)

        finally:
            self._busy = False
            # Clean up browser if it was used during this task
            try:
                from ouroboros.tools.browser import cleanup_browser

                cleanup_browser(self.tools._ctx)
            except Exception:
                log.debug("Failed to cleanup browser", exc_info=True)
                pass
            while not self._incoming_messages.empty():
                try:
                    self._incoming_messages.get_nowait()
                except queue.Empty:
                    break
            if heartbeat_stop is not None:
                heartbeat_stop.set()
            self._current_task_type = None

    # =====================================================================
    # Task result emission
    # =====================================================================

    def _emit_task_results(
        self,
        task: Dict[str, Any],
        text: str,
        usage: Dict[str, Any],
        llm_trace: Dict[str, Any],
        start_time: float,
        drive_logs: pathlib.Path,
    ) -> None:
        """Emit all end-of-task events to supervisor."""
        # NOTE: per-round llm_usage events are already emitted in loop.py
        # (_emit_llm_usage_event). Do NOT emit an aggregate llm_usage here —
        # that would double-count in update_budget_from_usage.
        # Cost/token summaries are carried by task_metrics and task_done events.

        self._pending_events.append(
            {
                "type": "send_message",
                "chat_id": task["chat_id"],
                "text": text or "\u200b",
                "log_text": text or "",
                "format": "markdown",
                "task_id": task.get("id"),
                "ts": utc_now_iso(),
            }
        )

        duration_sec = round(time.time() - start_time, 3)
        n_tool_calls = len(llm_trace.get("tool_calls", []))
        n_tool_errors = sum(1 for tc in llm_trace.get("tool_calls", []) if isinstance(tc, dict) and tc.get("is_error"))
        try:
            append_jsonl(
                drive_logs / "events.jsonl",
                {
                    "ts": utc_now_iso(),
                    "type": "task_eval",
                    "ok": True,
                    "task_id": task.get("id"),
                    "task_type": task.get("type"),
                    "duration_sec": duration_sec,
                    "tool_calls": n_tool_calls,
                    "tool_errors": n_tool_errors,
                    "response_len": len(text),
                },
            )
        except Exception:
            log.warning("Failed to log task eval event", exc_info=True)
            pass

        self._pending_events.append(
            {
                "type": "task_metrics",
                "task_id": task.get("id"),
                "task_type": task.get("type"),
                "duration_sec": duration_sec,
                "tool_calls": n_tool_calls,
                "tool_errors": n_tool_errors,
                "cost_usd": round(float(usage.get("cost") or 0), 6),
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_rounds": int(usage.get("rounds") or 0),
                "ts": utc_now_iso(),
            }
        )

        self._pending_events.append(
            {
                "type": "task_done",
                "task_id": task.get("id"),
                "task_type": task.get("type"),
                "cost_usd": round(float(usage.get("cost") or 0), 6),
                "total_rounds": int(usage.get("rounds") or 0),
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "ts": utc_now_iso(),
            }
        )
        append_jsonl(
            drive_logs / "events.jsonl",
            {
                "ts": utc_now_iso(),
                "type": "task_done",
                "task_id": task.get("id"),
                "task_type": task.get("type"),
                "cost_usd": round(float(usage.get("cost") or 0), 6),
                "total_rounds": int(usage.get("rounds") or 0),
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
            },
        )

        # Store task result for parent task retrieval
        try:
            results_dir = pathlib.Path(self.env.drive_root) / "task_results"
            results_dir.mkdir(parents=True, exist_ok=True)
            result_data = {
                "task_id": task.get("id"),
                "parent_task_id": task.get("parent_task_id"),
                "status": "completed",
                "result": text[:4000] if text else "",  # Truncate to avoid huge files
                "cost_usd": round(float(usage.get("cost") or 0), 6),
                "total_rounds": int(usage.get("rounds") or 0),
                "ts": utc_now_iso(),
            }
            result_file = results_dir / f"{task.get('id')}.json"
            tmp_file = results_dir / f"{task.get('id')}.json.tmp"
            tmp_file.write_text(json.dumps(result_data, ensure_ascii=False, indent=2))
            os.rename(tmp_file, result_file)
        except Exception as e:
            log.warning("Failed to store task result: %s", e)

    # =====================================================================
    # Auto-update scratchpad after evolution/review tasks
    # =====================================================================

    def _auto_update_scratchpad_after_task(
        self,
        task: Dict[str, Any],
        response_text: str,
        llm_trace: Dict[str, Any],
    ) -> None:
        """Auto-log evolution/review results with success tracking and archive/forget."""
        try:
            from ouroboros.memory import Memory

            task_type = task.get("type", "unknown")
            task_id = task.get("id", "")

            # Count commits made during this task
            commit_tools = {"repo_write_commit", "repo_commit_push", "commit"}
            commit_count = sum(
                1
                for tc in llm_trace.get("tool_calls", [])
                if isinstance(tc, dict) and tc.get("tool", "").lower() in commit_tools
            )

            # Check if tests passed (look for test-related tool calls)
            test_tools = {"shell_run", "bash"}
            test_mentions = [
                tc
                for tc in llm_trace.get("tool_calls", [])
                if isinstance(tc, dict) and "test" in tc.get("tool", "").lower()
            ]

            cost = sum(float(tc.get("cost", 0)) for tc in llm_trace.get("tool_calls", []) if isinstance(tc, dict))

            # Determine success: made commits AND has meaningful response
            success = commit_count > 0 and len(response_text.strip()) > 100

            # Get current cycle
            try:
                st = self._load_state_fn()
                cycle = int(st.get("evolution_cycle", 0))
            except Exception:
                cycle = 0

            timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

            # Extract summary from response (first 300 chars)
            summary = response_text[:300].replace("#", "").replace("*", "").replace("\n", " ").strip()
            if len(response_text) > 300:
                summary += "..."

            # Build history entry
            history_entry = {
                "task_id": task_id,
                "cycle": cycle,
                "timestamp": timestamp,
                "commits": commit_count,
                "success": success,
                "archived": False,
                "summary": summary,
                "cost": round(cost, 4),
            }

            # Update state with history
            self._update_evolution_history(history_entry, success)

            # Update scratchpad with human-readable entry
            mem = Memory(self.env.drive_root, self.env.repo_dir)
            current = mem.load_scratchpad()

            status_emoji = "✅" if success else "❌"
            status_text = "stable" if success else "failed"

            new_section = f"""
## {task_type.title()} #{task_id} ({cycle}) {status_emoji} [{status_text}]
- {timestamp}
- Commits: {commit_count}
- Cost: ${cost:.4f}
- Summary: {summary}
"""

            # Append to scratchpad
            updated = current + new_section
            lines = updated.splitlines()

            # Prune: keep last 50 evolution entries (~200 lines)
            if len(lines) > 200:
                lines = lines[-200:]
                updated = "\n".join(lines)

            mem.save_scratchpad(updated)
            log.info(f"Auto-updated scratchpad after {task_type} task {task_id} (success={success})")

            # Auto-archive if stable (success + no failures for 3 cycles)
            self._try_archive_stable_evolution()

        except Exception as e:
            log.warning("Failed to auto-update scratchpad: %s", e)

    def _load_state_fn(self):
        """Load state - imported lazily to avoid circular imports."""
        from supervisor.state import load_state

        return load_state()

    def _save_state_fn(self, st):
        """Save state - imported lazily."""
        from supervisor.state import save_state

        save_state(st)

    def _update_evolution_history(self, entry: Dict[str, Any], success: bool) -> None:
        """Update evolution history in state with archive/forget logic."""
        try:
            st = self._load_state_fn()
            history = st.get("evolution_history", [])

            # Add new entry at the beginning
            history.insert(0, entry)

            # Prune: keep last 30 entries
            MAX_HISTORY = 30
            if len(history) > MAX_HISTORY:
                # Move entries older than 7 days to archived (they're "forgotten" from active view)
                cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                pruned = []
                for h in history:
                    try:
                        ts = datetime.datetime.fromisoformat(h.get("timestamp", ""))
                        if ts > cutoff:
                            pruned.append(h)
                    except Exception:
                        pruned.append(h)
                history = pruned[:MAX_HISTORY]

            st["evolution_history"] = history

            # Update consecutive failures counter
            if success:
                st["evolution_consecutive_failures"] = 0
            else:
                st["evolution_consecutive_failures"] = int(st.get("evolution_consecutive_failures", 0)) + 1
                failures = st["evolution_consecutive_failures"]
                if failures >= 2:
                    log.warning(
                        f"EVOLUTION HEALTH ALERT: {failures} consecutive failures. "
                        f"Consider pausing evolution mode and reviewing recent commits."
                    )

            self._save_state_fn(st)

        except Exception as e:
            log.warning("Failed to update evolution history: %s", e)

    def _try_archive_stable_evolution(self) -> None:
        """Archive evolutions that have been stable (3+ successful, no recent failures)."""
        try:
            st = self._load_state_fn()
            history = st.get("evolution_history", [])
            consecutive_success = 0

            for entry in history:
                if entry.get("archived"):
                    continue
                if entry.get("success"):
                    consecutive_success += 1
                else:
                    break

            # Archive if 3+ consecutive successful evolutions
            if consecutive_success >= 3:
                archived_count = 0
                for entry in history:
                    if entry.get("success") and not entry.get("archived"):
                        entry["archived"] = True
                        archived_count += 1
                        if archived_count >= consecutive_success - 1:  # Keep latest
                            break

                st["evolution_history"] = history
                self._save_state_fn(st)
                log.info(f"Archived {archived_count} stable evolution entries")

        except Exception as e:
            log.warning("Failed to archive stable evolutions: %s", e)

    # =====================================================================
    # Review context builder
    # =====================================================================

    def _build_review_context(self) -> str:
        """Collect code snapshot + complexity metrics for review tasks."""
        try:
            from ouroboros.review import collect_sections, compute_complexity_metrics, format_metrics

            sections, stats = collect_sections(self.env.repo_dir, self.env.drive_root)
            metrics = compute_complexity_metrics(sections)

            parts = [
                "## Code Review Context\n",
                format_metrics(metrics),
                f"\nFiles: {stats['files']}, chars: {stats['chars']}\n",
                "\nUse repo_read to inspect specific files. Use run_shell for tests. Key files below:\n",
            ]

            total_chars = 0
            max_chars = 80_000
            files_added = 0
            for path, content in sections:
                if total_chars >= max_chars:
                    parts.append(f"\n... ({len(sections) - files_added} more files, use repo_read)")
                    break
                preview = content[:2000] if len(content) > 2000 else content
                file_block = f"\n### {path}\n```\n{preview}\n```\n"
                total_chars += len(file_block)
                parts.append(file_block)
                files_added += 1

            return "\n".join(parts)
        except Exception as e:
            return f"## Code Review Context\n\n(Failed to collect: {e})\nUse repo_read and repo_list to inspect code."

    # =====================================================================
    # Event emission helpers
    # =====================================================================

    def _emit_progress(self, text: str) -> None:
        self._last_progress_ts = time.time()

        # Suppress progress messages to owner if configured
        if os.environ.get("OUROBOROS_SUPPRESS_PROGRESS", "1") == "1":
            log.debug(f"[Progress] {text}")  # Still log internally
            return

        if self._event_queue is None or self._current_chat_id is None:
            return
        try:
            self._event_queue.put(
                {
                    "type": "send_message",
                    "chat_id": self._current_chat_id,
                    "text": f"💬 {text}",
                    "format": "markdown",
                    "is_progress": True,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit progress event", exc_info=True)
            pass

    def _emit_typing_start(self) -> None:
        if self._event_queue is None or self._current_chat_id is None:
            return
        try:
            self._event_queue.put(
                {
                    "type": "typing_start",
                    "chat_id": self._current_chat_id,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit typing start event", exc_info=True)
            pass

    def _emit_task_heartbeat(self, task_id: str, phase: str) -> None:
        if self._event_queue is None:
            return
        try:
            self._event_queue.put(
                {
                    "type": "task_heartbeat",
                    "task_id": task_id,
                    "phase": phase,
                    "ts": utc_now_iso(),
                }
            )
        except Exception:
            log.warning("Failed to emit task heartbeat event", exc_info=True)
            pass

    def _start_task_heartbeat_loop(self, task_id: str) -> Optional[threading.Event]:
        if self._event_queue is None or not task_id.strip():
            return None
        interval = 30
        stop = threading.Event()
        self._emit_task_heartbeat(task_id, "start")

        def _loop() -> None:
            while not stop.wait(interval):
                self._emit_task_heartbeat(task_id, "running")

        threading.Thread(target=_loop, daemon=True).start()
        return stop


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_agent(repo_dir: str, drive_root: str, event_queue: Any = None) -> OuroborosAgent:
    env = Env(repo_dir=pathlib.Path(repo_dir), drive_root=pathlib.Path(drive_root))
    return OuroborosAgent(env, event_queue=event_queue)
