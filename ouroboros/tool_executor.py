"""
Tool execution module for Ouroboros.

Handles single tool execution, stateful tool executors (for Playwright),
parallel execution, and timeout handling.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from ouroboros.utils import (
    utc_now_iso,
    append_jsonl,
    truncate_for_log,
    sanitize_tool_args_for_log,
    sanitize_tool_result_for_log,
)

log = logging.getLogger(__name__)


READ_ONLY_PARALLEL_TOOLS = frozenset(
    {
        # File operations (read-only)
        "repo_read",
        "repo_list",
        "repo_status",
        "repo_log",
        "drive_read",
        "drive_list",
        # Search operations
        "web_search",
        "codebase_digest",
        "anatomy_scan",
        "anatomy_lookup",
        "anatomy_search",
        # Query operations
        "query_status",
        "query_full",
        "query_health",
        # Memory operations (read-only)
        "cerebrum_search",
        "cerebrum_summary",
        "cerebrum_check",
        "buglog_search",
        "buglog_summary",
        "memory_extract",
        # State operations (read-only)
        "notepad_read",
        "notepad_stats",
        "project_memory_read",
        "persistent_tag_list",
        "state_full_context",
        "chat_history",
        # Verification operations
        "verify_build",
        "verify_tests",
        # Skill and disclosure operations
        "disclosure_visible_skills",
        "disclosure_stats",
        "capability_detect_gaps",
        "capability_stats",
        # Consciousness and growth operations
        "consciousness_status",
        "growth_report",
        "growth_stats",
        # Identity operations
        "identity_verify",
        "identity_history",
        "identity_stats",
        # Self-healing operations
        "self_healing_detect",
        "self_healing_stats",
        # Outreach operations
        "outreach_pending",
        "outreach_stats",
        # Modification operations
        "modification_history",
    }
)

STATEFUL_BROWSER_TOOLS = frozenset({"browse_page", "browser_action"})


def _truncate_tool_result(result: Any, max_chars: int = 15000) -> str:
    result_str = str(result)
    if len(result_str) <= max_chars:
        return result_str

    original_len = len(result_str)
    separator = f"\n\n... ({original_len - max_chars} chars omitted) ...\n\n"
    separator_len = len(separator)
    available = max_chars - separator_len
    if available <= 0:
        return separator[:max_chars]

    begin_size = int(available * 0.6)
    end_size = available - begin_size
    begin_part = result_str[:begin_size]
    end_part = result_str[-end_size:] if end_size > 0 else ""

    return begin_part + separator + end_part


def _summarize_tool_result(fn_name: str, result: str) -> str:
    """Code Mode: Summarize tool results instead of raw output.

    Inspired by Claude Code - returns structured summary, not raw data.
    This keeps context clean and improves model independence.
    """
    result_str = str(result)

    if fn_name in ("repo_read", "drive_read"):
        lines = result_str.split("\n")
        return f"[FILE] {len(lines)} lines, {len(result_str)} chars - First 500: {result_str[:500]}"

    if fn_name in ("repo_list", "drive_list"):
        items = result_str.strip().split("\n")
        return f"[LIST] {len(items)} items - {', '.join(items[:10])}" + (
            f" ... +{len(items) - 10} more" if len(items) > 10 else ""
        )

    if fn_name == "web_search":
        return f"[SEARCH] {result_str[:500]}..." if len(result_str) > 500 else f"[SEARCH] {result_str}"

    if fn_name == "codebase_digest":
        return f"[CODEBASE] {result_str[:300]}..." if len(result_str) > 300 else f"[CODEBASE] {result_str}"

    if fn_name == "grep_content":
        lines = [l for l in result_str.split("\n") if l.strip()]
        return f"[GREP] {len(lines)} matches - {', '.join(lines[:5])}"

    if fn_name == "vault_search":
        return f"[VAULT] {result_str[:400]}..." if len(result_str) > 400 else f"[VAULT] {result_str}"

    if fn_name == "codebase_analyze":
        try:
            data = json.loads(result_str)
            return f"[GRAPH] {data.get('nodes', 0)} nodes, {data.get('edges', 0)} edges"
        except:
            return f"[ANALYZE] {result_str[:200]}..."

    if "error" in result_str.lower() or result_str.startswith("!"):
        return f"[ERROR] {result_str[:300]}"

    if len(result_str) > 300:
        return f"[SUMMARY] {result_str[:300]}... ({len(result_str)} chars total)"

    return result_str


def _execute_single_tool(
    tools: Any,
    tc: Dict[str, Any],
    drive_logs: Path,
    task_id: str = "",
    traceability: Any = None,
) -> Dict[str, Any]:
    fn_name = tc["function"]["name"]
    tool_call_id = tc["id"]
    is_code_tool = fn_name in tools.CODE_TOOLS

    # Sandbox check - enforce read-only mode if enabled
    sandbox_readonly = getattr(tools._ctx, "sandbox_read_only", False)
    write_tools = {
        "repo_write_commit",
        "repo_commit_push",
        "code_edit",
        "vault_write",
        "vault_create",
        "drive_write",
        "delete_file",
        "move_file",
        "copy_file",
        "run_shell",
    }

    if sandbox_readonly and fn_name in write_tools:
        return {
            "tool_call_id": tool_call_id,
            "fn_name": fn_name,
            "result": f"⚠️ SANDBOX_BLOCKED: {fn_name} is write-tool but sandbox mode is read-only. Use exit_plan_mode to unlock.",
            "is_error": True,
            "args_for_log": {},
            "is_code_tool": is_code_tool,
        }

    # Auto-system sandbox check for analysis task detection
    try:
        from ouroboros.auto_system import sandbox_check

        is_analysis = getattr(tools._ctx, "is_analysis_task", False)
        ok, reason = sandbox_check(fn_name, is_analysis)
        if not ok:
            return {
                "tool_call_id": tool_call_id,
                "fn_name": fn_name,
                "result": f"⚠️ {reason}",
                "is_error": True,
                "args_for_log": {},
                "is_code_tool": is_code_tool,
            }
    except Exception:
        pass

    try:
        args = json.loads(tc["function"]["arguments"] or "{}")
    except (json.JSONDecodeError, ValueError) as e:
        result = f"⚠️ TOOL_ARG_ERROR: Could not parse arguments for '{fn_name}': {e}"
        return {
            "tool_call_id": tool_call_id,
            "fn_name": fn_name,
            "result": result,
            "is_error": True,
            "args_for_log": {},
            "is_code_tool": is_code_tool,
        }

    args_for_log = sanitize_tool_args_for_log(fn_name, args if isinstance(args, dict) else {})

    # Permission system: classify risk and check if blocked
    try:
        from ouroboros.skills.permission_system import get_permission_system

        perm = get_permission_system(repo_dir=Path(os.environ.get("REPO_DIR", ".")))
        action = perm.classify_risk(fn_name, args if isinstance(args, dict) else {})
        if action.blocked:
            return {
                "tool_call_id": tool_call_id,
                "fn_name": fn_name,
                "result": f"⚠️ PERMISSION_BLOCKED: {action.block_reason}",
                "is_error": True,
                "args_for_log": args_for_log,
                "is_code_tool": is_code_tool,
            }
        # Log risk classification for monitoring
        if action.risk_level.value == "high":
            log.warning("[Permission] High risk tool call: %s - %s", fn_name, action.explanation)
    except Exception:
        log.debug("Permission system check failed", exc_info=True)

    # Hook integration: Pre-tool hooks
    hook_mgr = None
    try:
        from ouroboros.hooks import get_hook_manager

        hook_mgr = get_hook_manager()
        allowed, modified_args, deny_msg = hook_mgr.fire_pre_tool(fn_name, args if isinstance(args, dict) else {})
        if not allowed:
            return {
                "tool_call_id": tool_call_id,
                "fn_name": fn_name,
                "result": f"⚠️ HOOK_DENIED: {deny_msg}",
                "is_error": True,
                "args_for_log": args_for_log,
                "is_code_tool": is_code_tool,
            }
        # Use modified args if hook rewrote them
        if modified_args != args:
            args = modified_args
            args_for_log = sanitize_tool_args_for_log(fn_name, args if isinstance(args, dict) else {})
    except Exception:
        log.debug("Pre-tool hook failed", exc_info=True)

    # Proof gate: check for violations before file writes
    if fn_name in ("repo_write_commit", "repo_commit_push", "code_edit", "vault_write", "vault_create"):
        try:
            from ouroboros.proof_gate import validate_files

            files_to_write = []
            if isinstance(args, dict):
                for key in ("file_path", "path", "files"):
                    val = args.get(key, "")
                    if isinstance(val, str) and val:
                        files_to_write.append(val)
                    elif isinstance(val, list):
                        files_to_write.extend(val)

            if files_to_write:
                report = validate_files(files_to_write, repo_dir=Path(os.environ.get("REPO_DIR", ".")))
                if "FAILED" in report:
                    log.warning("[ProofGate] %s blocked: %s", fn_name, report[:200])
                    return {
                        "tool_call_id": tool_call_id,
                        "fn_name": fn_name,
                        "result": f"PROOF GATE BLOCKED: {report[:500]}",
                        "is_error": True,
                        "args_for_log": args_for_log,
                        "is_code_tool": is_code_tool,
                    }
        except Exception:
            log.debug("Unexpected error", exc_info=True)

    tool_ok = True
    error_msg = None
    try:
        result = tools.execute(fn_name, args)
    except Exception as e:
        tool_ok = False
        error_msg = f"{type(e).__name__}: {e}"
        result = f"⚠️ TOOL_ERROR ({fn_name}): {error_msg}"
        append_jsonl(
            drive_logs / "events.jsonl",
            {
                "ts": utc_now_iso(),
                "type": "tool_error",
                "task_id": task_id,
                "tool": fn_name,
                "args": args_for_log,
                "error": repr(e),
            },
        )

    append_jsonl(
        drive_logs / "tools.jsonl",
        {
            "ts": utc_now_iso(),
            "tool": fn_name,
            "task_id": task_id,
            "args": args_for_log,
            "result_preview": sanitize_tool_result_for_log(truncate_for_log(result, 2000)),
        },
    )

    is_error = (not tool_ok) or str(result).startswith("⚠️")

    if traceability is not None:
        try:
            traceability.on_tool_invoked(fn_name, args_for_log, str(result)[:500], error_msg)
        except Exception as e:
            log.debug(f"Traceability hook failed: {e}")

    # Hook integration: Post-tool hooks
    if hook_mgr is not None:
        try:
            result = hook_mgr.fire_post_tool(fn_name, args_for_log, str(result))
        except Exception:
            log.debug("Post-tool hook failed", exc_info=True)

    # Hook integration: Error hooks
    if is_error and hook_mgr is not None:
        try:
            error_messages = hook_mgr.fire_on_error(fn_name, args_for_log, str(result))
            if error_messages:
                # Append hook error suggestions to result
                result = f"{result}\n\nHook suggestions:\n" + "\n".join(f"- {msg}" for msg in error_messages)
        except Exception:
            log.debug("On-error hook failed", exc_info=True)

    return {
        "tool_call_id": tool_call_id,
        "fn_name": fn_name,
        "result": result,
        "is_error": is_error,
        "args_for_log": args_for_log,
        "is_code_tool": is_code_tool,
    }


class _StatefulToolExecutor:
    """Thread-sticky executor for stateful tools (browser).

    Playwright sync API uses greenlet internally which has strict thread-affinity.
    This executor ensures browse_page/browser_action always run in the same thread.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._executor: Optional[ThreadPoolExecutor] = None
        self._sticky_thread_id: Optional[int] = None

    def submit(self, fn, *args, **kwargs):
        import logging

        log = logging.getLogger(__name__)

        with self._lock:
            current_tid = threading.get_ident()
            if self._executor is None:
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stateful_tool")
                self._sticky_thread_id = current_tid
            elif current_tid != self._sticky_thread_id:
                log.warning(
                    f"Stateful tool thread mismatch! Expected thread {self._sticky_thread_id}, "
                    f"got {current_tid}. Resetting executor."
                )
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="stateful_tool")
                self._sticky_thread_id = current_tid
            return self._executor.submit(fn, *args, **kwargs)

    def reset(self):
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=False, cancel_futures=True)
                self._executor = None
                self._sticky_thread_id = None

    def shutdown(self, wait=True, cancel_futures=False):
        with self._lock:
            if self._executor is not None:
                self._executor.shutdown(wait=wait, cancel_futures=cancel_futures)
                self._executor = None
                self._sticky_thread_id = None


