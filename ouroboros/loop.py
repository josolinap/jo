"""
Ouroboros — LLM tool loop.

Core loop: send messages to LLM, execute tool calls, repeat until final response.
Extracted from agent.py to keep the agent thin.
Tool execution logic extracted to tool_executor.py.
"""

from __future__ import annotations

import json
import os
import pathlib
import queue
import threading
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

import logging

from ouroboros.llm import LLMClient, normalize_reasoning_effort, add_usage
from ouroboros.tools.registry import ToolRegistry
from ouroboros.context import (
    compact_tool_history,
    compact_tool_history_llm,
    auto_summarize_if_needed,
    smart_context_optimize,
    DifferentialContext,
)
from ouroboros.response_analyzer import analyze_response, get_analyzer
from ouroboros.utils import (
    utc_now_iso,
    append_jsonl,
    truncate_for_log,
    estimate_tokens,
)
from ouroboros.tool_executor import _StatefulToolExecutor, _handle_tool_calls
from ouroboros.traceability import get_traceability_layer

# PIPELINE_PLAN.md Feature Flags
USE_STRUCTURED_PIPELINE = os.environ.get("OUROBOROS_USE_PIPELINE", "0") == "1"
USE_CONTEXT_ENRICHMENT = os.environ.get("OUROBOROS_ENRICH_CONTEXT", "1") == "1"
USE_SEMANTIC_SYNTHESIS = os.environ.get("OUROBOROS_SYNTHESIS", "0") == "1"
USE_TASK_GRAPH = os.environ.get("OUROBOROS_TASK_GRAPH", "0") == "1"
USE_TASK_EVALUATION = os.environ.get("OUROBOROS_EVAL", "0") == "1"
USE_CODE_NORMALIZATION = os.environ.get("OUROBOROS_NORMALIZE_CODE", "1") == "1"

log = logging.getLogger(__name__)

# Initialize pipeline components (used when USE_STRUCTURED_PIPELINE is enabled)
_pipeline = None

# Track quality feedback injection state (per-task, reset in run_llm_loop)
_quality_feedback_injected: bool = False

# Track files changed across rounds for synthesis and evaluation
_files_changed_total: List[str] = []

# Track context optimization state per task (differential context optimization)
_task_context_tracker: Dict[str, DifferentialContext] = {}

# Pricing from OpenRouter API (2026-02-17). Update periodically via /api/v1/models.
_MODEL_PRICING_STATIC = {
    "anthropic/claude-opus-4.6": (5.0, 0.5, 25.0),
    "anthropic/claude-opus-4": (15.0, 1.5, 75.0),
    "anthropic/claude-sonnet-4": (3.0, 0.30, 15.0),
    "anthropic/claude-sonnet-4.6": (3.0, 0.30, 15.0),
    "anthropic/claude-sonnet-4.5": (3.0, 0.30, 15.0),
    "openai/o3": (2.0, 0.50, 8.0),
    "openai/o3-pro": (20.0, 1.0, 80.0),
    "openai/o4-mini": (1.10, 0.275, 4.40),
    "openai/gpt-4.1": (2.0, 0.50, 8.0),
    "openai/gpt-5.2": (1.75, 0.175, 14.0),
    "openai/gpt-5.2-codex": (1.75, 0.175, 14.0),
    "google/gemini-2.5-pro-preview": (1.25, 0.125, 10.0),
    "google/gemini-3-pro-preview": (2.0, 0.20, 12.0),
    "x-ai/grok-3-mini": (0.30, 0.03, 0.50),
    "qwen/qwen3.5-plus-02-15": (0.40, 0.04, 2.40),
}

_pricing_fetched = False
_cached_pricing = None
_pricing_lock = threading.Lock()


def _get_pricing() -> Dict[str, Tuple[float, float, float]]:
    """
    Lazy-load pricing. On first call, attempts to fetch from OpenRouter API.
    Falls back to static pricing if fetch fails.
    Thread-safe via module-level lock.
    """
    global _pricing_fetched, _cached_pricing

    if _pricing_fetched:
        return _cached_pricing or _MODEL_PRICING_STATIC

    with _pricing_lock:
        if _pricing_fetched:
            return _cached_pricing or _MODEL_PRICING_STATIC

        _pricing_fetched = True
        _cached_pricing = dict(_MODEL_PRICING_STATIC)

        try:
            from ouroboros.llm import fetch_openrouter_pricing

            _live = fetch_openrouter_pricing()
            if _live and len(_live) > 5:
                _cached_pricing.update(_live)
        except Exception as e:
            import logging as _log

            _log.getLogger(__name__).warning("Failed to sync pricing from OpenRouter: %s", e)
            _pricing_fetched = False

        return _cached_pricing


