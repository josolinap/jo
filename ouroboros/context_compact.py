"""Context compaction functions for reducing message history tokens.

Extracted from context.py (Principle 5: Minimalism).
Handles: tool history compaction, message summarization, LLM-driven compaction.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


def _compact_tool_result(msg: dict, content: str) -> dict:
    """Compact a single tool result message."""
    is_error = content.startswith("⚠️")
    if is_error:
        summary = content[:200]
    else:
        first_line = content.split("\n")[0][:80]
        char_count = len(content)
        summary = f"{first_line}... ({char_count} chars)" if char_count > 80 else content[:200]

    return {**msg, "content": summary}


def _compact_assistant_msg(msg: dict, compact_tool_call_args_fn=None) -> dict:
    """Compact assistant message content and tool_call arguments."""
    compacted_msg = dict(msg)

    content = msg.get("content") or ""
    if len(content) > 200:
        content = content[:200] + "..."
    compacted_msg["content"] = content

    if msg.get("tool_calls"):
        compacted_tool_calls = []
        for tc in msg["tool_calls"]:
            compacted_tc = dict(tc)

            if "function" in compacted_tc:
                func = dict(compacted_tc["function"])
                args_str = func.get("arguments", "")

                if args_str:
                    compacted_tc["function"] = _compact_tool_call_arguments(func["name"], args_str)
                else:
                    compacted_tc["function"] = func

            compacted_tool_calls.append(compacted_tc)

        compacted_msg["tool_calls"] = compacted_tool_calls

    return compacted_msg


def _compact_tool_call_arguments(tool_name: str, args_json: str) -> Dict[str, Any]:
    """Compact tool call arguments for old rounds."""
    LARGE_CONTENT_TOOLS = {
        "repo_write_commit": "content",
        "drive_write": "content",
        "code_edit": "content",
        "update_scratchpad": "content",
    }

    try:
        args = json.loads(args_json)

        if tool_name in LARGE_CONTENT_TOOLS:
            large_field = LARGE_CONTENT_TOOLS[tool_name]
            if large_field in args and args[large_field]:
                args[large_field] = {"_truncated": True}
                return {"name": tool_name, "arguments": json.dumps(args, ensure_ascii=False)}

        if len(args_json) > 500:
            truncated_args = {}
            for k, v in args.items():
                if isinstance(v, str) and len(v) > 100:
                    truncated_args[k] = v[:100] + "..."
                else:
                    truncated_args[k] = v
            return {"name": tool_name, "arguments": json.dumps(truncated_args, ensure_ascii=False)}

        return {"name": tool_name, "arguments": args_json}

    except (json.JSONDecodeError, Exception):
        if len(args_json) > 500:
            safe_end = args_json.rfind(",", 0, 200)
            if safe_end > 0:
                return {"name": tool_name, "arguments": args_json[:safe_end] + "...}"}
            return {"name": tool_name, "arguments": '{"_truncated": true}'}
        return {"name": tool_name, "arguments": args_json}


def compact_tool_history(messages: list, keep_recent: int = 6) -> list:
    """Compress old tool call/result message pairs into compact summaries.

    Keeps the last `keep_recent` tool-call rounds intact.
    """
    tool_round_starts = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_round_starts.append(i)

    if len(tool_round_starts) <= keep_recent:
        return messages

    rounds_to_compact = set(tool_round_starts[:-keep_recent])

    result = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "system" and isinstance(msg.get("content"), list):
            result.append(msg)
            continue

        if msg.get("role") == "tool" and i > 0:
            parent_round = None
            for rs in reversed(tool_round_starts):
                if rs < i:
                    parent_round = rs
                    break

            if parent_round is not None and parent_round in rounds_to_compact:
                content = str(msg.get("content") or "")
                result.append(_compact_tool_result(msg, content))
                continue

        if i in rounds_to_compact and msg.get("role") == "assistant":
            result.append(_compact_assistant_msg(msg))
            continue

        result.append(msg)

    return result


def summarize_completed_task(
    task: str,
    result: str,
    files_changed: Optional[List[str]] = None,
) -> str:
    """Create a concise summary of a completed sub-task."""
    summary_parts = [f"Task: {task[:100]}"]

    result_summary = result[:200].replace("\n", " ").strip()
    if len(result) > 200:
        result_summary += "..."
    summary_parts.append(f"Result: {result_summary}")

    if files_changed:
        files_str = ", ".join(files_changed[:3])
        if len(files_changed) > 3:
            files_str += f" (+{len(files_changed) - 3} more)"
        summary_parts.append(f"Files: {files_str}")

    return " | ".join(summary_parts)


def smart_context_compress(
    messages: List[Dict[str, Any]],
    completed_tasks: Optional[List[str]] = None,
    keep_recent: int = 4,
) -> List[Dict[str, Any]]:
    """Smart context compression inspired by DeerFlow."""
    if not messages:
        return messages

    compacted = compact_tool_history(messages, keep_recent=keep_recent)

    if completed_tasks:
        task_summary = "[Context Summary] Completed tasks: " + "; ".join(t[:50] for t in completed_tasks[-5:])
        
        # Inject Agent Index Summary (Soul continuity)
        try:
            from ouroboros.agent_index import get_agent_index
            repo_dir = Path(os.environ.get("REPO_DIR", "."))
            index_summary = get_agent_index(repo_dir).get_summary()
            task_summary = f"{index_summary}\n{task_summary}"
        except Exception:
            pass

        insert_idx = 0
        for i, msg in enumerate(compacted):
            if msg.get("role") != "system":
                insert_idx = i
                break
        compacted.insert(insert_idx, {"role": "system", "content": task_summary})

    return compacted


def compact_tool_history_llm(messages: list, keep_recent: int = 6) -> list:
    """LLM-driven compaction: summarize old tool results via a light model."""
    tool_round_starts = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_round_starts.append(i)

    if len(tool_round_starts) <= keep_recent:
        return messages

    rounds_to_compact = set(tool_round_starts[:-keep_recent])

    old_results = []
    for i, msg in enumerate(messages):
        if msg.get("role") != "tool" or i == 0:
            continue
        parent_round = None
        for rs in reversed(tool_round_starts):
            if rs < i:
                parent_round = rs
                break
        if parent_round is not None and parent_round in rounds_to_compact:
            content = str(msg.get("content") or "")
            if len(content) > 120:
                tool_call_id = msg.get("tool_call_id", "")
                old_results.append({"idx": i, "tool_call_id": tool_call_id, "content": content[:1500]})

    if not old_results:
        return compact_tool_history(messages, keep_recent=keep_recent)

    batch_text = "\n---\n".join(f"[{r['tool_call_id']}]\n{r['content']}" for r in old_results[:20])
    prompt = (
        "Summarize each tool result below into 1-2 lines of key facts. "
        "Preserve errors, file paths, and important values. "
        "Output one summary per [id] block, same order.\n\n" + batch_text
    )

    try:
        from ouroboros.llm import LLMClient, DEFAULT_LIGHT_MODEL

        light_model = os.environ.get("OUROBOROS_MODEL_LIGHT") or DEFAULT_LIGHT_MODEL
        client = LLMClient()
        resp_msg, _usage = client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=light_model,
            reasoning_effort="low",
            max_tokens=1024,
        )
        summary_text = resp_msg.get("content") or ""
        if not summary_text.strip():
            raise ValueError("empty summary response")
    except Exception:
        log.warning("LLM compaction failed, falling back to truncation", exc_info=True)
        return compact_tool_history(messages, keep_recent=keep_recent)

    summary_lines = summary_text.strip().split("\n")
    summary_map: Dict[str, str] = {}
    current_id = None
    current_lines: list = []
    for line in summary_lines:
        stripped = line.strip()
        if stripped.startswith("[") and "]" in stripped:
            if current_id is not None:
                summary_map[current_id] = " ".join(current_lines).strip()
            bracket_end = stripped.index("]")
            current_id = stripped[1:bracket_end]
            rest = stripped[bracket_end + 1 :].strip()
            current_lines = [rest] if rest else []
        elif current_id is not None:
            current_lines.append(stripped)
    if current_id is not None:
        summary_map[current_id] = " ".join(current_lines).strip()

    idx_to_summary = {}
    for r in old_results:
        s = summary_map.get(r["tool_call_id"])
        if s:
            idx_to_summary[r["idx"]] = s

    result = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "system" and isinstance(msg.get("content"), list):
            result.append(msg)
            continue
        if i in idx_to_summary:
            result.append({**msg, "content": idx_to_summary[i]})
            continue
        if msg.get("role") == "tool" and i > 0:
            parent_round = None
            for rs in reversed(tool_round_starts):
                if rs < i:
                    parent_round = rs
                    break
            if parent_round is not None and parent_round in rounds_to_compact:
                content = str(msg.get("content") or "")
                result.append(_compact_tool_result(msg, content))
                continue
        if i in rounds_to_compact and msg.get("role") == "assistant":
            result.append(_compact_assistant_msg(msg))
            continue
        result.append(msg)

    return result