def _make_timeout_result(
    fn_name: str,
    tool_call_id: str,
    is_code_tool: bool,
    tc: Dict[str, Any],
    drive_logs: Path,
    timeout_sec: int,
    task_id: str = "",
    reset_msg: str = "",
) -> Dict[str, Any]:
    args_for_log = {}
    try:
        args = json.loads(tc["function"]["arguments"] or "{}")
        args_for_log = sanitize_tool_args_for_log(fn_name, args if isinstance(args, dict) else {})
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    issue_note = " about the issue" if not reset_msg else ""
    result = (
        f"⚠️ TOOL_TIMEOUT ({fn_name}): exceeded {timeout_sec}s limit. "
        f"The tool is still running in background but control is returned to you. "
        f"{reset_msg}Try a different approach or inform the owner{issue_note}."
    )

    append_jsonl(
        drive_logs / "events.jsonl",
        {
            "ts": utc_now_iso(),
            "type": "tool_timeout",
            "tool": fn_name,
            "args": args_for_log,
            "timeout_sec": timeout_sec,
        },
    )
    append_jsonl(
        drive_logs / "tools.jsonl",
        {"ts": utc_now_iso(), "tool": fn_name, "args": args_for_log, "result_preview": result},
    )

    return {
        "tool_call_id": tool_call_id,
        "fn_name": fn_name,
        "result": result,
        "is_error": True,
        "args_for_log": args_for_log,
        "is_code_tool": is_code_tool,
    }