def _estimate_cost(
    model: str, prompt_tokens: int, completion_tokens: int, cached_tokens: int = 0, cache_write_tokens: int = 0
) -> float:
    """Estimate cost from token counts using known pricing. Returns 0 if model unknown."""
    model_pricing = _get_pricing()
    pricing = model_pricing.get(model)
    if not pricing:
        best_match = None
        best_length = 0
        for key, val in model_pricing.items():
            if model and model.startswith(key):
                if len(key) > best_length:
                    best_match = val
                    best_length = len(key)
        pricing = best_match
    if not pricing:
        return 0.0
    input_price, cached_price, output_price = pricing
    regular_input = max(0, prompt_tokens - cached_tokens)
    cost = (
        regular_input * input_price / 1_000_000
        + cached_tokens * cached_price / 1_000_000
        + completion_tokens * output_price / 1_000_000
    )
    return round(cost, 6)


def _handle_text_response(
    content: Optional[str],
    llm_trace: Dict[str, Any],
    accumulated_usage: Dict[str, Any],
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Handle LLM response without tool calls (final response)."""
    if content and content.strip():
        llm_trace["assistant_notes"].append(content.strip()[:320])

        # PIPELINE_PLAN.md Feature 3: Semantic Synthesis Pass
        synthesis_summary = None
        if USE_SEMANTIC_SYNTHESIS:
            from ouroboros.synthesis import synthesize_task

            # Use the response content as task hint for synthesis
            task_text = content[:200] if content else ""

            if task_text:
                synthesis_summary = synthesize_task(
                    task=task_text,
                    output=content or "",
                    files_changed=getattr(run_llm_loop, "_files_changed_total", []),
                    repo_dir=pathlib.Path(os.environ.get("REPO_DIR", ".")) if os.environ.get("REPO_DIR", ".") else None,
                )

        # PIPELINE_PLAN.md Feature 5: Eval Framework / Quality Scoring
        eval_report_str = None
        if USE_TASK_EVALUATION:
            from ouroboros.eval import evaluate_task

            # Use the response content as task hint for evaluation
            task_text = content[:200] if content else ""

            if task_text:
                repo_dir_str = os.environ.get("REPO_DIR")
                repo_dir = pathlib.Path(repo_dir_str) if repo_dir_str else None

                eval_report_str = evaluate_task(
                    task=task_text,
                    output=content or "",
                    files_changed=getattr(run_llm_loop, "_files_changed_total", []),
                    repo_dir=repo_dir,
                )

        # Add synthesis and eval insights to content
        insights_added = []
        if synthesis_summary:
            insights_added.append(f"\n\n## Synthesis Insights\n{synthesis_summary}")
        if eval_report_str:  # evaluate_task returns a formatted string if there are issues
            insights_added.append(f"\n\n## Quality Evaluation\n{eval_report_str}")

        if insights_added:
            content = content + "".join(insights_added)

    return (content or ""), accumulated_usage, llm_trace


def _check_budget_limits(
    budget_remaining_usd: Optional[float],
    accumulated_usage: Dict[str, Any],
    round_idx: int,
    messages: List[Dict[str, Any]],
    llm: LLMClient,
    active_model: str,
    active_effort: str,
    max_retries: int,
    drive_logs: pathlib.Path,
    task_id: str,
    event_queue: Optional[queue.Queue],
    llm_trace: Dict[str, Any],
    task_type: str = "task",
) -> Optional[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """Check budget limits and handle budget overrun."""
    if budget_remaining_usd is None:
        return None

    task_cost = accumulated_usage.get("cost", 0)
    budget_pct = task_cost / budget_remaining_usd if budget_remaining_usd > 0 else 1.0

    if budget_pct > 0.5:
        finish_reason = (
            f"Task spent ${task_cost:.3f} (>50% of remaining ${budget_remaining_usd:.2f}). Budget exhausted."
        )
        messages.append({"role": "system", "content": f"[BUDGET LIMIT] {finish_reason} Give your final response now."})
        try:
            final_msg, final_cost = _call_llm_with_retry(
                llm,
                messages,
                active_model,
                None,
                active_effort,
                max_retries,
                drive_logs,
                task_id,
                round_idx,
                event_queue,
                accumulated_usage,
                task_type,
            )
            if final_msg:
                return (final_msg.get("content") or finish_reason), accumulated_usage, llm_trace
            return finish_reason, accumulated_usage, llm_trace
        except Exception:
            log.warning("Failed to get final response after budget limit", exc_info=True)
            return finish_reason, accumulated_usage, llm_trace
    elif budget_pct > 0.3 and round_idx % 10 == 0:
        messages.append(
            {
                "role": "system",
                "content": f"[INFO] Task spent ${task_cost:.3f} of ${budget_remaining_usd:.2f}. Wrap up if possible.",
            }
        )

    return None


def _maybe_inject_self_check(
    round_idx: int,
    max_rounds: int,
    messages: List[Dict[str, Any]],
    accumulated_usage: Dict[str, Any],
    emit_progress: Callable[[str], None],
) -> None:
    """Inject a soft self-check reminder every REMINDER_INTERVAL rounds."""
    REMINDER_INTERVAL = 50
    if round_idx <= 1 or round_idx % REMINDER_INTERVAL != 0:
        return
    ctx_tokens = sum(
        estimate_tokens(str(m.get("content", "")))
        if isinstance(m.get("content"), str)
        else sum(estimate_tokens(str(b.get("text", ""))) for b in m.get("content", []) if isinstance(b, dict))
        for m in messages
    )
    task_cost = accumulated_usage.get("cost", 0)
    checkpoint_num = round_idx // REMINDER_INTERVAL

    reminder = (
        f"[CHECKPOINT {checkpoint_num} — round {round_idx}/{max_rounds}]\n"
        f"Context: ~{ctx_tokens} tokens | Cost so far: ${task_cost:.2f} | "
        f"Rounds remaining: {max_rounds - round_idx}\n\n"
        f"PAUSE AND REFLECT before continuing:\n"
        f"1. Am I making real progress, or repeating the same actions?\n"
        f"2. Is my current strategy working? Should I try something different?\n"
        f"3. Is my context bloated with old tool results I no longer need?\n"
        f"   -> If yes, call `compact_context` to summarize them selectively.\n"
        f"4. Have I been stuck on the same sub-problem for many rounds?\n"
        f"   -> If yes, consider: simplify the approach, skip the sub-problem, or finish with what I have.\n"
        f"5. Should I just STOP and return my best result so far?\n\n"
        f"This is not a hard limit — you decide. But be honest with yourself."
    )
    messages.append({"role": "system", "content": reminder})
    emit_progress(
        f"📍 Checkpoint {checkpoint_num} | Round {round_idx} | ~{ctx_tokens // 1000}k tokens | ${task_cost:.2f}"
    )


def _setup_dynamic_tools(tools_registry, tool_schemas, messages):
    """Wire tool-discovery handlers onto an existing tool_schemas list."""
    enabled_extra: set = set()

    def _handle_list_tools(ctx=None, **kwargs):
        non_core = tools_registry.list_non_core_tools()
        if not non_core:
            return "All tools are already in your active set."
        lines = [f"**{len(non_core)} additional tools available** (use `enable_tools` to activate):\n"]
        for t in non_core:
            lines.append(f"- **{t['name']}**: {t['description'][:120]}")
        return "\n".join(lines)

    def _handle_enable_tools(ctx=None, tools: str = "", **kwargs):
        names = [n.strip() for n in tools.split(",") if n.strip()]
        enabled, not_found = [], []
        for name in names:
            schema = tools_registry.get_schema_by_name(name)
            if schema and name not in enabled_extra:
                tool_schemas.append(schema)
                enabled_extra.add(name)
                enabled.append(name)
            elif name in enabled_extra:
                enabled.append(f"{name} (already active)")
            else:
                not_found.append(name)
        parts = []
        if enabled:
            parts.append(f"Enabled: {', '.join(enabled)}")
        if not_found:
            parts.append(f"Not found: {', '.join(not_found)}")
        return "\n".join(parts) if parts else "No tools specified."

    tools_registry.override_handler("list_available_tools", _handle_list_tools)
    tools_registry.override_handler("enable_tools", _handle_enable_tools)

    non_core_count = len(tools_registry.list_non_core_tools())
    if non_core_count > 0:
        messages.append(
            {
                "role": "system",
                "content": (
                    f"Note: You have {len(tool_schemas)} core tools loaded. "
                    f"There are {non_core_count} additional tools available "
                    f"(use `list_available_tools` to see them, `enable_tools` to activate). "
                    f"Core tools cover most tasks. Enable extras only when needed."
                ),
            }
        )

    return tool_schemas, enabled_extra


def _drain_incoming_messages(
    messages: List[Dict[str, Any]],
    incoming_messages: queue.Queue,
    drive_root: Optional[pathlib.Path],
    task_id: str,
    event_queue: Optional[queue.Queue],
    _owner_msg_seen: set,
) -> None:
    """Inject owner messages received during task execution."""
    while not incoming_messages.empty():
        try:
            injected = incoming_messages.get_nowait()
            messages.append({"role": "user", "content": injected})
        except queue.Empty:
            break

    if drive_root is not None and task_id:
        from ouroboros.owner_inject import drain_owner_messages

        drive_msgs = drain_owner_messages(drive_root, task_id=task_id, seen_ids=_owner_msg_seen)
        for dmsg in drive_msgs:
            messages.append({"role": "user", "content": f"[Owner message during task]: {dmsg}"})
            if event_queue is not None:
                try:
                    event_queue.put_nowait(
                        {
                            "type": "owner_message_injected",
                            "task_id": task_id,
                            "text": dmsg[:200],
                        }
                    )
                except Exception:
                    pass


def _emit_llm_usage_event(
    event_queue: Optional[queue.Queue],
    task_id: str,
    model: str,
    usage: Dict[str, Any],
    cost: float,
    category: str = "task",
) -> None:
    """Emit llm_usage event to the event queue."""
    if not event_queue:
        return
    try:
        event_queue.put_nowait(
            {
                "type": "llm_usage",
                "ts": utc_now_iso(),
                "task_id": task_id,
                "model": model,
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "cached_tokens": int(usage.get("cached_tokens") or 0),
                "cache_write_tokens": int(usage.get("cache_write_tokens") or 0),
                "cost": cost,
                "cost_estimated": not bool(usage.get("cost")),
                "usage": usage,
                "category": category,
            }
        )
    except Exception:
        log.debug("Failed to put llm_usage event to queue", exc_info=True)


def _call_llm_with_retry(
    llm: LLMClient,
    messages: List[Dict[str, Any]],
    model: str,
    tools: Optional[List[Dict[str, Any]]],
    effort: str,
    max_retries: int,
    drive_logs: pathlib.Path,
    task_id: str,
    round_idx: int,
    event_queue: Optional[queue.Queue],
    accumulated_usage: Dict[str, Any],
    task_type: str = "",
) -> Tuple[Optional[Dict[str, Any]], float]:
    """Call LLM with retry logic, usage tracking, and event emission."""
    msg = None
    last_error: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            kwargs = {"messages": messages, "model": model, "reasoning_effort": effort}
            if tools:
                kwargs["tools"] = tools
            resp_msg, usage = llm.chat(**kwargs)
            msg = resp_msg
            add_usage(accumulated_usage, usage)

            cost = float(usage.get("cost") or 0)
            if not cost:
                cost = _estimate_cost(
                    model,
                    int(usage.get("prompt_tokens") or 0),
                    int(usage.get("completion_tokens") or 0),
                    int(usage.get("cached_tokens") or 0),
                    int(usage.get("cache_write_tokens") or 0),
                )

            category = task_type if task_type in ("evolution", "consciousness", "review", "summarize") else "task"
            _emit_llm_usage_event(event_queue, task_id, model, usage, cost, category)

            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content")
            if not tool_calls and (not content or not content.strip()):
                log.warning(
                    "LLM returned empty response (no content, no tool_calls), attempt %d/%d", attempt + 1, max_retries
                )
                append_jsonl(
                    drive_logs / "events.jsonl",
                    {
                        "ts": utc_now_iso(),
                        "type": "llm_empty_response",
                        "task_id": task_id,
                        "round": round_idx,
                        "attempt": attempt + 1,
                        "model": model,
                        "raw_content": repr(content)[:500] if content else None,
                        "raw_tool_calls": repr(tool_calls)[:500] if tool_calls else None,
                        "finish_reason": msg.get("finish_reason") or msg.get("stop_reason"),
                    },
                )

                if attempt < max_retries - 1:
                    time.sleep(2**attempt)
                    continue
                return None, cost

            accumulated_usage["rounds"] = accumulated_usage.get("rounds", 0) + 1

            _round_event = {
                "ts": utc_now_iso(),
                "type": "llm_round",
                "task_id": task_id,
                "round": round_idx,
                "model": model,
                "reasoning_effort": effort,
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "cached_tokens": int(usage.get("cached_tokens") or 0),
                "cache_write_tokens": int(usage.get("cache_write_tokens") or 0),
                "cost_usd": cost,
            }
            append_jsonl(drive_logs / "events.jsonl", _round_event)
            return msg, cost

        except Exception as e:
            last_error = e
            append_jsonl(
                drive_logs / "events.jsonl",
                {
                    "ts": utc_now_iso(),
                    "type": "llm_api_error",
                    "task_id": task_id,
                    "round": round_idx,
                    "attempt": attempt + 1,
                    "model": model,
                    "error": repr(e),
                },
            )
            if attempt < max_retries - 1:
                time.sleep(min(2**attempt * 2, 30))

    return None, 0.0


# Pipeline Phase Handlers for Feature 1: Structured Pipeline Architecture
if USE_STRUCTURED_PIPELINE:
    from ouroboros.pipeline import Pipeline, PipelineContext, PipelinePhase, PhaseResult

    # Initialize pipeline with default handlers (already built into Pipeline class)
    _pipeline = Pipeline(enabled=True)
    log.info("[Pipeline] Structured pipeline enabled with default phase handlers")


def _maybe_build_task_graph(task: str) -> Optional[Any]:
    """Build task graph for complex multi-step tasks (Feature 4: Task Graph)."""
    if not USE_TASK_GRAPH:
        return None

    try:
        from ouroboros.task_graph import decompose_into_graph

        # Use the existing decompose_into_graph function which uses heuristics
        graph = decompose_into_graph(task)

        if graph:
            log.info(f"[TaskGraph] Decomposed task into {len(graph.nodes)} subtasks")
            return graph
    except Exception as e:
        log.warning(f"[TaskGraph] Failed to decompose task: {e}")

    return None


def run_llm_loop(
    messages: List[Dict[str, Any]],
    tools: ToolRegistry,
    llm: LLMClient,
    drive_logs: pathlib.Path,
    emit_progress: Callable[[str], None],
    incoming_messages: queue.Queue,
    task_type: str = "",
    task_id: str = "",
    budget_remaining_usd: Optional[float] = None,
    event_queue: Optional[queue.Queue] = None,
    initial_effort: str = "medium",
    drive_root: Optional[pathlib.Path] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """
    Core LLM-with-tools loop.

    Sends messages to LLM, executes tool calls, retries on errors.
    LLM controls model/effort via switch_model tool.
    """
    global _quality_feedback_injected

    active_model = llm.default_model()
    active_effort = initial_effort

    llm_trace: Dict[str, Any] = {"assistant_notes": [], "tool_calls": []}
    accumulated_usage: Dict[str, Any] = {}
    max_retries = 3

    from ouroboros.tools import tool_discovery as _td

    _td.set_registry(tools)

    tool_schemas = tools.schemas(core_only=True)
    tool_schemas, _enabled_extra_tools = _setup_dynamic_tools(tools, tool_schemas, messages)

    tools._ctx.event_queue = event_queue
    tools._ctx.task_id = task_id
    stateful_executor = _StatefulToolExecutor()
    _owner_msg_seen: set = set()
    traceability = get_traceability_layer(tools._ctx)

    try:
        MAX_ROUNDS = max(1, int(os.environ.get("OUROBOROS_MAX_ROUNDS", "200")))
    except (ValueError, TypeError):
        MAX_ROUNDS = 200
        log.warning("Invalid OUROBOROS_MAX_ROUNDS, defaulting to 200")

    round_idx = 0
    get_analyzer().reset()
    _quality_feedback_injected = False

    _previous_issues: List[Any] = []
    _current_skill: Any = None
    _last_reevaluation_round: int = 0
    _tool_call_count: int = 0
    _recent_responses: List[str] = []
    _consecutive_drift_rounds: int = 0

    try:
        while True:
            round_idx += 1

            if round_idx > MAX_ROUNDS:
                finish_reason = (
                    f"Task exceeded MAX_ROUNDS ({MAX_ROUNDS}). Consider decomposing into subtasks via schedule_task."
                )
                messages.append({"role": "system", "content": f"[ROUND_LIMIT] {finish_reason}"})
                try:
                    final_msg, final_cost = _call_llm_with_retry(
                        llm,
                        messages,
                        active_model,
                        None,
                        active_effort,
                        max_retries,
                        drive_logs,
                        task_id,
                        round_idx,
                        event_queue,
                        accumulated_usage,
                        task_type,
                    )
                    if final_msg:
                        return (final_msg.get("content") or finish_reason), accumulated_usage, llm_trace
                    return finish_reason, accumulated_usage, llm_trace
                except Exception:
                    log.warning("Failed to get final response after round limit", exc_info=True)
                    return finish_reason, accumulated_usage, llm_trace

            _maybe_inject_self_check(round_idx, MAX_ROUNDS, messages, accumulated_usage, emit_progress)

            ctx = tools._ctx
            if ctx.active_model_override:
                active_model = ctx.active_model_override
                ctx.active_model_override = None
            if ctx.active_effort_override:
                active_effort = normalize_reasoning_effort(ctx.active_effort_override, default=active_effort)
                ctx.active_effort_override = None

            _drain_incoming_messages(messages, incoming_messages, drive_root, task_id, event_queue, _owner_msg_seen)

            if round_idx == 0 and drive_root is not None:
                context_limit = int(os.environ.get("OUROBOROS_CONTEXT_LIMIT", "120000"))
                messages, summarize_info = auto_summarize_if_needed(messages, drive_root, context_limit)
                if summarize_info.get("auto_summarized"):
                    emit_progress(f"📝 [Memory] Auto-summarized: {summarize_info.get('reason', '')}")

                from ouroboros.context_enricher import enrich_messages

                task_text = ""
                for m in messages:
                    if m.get("role") == "user":
                        task_text = m.get("content", "")
                        break
                if task_text:
                    task_type = (
                        "code"
                        if any(kw in task_text.lower() for kw in ["code", "file", "function", "class", "implement"])
                        else "general"
                    )
                    repo_dir = pathlib.Path(os.environ.get("REPO_DIR", "."))
                    messages = enrich_messages(messages, task_text, task_type, repo_dir)

            if round_idx == 1:
                from ouroboros.tools.agent_coordinator import _coordinator

                if _coordinator is not None:
                    task_text = ""
                    for m in messages:
                        if m.get("role") == "user":
                            task_text = m.get("content", "")
                            break
                    if task_text and len(task_text) > 200:
                        decomposition = _coordinator.decompose_task(task_text, "")
                        if len(decomposition.subtasks) >= 2:
                            orch_hint = (
                                f"\n[MULTI-AGENT HINT] This task appears complex. "
                                f"Consider using `delegate_and_collect` or `decompose_task` to break it down.\n"
                                f"Detected {len(decomposition.subtasks)} subtask types: "
                                f"{', '.join(s['role'] for s in decomposition.subtasks[:4])}"
                            )
                            messages.append({"role": "system", "content": orch_hint})
                            emit_progress(
                                f"Auto-orchestration: Task decomposed into {len(decomposition.subtasks)} roles"
                            )

            if round_idx == 1:
                from ouroboros.tools.skills import (
                    detect_skill_with_triggers,
                    extract_task_from_skill_text,
                    log_skill_activation,
                )

                for m in messages:
                    if m.get("role") == "user":
                        user_text = m.get("content", "")
                        skill, matched_triggers = detect_skill_with_triggers(user_text)
                        if skill:
                            task = extract_task_from_skill_text(user_text, skill)
                            log_skill_activation(skill, matched_triggers, user_text)

                            trigger_info = ""
                            if matched_triggers:
                                trigger_info = f"\n**[Auto-detected from keywords: {', '.join(matched_triggers)}]**"

                            skill_prompt = f"""[SKILL ACTIVATED: {skill.name.upper()}{trigger_info}]

Version: {skill.version}

{skill.system_prompt_addition}

---

## Task to Analyze

{task}

---

{skill.pre_task_prompt}

{skill.post_task_prompt}"""
                            messages.append({"role": "system", "content": skill_prompt})
                            emit_progress(
                                f"🎯 [Skill] {skill.name.upper()} activated - {skill.description[:60]}... (triggers: {matched_triggers})"
                            )
                            _current_skill = skill
                            _last_reevaluation_round = round_idx
                            break

            from ouroboros.spice import get_spice_for_round, get_spice_for_analysis

            # Only inject targeted spice for HIGH severity issues (reduce spam)
            high_severity_issues = [i for i in _previous_issues if i.severity == "high"]

            if high_severity_issues:
                spice = get_spice_for_analysis(high_severity_issues)
                if spice:
                    messages.append({"role": "system", "content": f"[Targeted Spice] {spice}"})
                    # Log to internal logs only, don't bother owner
                    log.info(f"[Spice] Targeted (high severity): {high_severity_issues[0].issue_type}")
                    # Clear to prevent repeated injections
                    _previous_issues = []
            else:
                # Less aggressive: every 5 rounds instead of 3
                spice_interval = int(os.environ.get("OUROBOROS_SPICE_INTERVAL", "5"))
                spice = get_spice_for_round(round_idx, spice_interval=spice_interval)
                if spice:
                    messages.append({"role": "system", "content": f"[Spice] {spice}"})

            pending_compaction = getattr(tools._ctx, "_pending_compaction", None)
            if pending_compaction is not None:
                messages = compact_tool_history_llm(messages, keep_recent=pending_compaction)
                tools._ctx._pending_compaction = None
            elif round_idx > 8:
                messages = compact_tool_history(messages, keep_recent=6)
            elif round_idx > 3:
                if len(messages) > 60:
                    messages = compact_tool_history(messages, keep_recent=6)

            # PIPELINE_PLAN.md Feature 2: Context Enrichment Before LLM Calls
            if USE_CONTEXT_ENRICHMENT:
                from ouroboros.context_enricher import enrich_messages

                task_text = ""
                for m in messages:
                    if m.get("role") == "user":
                        task_text = m.get("content", "")
                        break

                if task_text:
                    task_type_detected = (
                        "code"
                        if any(kw in task_text.lower() for kw in ["code", "file", "function", "class", "implement"])
                        else "general"
                    )
                    repo_dir = pathlib.Path(os.environ.get("REPO_DIR", "."))
                    messages = enrich_messages(messages, task_text, task_type_detected, repo_dir)

            msg, cost = _call_llm_with_retry(
                llm,
                messages,
                active_model,
                tool_schemas,
                active_effort,
                max_retries,
                drive_logs,
                task_id,
                round_idx,
                event_queue,
                accumulated_usage,
                task_type,
            )

            if msg is None:
                fallback_list_raw = os.environ.get(
                    "OUROBOROS_MODEL_FALLBACK_LIST",
                    "stepfun/step-3.5-flash:free,arcee-ai/trinity-large-preview:free,qwen/qwen-2.5-72b-instruct:free",
                )
                fallback_candidates = [m.strip() for m in fallback_list_raw.split(",") if m.strip()]
                fallback_model = None
                for candidate in fallback_candidates:
                    if candidate != active_model:
                        fallback_model = candidate
                        break
                if fallback_model is None:
                    return (
                        (
                            f"Failed to get a response from model {active_model} after {max_retries} attempts. "
                            f"All fallback models match the active one. Try rephrasing your request."
                        ),
                        accumulated_usage,
                        llm_trace,
                    )

                fallback_progress = f"Fallback: {active_model} -> {fallback_model} after empty response"
                emit_progress(f"🔄 [Fallback] {active_model} → {fallback_model}")

                msg, fallback_cost = _call_llm_with_retry(
                    llm,
                    messages,
                    fallback_model,
                    tool_schemas,
                    active_effort,
                    max_retries,
                    drive_logs,
                    task_id,
                    round_idx,
                    event_queue,
                    accumulated_usage,
                    task_type,
                )

                if msg is None:
                    return (
                        (
                            f"Failed to get a response from the model after {max_retries} attempts. "
                            f"Fallback model ({fallback_model}) also returned no response."
                        ),
                        accumulated_usage,
                        llm_trace,
                    )

            tool_calls = msg.get("tool_calls") or []
            content = msg.get("content")
            if not tool_calls:
                task_text = ""
                return _handle_text_response(content, llm_trace, accumulated_usage)

            messages.append({"role": "assistant", "content": content or "", "tool_calls": tool_calls})

            if content and content.strip():
                emit_progress(content.strip())
                llm_trace["assistant_notes"].append(content.strip()[:320])

            error_count = _handle_tool_calls(
                tool_calls,
                tools,
                drive_logs,
                task_id,
                stateful_executor,
                messages,
                llm_trace,
                emit_progress,
                traceability,
            )

            # Track files changed during this round (from tool calls)
            files_changed_this_round = []
            for tc in tool_calls:
                if tc.get("function", {}).get("name") in ["repo_write_commit", "drive_write", "apply_patch"]:
                    # Try to extract file path from tool arguments
                    try:
                        args = json.loads(tc.get("function", {}).get("arguments", "{}"))
                        if "path" in args:
                            files_changed_this_round.append(args["path"])
                        elif "file_path" in args:
                            files_changed_this_round.append(args["file_path"])
                    except (json.JSONDecodeError, KeyError, TypeError) as e:
                        log.debug(f"Failed to parse tool args: {e}")

            # Accumulate files changed across rounds
            if not hasattr(run_llm_loop, "_files_changed_total"):
                run_llm_loop._files_changed_total = []
            run_llm_loop._files_changed_total.extend(files_changed_this_round)
            # Remove duplicates while preserving order
            seen = set()
            run_llm_loop._files_changed_total = [
                x for x in run_llm_loop._files_changed_total if not (x in seen or seen.add(x))
            ]

            # PIPELINE_PLAN.md Feature 3: Semantic Synthesis Pass
            synthesis_summary = None
            if USE_SEMANTIC_SYNTHESIS and round_idx >= 3:  # Run synthesis after a few rounds
                from ouroboros.synthesis import synthesize_task

                task_text_for_synth = ""
                for m in messages:
                    if m.get("role") == "user":
                        task_text_for_synth = m.get("content", "")
                        break

                if task_text_for_synth:
                    repo_dir_str = os.environ.get("REPO_DIR")
                    repo_dir_path = pathlib.Path(repo_dir_str) if repo_dir_str else None

                    synthesis_summary = synthesize_task(
                        task=task_text_for_synth,
                        output=content or "",
                        files_changed=getattr(run_llm_loop, "_files_changed_total", []),
                        repo_dir=repo_dir_path,
                    )

            # PIPELINE_PLAN.md Feature 5: Eval Framework / Quality Scoring
            # Note: Evaluation in mid-loop is for logging only; final eval happens in _handle_text_response
            if USE_TASK_EVALUATION and round_idx >= 2:  # Log evaluation after tool usage
                from ouroboros.eval import evaluate_task

                task_text_for_eval = ""
                for m in messages:
                    if m.get("role") == "user":
                        task_text_for_eval = m.get("content", "")
                        break

                if task_text_for_eval:
                    repo_dir_str = os.environ.get("REPO_DIR")
                    repo_dir_path = pathlib.Path(repo_dir_str) if repo_dir_str else None

                    eval_result = evaluate_task(
                        task=task_text_for_eval,
                        output=content or "",
                        files_changed=getattr(run_llm_loop, "_files_changed_total", []),
                        repo_dir=repo_dir_path,
                    )
                    if eval_result:
                        log.info(f"[Eval] Quality issue detected in round {round_idx}")

            _current_issues: List[Any] = []
            try:
                repo_dir = str(drive_root / "repo") if drive_root else ""
                analysis = analyze_response(
                    response_text=content or "",
                    tool_calls=tool_calls,
                    messages=messages,
                    repo_dir=repo_dir,
                )
                if analysis.issues:
                    issue_types = [f"{i.issue_type}({i.severity})" for i in analysis.issues]
                    log.info(
                        f"[DIAG] Response analysis R{round_idx}: score={analysis.quality_score:.2f}, issues={issue_types}"
                    )

                _current_issues = analysis.issues

                # HALLUCINATION ENFORCEMENT - Block high-severity hallucinations
                hallucination_issues = [
                    i for i in analysis.issues if i.issue_type == "hallucination" and i.severity == "high"
                ]
                if hallucination_issues and not tool_calls:
                    # High-severity hallucination without tool calls to verify
                    # Inject correction instead of sending hallucinated response
                    correction_msg = (
                        "[ANTI-HALLUCINATION] Your response contains unverified claims. "
                        "Before stating something as fact, you MUST verify it with tools:\n"
                    )
                    for issue in hallucination_issues[:3]:
                        correction_msg += f"- {issue.description}\n"
                        if issue.suggestion:
                            correction_msg += f"  Suggestion: {issue.suggestion}\n"
                    correction_msg += (
                        "\nPlease verify your claims with repo_read, grep, or other tools before continuing."
                    )

                    messages.append({"role": "system", "content": correction_msg})
                    emit_progress("⚠️ Hallucination detected - requesting verification")
                    log.warning(f"[HALLUCINATION] Blocked response with {len(hallucination_issues)} issues")
                    continue  # Skip to next round, let LLM correct

                high_severity_issues = [i for i in analysis.issues if i.severity in ("high", "medium")]
                if analysis.quality_score < 0.85 and high_severity_issues:
                    if not _quality_feedback_injected:
                        if analysis.feedback_for_next_round:
                            messages.append(
                                {
                                    "role": "system",
                                    "content": analysis.feedback_for_next_round,
                                }
                            )
                            emit_progress(
                                f"📊 Quality check: {analysis.quality_score:.0%} | Issues: {len(analysis.issues)} | {analysis.confidence} confidence"
                            )
                            _quality_feedback_injected = True
            except Exception:
                pass
            finally:
                # Track consecutive drift rounds
                drift_in_current = any(i.issue_type == "drift" for i in _current_issues)
                if drift_in_current:
                    _consecutive_drift_rounds += 1
                else:
                    _consecutive_drift_rounds = 0

                # Inject escalation if stuck in drift for too long
                if _consecutive_drift_rounds >= 5:
                    messages.append(
                        {
                            "role": "system",
                            "content": "[ESCALATION] You've been drifting for 5+ rounds. STOP analyzing. Either: (1) Make a decision NOW, or (2) Say you cannot complete the task and explain why.",
                        }
                    )
                    emit_progress(
                        "🚨 [ESCALATION] Stuck in loop for 5+ rounds. Forcing a decision or admitting blockers."
                    )
                    # Clear issues to prevent further spice spam after escalation
                    _previous_issues = []
                    _current_issues = []
                    _consecutive_drift_rounds = 0
                else:
                    _previous_issues = _current_issues

            if content:
                _recent_responses.append(content[:200])
                if len(_recent_responses) > 5:
                    _recent_responses = _recent_responses[-5:]
            _tool_call_count += len(tool_calls)

            try:
                from ouroboros.tools.skills import (
                    evaluate_skill_relevance,
                    should_reevaluate,
                    get_skill_switch_hint,
                )

                if should_reevaluate(round_idx, _tool_call_count, _last_reevaluation_round):
                    task_text = ""
                    for m in messages:
                        if m.get("role") == "user":
                            task_text = m.get("content", "")
                            break

                    context = {
                        "task_text": task_text,
                        "recent_tools": [tc.get("tool", "") for tc in tool_calls],
                        "recent_responses": _recent_responses,
                    }

                    relevance = evaluate_skill_relevance(_current_skill, context)

                    log.info(
                        f"[DIAG] Skill re-eval R{round_idx}: "
                        f"current={_current_skill.name if _current_skill else 'None'}, "
                        f"score={relevance.score:.2f}, "
                        f"switch={relevance.should_switch}"
                    )

                    if relevance.should_switch and relevance.skill:
                        switch_hint = get_skill_switch_hint(relevance)
                        if switch_hint:
                            messages.append({"role": "system", "content": switch_hint})
                            emit_progress(
                                f"🔄 [Strategy] {relevance.reason} | Switching to: {_current_skill.name if _current_skill else 'default'}"
                            )

                        _current_skill = relevance.skill
                        _last_reevaluation_round = round_idx
                        _tool_call_count = 0
            except Exception:
                pass

            budget_result = _check_budget_limits(
                budget_remaining_usd,
                accumulated_usage,
                round_idx,
                messages,
                llm,
                active_model,
                active_effort,
                max_retries,
                drive_logs,
                task_id,
                event_queue,
                llm_trace,
                task_type,
            )
            if budget_result is not None:
                return budget_result

    finally:
        if stateful_executor:
            try:
                stateful_executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                log.warning("Failed to shutdown stateful executor", exc_info=True)
        if drive_root is not None and task_id:
            try:
                from ouroboros.owner_inject import cleanup_task_mailbox

                cleanup_task_mailbox(drive_root, task_id)
            except Exception:
                log.debug("Failed to cleanup task mailbox", exc_info=True)
