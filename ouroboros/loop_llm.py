"""LLM calling and first-round setup for loop.

Extracted from loop.py (Principle 5: Minimalism).
Handles: LLM retry logic, first-round context enrichment.
"""

from __future__ import annotations

import logging
import os
import pathlib
import queue
import time
from typing import Any, Callable, Dict, List, Optional, Tuple

from ouroboros.llm import LLMClient, add_usage, normalize_reasoning_effort
from ouroboros.tools.registry import ToolRegistry
from ouroboros.utils import utc_now_iso, append_jsonl

log = logging.getLogger(__name__)


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
    estimate_cost_fn=None,
    emit_llm_usage_event_fn=None,
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
            if not cost and estimate_cost_fn:
                cost = estimate_cost_fn(
                    model,
                    int(usage.get("prompt_tokens") or 0),
                    int(usage.get("completion_tokens") or 0),
                    int(usage.get("cached_tokens") or 0),
                    int(usage.get("cache_write_tokens") or 0),
                )

            category = task_type if task_type in ("evolution", "consciousness", "review", "summarize") else "task"
            if emit_llm_usage_event_fn:
                emit_llm_usage_event_fn(event_queue, task_id, model, usage, cost, category)

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


def _handle_first_round_setup(
    messages: List[Dict[str, Any]],
    drive_root: Optional[pathlib.Path],
    emit_progress: Callable[[str], None],
    tools: ToolRegistry,
    handle_context_enrichment_fn=None,
) -> Tuple[List[Dict[str, Any]], Optional[Any], int, str]:
    """Handle all first-round setup logic: context enrichment, task decomposition, skill detection, ontology."""
    current_skill = None
    last_reevaluation_round = 0
    ontology_task_type = "general"

    # 1. Context enrichment and auto-summarization
    if drive_root is not None and handle_context_enrichment_fn:
        messages = handle_context_enrichment_fn(messages, drive_root, emit_progress)

    # 2. Task decomposition check
    try:
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
                    emit_progress(f"Auto-orchestration: Task decomposed into {len(decomposition.subtasks)} roles")
    except Exception:
        log.debug("Task decomposition check failed", exc_info=True)

    # 3. Skill detection
    try:
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
                        f"[Skill] {skill.name.upper()} activated - {skill.description[:60]}... (triggers: {matched_triggers})"
                    )
                    current_skill = skill
                    last_reevaluation_round = 1
                    break
    except Exception:
        log.debug("Skill detection failed", exc_info=True)

    # 4. Ontology integration
    try:
        from ouroboros.codebase_graph import get_ontology_for_task

        task_text = ""
        for m in messages:
            if m.get("role") == "user":
                task_text = m.get("content", "")
                break

        if task_text:
            task_ontology_info = get_ontology_for_task(task_text)
            ontology_task_type = task_ontology_info["task_type"]

            ontology_msg = (
                f"[Ontology] Task type: {task_ontology_info['task_type']}\n"
                f"Requires: {', '.join(task_ontology_info['requires'][:3])}\n"
                f"Produces: {', '.join(task_ontology_info['produces'][:3])}\n"
                f"Typical tools: {', '.join(task_ontology_info['typical_tools'][:3])}"
            )

            try:
                from ouroboros.codebase_graph import get_task_ontology_profile

                profile = get_task_ontology_profile(task_ontology_info["task_type"])
                if profile["top_tools"]:
                    top = profile["top_tools"][0]
                    ontology_msg += f"\nLearned best tool: {top['tool']} (confidence: {top['confidence']})"
                if profile["produces"]:
                    ontology_msg += f"\nMost produced: {profile['produces'][0]['artifact']}"
            except Exception:
                log.debug("Ontology profile enrichment failed", exc_info=True)

            messages.append({"role": "system", "content": ontology_msg})
    except Exception:
        log.debug("Ontology integration failed", exc_info=True)

    return messages, current_skill, last_reevaluation_round, ontology_task_type