def _execute_with_timeout(
    tools: Any,
    tc: Dict[str, Any],
    drive_logs: Path,
    timeout_sec: int,
    task_id: str = "",
    stateful_executor: Optional[_StatefulToolExecutor] = None,
    traceability: Any = None,
) -> Dict[str, Any]:
    fn_name = tc["function"]["name"]
    tool_call_id = tc["id"]
    is_code_tool = fn_name in tools.CODE_TOOLS
    use_stateful = stateful_executor and fn_name in STATEFUL_BROWSER_TOOLS

    if use_stateful:
        future = stateful_executor.submit(_execute_single_tool, tools, tc, drive_logs, task_id, traceability)
        try:
            return future.result(timeout=timeout_sec)
        except TimeoutError:
            stateful_executor.reset()
            reset_msg = "Browser state has been reset. "
            return _make_timeout_result(
                fn_name, tool_call_id, is_code_tool, tc, drive_logs, timeout_sec, task_id, reset_msg
            )
    else:
        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(_execute_single_tool, tools, tc, drive_logs, task_id, traceability)
            try:
                return future.result(timeout=timeout_sec)
            except TimeoutError:
                return _make_timeout_result(
                    fn_name, tool_call_id, is_code_tool, tc, drive_logs, timeout_sec, task_id, reset_msg=""
                )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)


def _handle_tool_calls(
    tool_calls: List[Dict[str, Any]],
    tools: Any,
    drive_logs: Path,
    task_id: str,
    stateful_executor: _StatefulToolExecutor,
    messages: List[Dict[str, Any]],
    llm_trace: Dict[str, Any],
    emit_progress: Callable[[str], None],
    traceability: Any = None,
) -> int:
    can_parallel = len(tool_calls) > 1 and all(
        tc.get("function", {}).get("name") in READ_ONLY_PARALLEL_TOOLS for tc in tool_calls
    )

    if not can_parallel:
        results = [
            _execute_with_timeout(
                tools,
                tc,
                drive_logs,
                tools.get_timeout(tc["function"]["name"]),
                task_id,
                stateful_executor,
                traceability,
            )
            for tc in tool_calls
        ]
    else:
        max_workers = min(len(tool_calls), 8)
        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            future_to_index = {
                executor.submit(
                    _execute_with_timeout,
                    tools,
                    tc,
                    drive_logs,
                    tools.get_timeout(tc["function"]["name"]),
                    task_id,
                    stateful_executor,
                    traceability,
                ): idx
                for idx, tc in enumerate(tool_calls)
            }
            results = [None] * len(tool_calls)
            for future in as_completed(future_to_index):
                idx = future_to_index[future]
                results[idx] = future.result()
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    return _process_tool_results(results, messages, llm_trace, emit_progress)


def _process_tool_results(
    results: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    llm_trace: Dict[str, Any],
    emit_progress: Callable[[str], None],
) -> int:
    error_count = 0
    for exec_result in results:
        fn_name = exec_result["fn_name"]
        is_error = exec_result["is_error"]
        if is_error:
            error_count += 1

        truncated_result = _truncate_tool_result(exec_result["result"])
        messages.append({"role": "tool", "tool_call_id": exec_result["tool_call_id"], "content": truncated_result})

        llm_trace["tool_calls"].append(
            {
                "tool": fn_name,
                "args": _safe_args(exec_result["args_for_log"]),
                "result": truncate_for_log(exec_result["result"], 700),
                "is_error": is_error,
            }
        )

    # Record tool chain for learning patterns
    try:
        from ouroboros.auto_system import record_tool_chain

        tool_sequence = [r["fn_name"] for r in results]
        record_tool_chain(tool_sequence, success=(error_count == 0))
    except Exception:
        pass

    return error_count


def _safe_args(v: Any) -> Any:
    try:
        return json.loads(json.dumps(v, ensure_ascii=False, default=str))
    except Exception:
        return {"_repr": repr(v)}
