"""
Ouroboros context builder.

Assembles LLM context from prompts, memory, logs, and runtime state.
Extracted from agent.py to keep the agent thin and focused.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import pathlib
import subprocess
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.utils import (
    utc_now_iso,
    read_text,
    clip_text,
    estimate_tokens,
    get_git_info,
)
from ouroboros.memory import Memory

log = logging.getLogger(__name__)


def _build_user_content(task: Dict[str, Any]) -> Any:
    """Build user message content. Supports text + optional image."""
    text = task.get("text", "")
    image_b64 = task.get("image_base64")
    image_mime = task.get("image_mime", "image/jpeg")
    image_caption = task.get("image_caption", "")

    if not image_b64:
        # Return fallback text if both text and image are empty
        if not text:
            return "(empty message)"
        return text

    # Multipart content with text + image
    parts = []
    # Combine caption and text for the text part
    combined_text = ""
    if image_caption:
        combined_text = image_caption
    if text and text != image_caption:
        combined_text = (combined_text + "\n" + text).strip() if combined_text else text

    # Always include a text part when there's an image
    if not combined_text:
        combined_text = "Analyze the screenshot"

    parts.append({"type": "text", "text": combined_text})
    parts.append({"type": "image_url", "image_url": {"url": f"data:{image_mime};base64,{image_b64}"}})
    return parts


def _build_runtime_section(env: Any, task: Dict[str, Any]) -> str:
    """Build the runtime context section (utc_now, repo_dir, drive_root, git_head, git_branch, task info, budget info)."""
    # --- Git context ---
    try:
        git_branch, git_sha = get_git_info(env.repo_dir)
    except Exception:
        log.debug("Failed to get git info for context", exc_info=True)
        git_branch, git_sha = "unknown", "unknown"

    # --- Budget calculation ---
    budget_info = None
    try:
        state_json = _safe_read(env.drive_path("state/state.json"), fallback="{}")
        state_data = json.loads(state_json)
        spent_usd = float(state_data.get("spent_usd", 0))
        total_usd = float(os.environ.get("TOTAL_BUDGET", "1"))
        remaining_usd = total_usd - spent_usd
        budget_info = {"total_usd": total_usd, "spent_usd": spent_usd, "remaining_usd": remaining_usd}
    except Exception:
        log.debug("Failed to calculate budget info for context", exc_info=True)
        pass

    # --- Runtime context JSON ---
    runtime_data = {
        "utc_now": utc_now_iso(),
        "repo_dir": str(env.repo_dir),
        "drive_root": str(env.drive_root),
        "git_head": git_sha,
        "git_branch": git_branch,
        "task": {"id": task.get("id"), "type": task.get("type")},
    }
    if budget_info:
        runtime_data["budget"] = budget_info
    runtime_ctx = json.dumps(runtime_data, ensure_ascii=False, indent=2)
    return "## Runtime context\n\n" + runtime_ctx


def _build_memory_sections(memory: Memory) -> List[str]:
    """Build scratchpad, identity, dialogue summary sections."""
    sections = []

    scratchpad_raw = memory.load_scratchpad()
    sections.append("## Scratchpad\n\n" + clip_text(scratchpad_raw, 90000))

    identity_raw = memory.load_identity()
    sections.append("## Identity\n\n" + clip_text(identity_raw, 80000))

    # Dialogue summary (key moments from chat history)
    summary_path = memory.drive_root / "memory" / "dialogue_summary.md"
    if summary_path.exists():
        summary_text = read_text(summary_path)
        if summary_text.strip():
            sections.append("## Dialogue Summary\n\n" + clip_text(summary_text, 20000))

    return sections


def _build_recent_sections(memory: Memory, env: Any, task_id: str = "") -> List[str]:
    """Build recent chat, recent progress, recent tools, recent events sections."""
    sections = []

    chat_summary = memory.summarize_chat(memory.read_jsonl_tail("chat.jsonl", 200))
    if chat_summary:
        sections.append("## Recent chat\n\n" + chat_summary)

    progress_entries = memory.read_jsonl_tail("progress.jsonl", 200)
    if task_id:
        progress_entries = [e for e in progress_entries if e.get("task_id") == task_id]
    progress_summary = memory.summarize_progress(progress_entries, limit=15)
    if progress_summary:
        sections.append("## Recent progress\n\n" + progress_summary)

    tools_entries = memory.read_jsonl_tail("tools.jsonl", 200)
    if task_id:
        tools_entries = [e for e in tools_entries if e.get("task_id") == task_id]
    tools_summary = memory.summarize_tools(tools_entries)
    if tools_summary:
        sections.append("## Recent tools\n\n" + tools_summary)

    events_entries = memory.read_jsonl_tail("events.jsonl", 200)
    if task_id:
        events_entries = [e for e in events_entries if e.get("task_id") == task_id]
    events_summary = memory.summarize_events(events_entries)
    if events_summary:
        sections.append("## Recent events\n\n" + events_summary)

    supervisor_summary = memory.summarize_supervisor(memory.read_jsonl_tail("supervisor.jsonl", 200))
    if supervisor_summary:
        sections.append("## Supervisor\n\n" + supervisor_summary)

    return sections


def _build_vault_context(env: Any, task_text: str) -> str:
    """Find vault notes relevant to the current task. Makes vault participatory."""
    try:
        vault_dir = env.repo_path("vault")
        if not vault_dir.exists():
            return ""

        # Extract key terms from task (words > 3 chars, lowercase)
        # Split on '.' to handle "agent.py", "identity.md" etc.
        terms = []
        for w in task_text.split():
            stem = w.split(".")[0]
            stripped = stem.strip(".,;:!?()[]{}\"'`~@#$%^&*=+<>/\\|")
            if len(stripped) > 3 and stripped.isalpha():
                terms.append(stripped.lower())
        if not terms:
            return ""

        matches = []
        for md_file in vault_dir.rglob("*.md"):
            if md_file.name.startswith("."):
                continue
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            content_lower = content.lower()
            filename_lower = md_file.stem.lower()
            score = sum(1 for t in terms if t in content_lower or t in filename_lower)
            if score >= 2:
                rel = md_file.relative_to(vault_dir)
                # Extract first meaningful paragraph (skip leading frontmatter only)
                lines = content.split("\n")
                body_lines = []
                in_frontmatter = False
                for line in lines:
                    stripped = line.strip()
                    if stripped == "---" and not body_lines and not in_frontmatter:
                        in_frontmatter = True
                        continue
                    if stripped == "---" and in_frontmatter:
                        in_frontmatter = False
                        continue
                    if not in_frontmatter and stripped:
                        body_lines.append(stripped)
                    if len(body_lines) >= 3:
                        break
                preview = " ".join(body_lines)[:200]
                matches.append((score, str(rel).replace("\\", "/"), preview))

        if not matches:
            return ""

        matches.sort(reverse=True, key=lambda x: x[0])
        parts = ["## Relevant Vault Notes\n"]
        for score, path, preview in matches[:3]:
            parts.append(f"- **{path}**: {preview}")
        return "\n".join(parts)
    except Exception:
        return ""


def _build_recent_commits_section(repo_dir: pathlib.Path, limit: int = 10) -> str:
    """Build recent git commits section for restart continuity."""
    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", str(limit), "origin/dev..HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        unpushed = result.stdout.strip()
        if unpushed:
            return f"## Recent unpushed commits\n\n{unpushed}\n"
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["git", "log", "--oneline", "-n", str(limit), "HEAD"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            timeout=10,
        )
        recent = result.stdout.strip()
        if recent:
            return f"## Recent commits\n\n{recent}\n"
    except Exception:
        pass

    return ""


def _build_health_invariants(env: Any) -> str:
    """Build health invariants section for LLM-first self-detection.

    Surfaces anomalies as informational text. The LLM (not code) decides
    what action to take based on what it reads here. (Bible P0+P3)

    Verification tracking is first because anti-hallucination is critical.
    """
    checks = []

    # 1. VERIFICATION TRACKING (anti-hallucination) - MOST IMPORTANT
    try:
        from ouroboros.memory import Memory

        mem = Memory(drive_root=env.drive_root)
        stats = mem.get_verification_stats()
        recent = stats.get("recent_verifications", 0)
        total = stats.get("total_verifications", 0)
        last = stats.get("last_verification", "never")
        if recent == 0 and total > 0:
            checks.append(f"⚠️ VERIFICATION: No verifications in last 24h (total: {total})")
        elif recent > 0:
            checks.append(f"✅ VERIFICATION: {recent} verifications in 24h ({total} total)")
        else:
            checks.append("ℹ️ VERIFICATION: Tracking active (no entries yet)")
    except Exception:
        pass

    # 2. Version sync: VERSION file vs pyproject.toml
    try:
        ver_file = read_text(env.repo_path("VERSION")).strip()
        pyproject = read_text(env.repo_path("pyproject.toml"))
        pyproject_ver = ""
        for line in pyproject.splitlines():
            if line.strip().startswith("version"):
                pyproject_ver = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        if ver_file and pyproject_ver and ver_file != pyproject_ver:
            checks.append(f"CRITICAL: VERSION DESYNC — VERSION={ver_file}, pyproject.toml={pyproject_ver}")
        elif ver_file:
            checks.append(f"OK: version sync ({ver_file})")
    except Exception:
        pass

    # 2. Budget drift
    try:
        state_json = read_text(env.drive_path("state/state.json"))
        state_data = json.loads(state_json)
        if state_data.get("budget_drift_alert"):
            drift_pct = state_data.get("budget_drift_pct", 0)
            our = state_data.get("spent_usd", 0)
            theirs = state_data.get("openrouter_total_usd", 0)
            checks.append(f"WARNING: BUDGET DRIFT {drift_pct:.1f}% — tracked=${our:.2f} vs OpenRouter=${theirs:.2f}")
        else:
            checks.append("OK: budget drift within tolerance")
    except Exception:
        pass

    # 3. Per-task cost anomalies
    try:
        from supervisor.state import per_task_cost_summary

        costly = [t for t in per_task_cost_summary(5) if t["cost"] > 5.0]
        for t in costly:
            checks.append(
                f"WARNING: HIGH-COST TASK — task_id={t['task_id']} cost=${t['cost']:.2f} rounds={t['rounds']}"
            )
        if not costly:
            checks.append("OK: no high-cost tasks (>$5)")
    except Exception:
        pass

    # 4. Identity.md awareness (missing or stale)
    try:
        import time as _time

        identity_path = env.drive_path("memory/identity.md")
        if not identity_path.exists():
            checks.append("⚠️ MISSING IDENTITY — identity.md not found, will be auto-created")
        else:
            age_hours = (_time.time() - identity_path.stat().st_mtime) / 3600
            if age_hours > 8:
                checks.append(f"WARNING: STALE IDENTITY — identity.md last updated {age_hours:.0f}h ago")
            else:
                checks.append("OK: identity.md recent")
    except Exception:
        pass

    # 4b. Scratchpad awareness
    try:
        import time as _time

        scratchpad_path = env.drive_path("memory/scratchpad.md")
        if not scratchpad_path.exists():
            checks.append("⚠️ MISSING SCRATCHPAD — scratchpad.md not found")
        else:
            age_hours = (_time.time() - scratchpad_path.stat().st_mtime) / 3600
            if age_hours > 24:
                checks.append(f"INFO: SCRATCHPAD STALE — {age_hours:.0f}h since last update")
            elif age_hours > 1:
                checks.append(f"OK: scratchpad updated {age_hours:.1f}h ago")
    except Exception:
        pass

    # 4c. Memory directory health
    try:
        memory_dir = env.drive_path("memory")
        required_files = ["identity.md", "scratchpad.md"]
        missing = [f for f in required_files if not (memory_dir / f).exists()]
        if missing:
            checks.append(f"⚠️ MISSING MEMORY FILES — {', '.join(missing)} will be auto-created")
        else:
            checks.append("OK: memory files present")
    except Exception:
        pass

    # 5. Duplicate processing detection: same owner message text appearing in multiple tasks
    try:
        import hashlib

        msg_hash_to_tasks: Dict[str, set] = {}
        tail_bytes = 1_000_000  # 1MB to capture more history

        def _scan_file_for_injected(path, type_field="type", type_value="owner_message_injected"):
            if not path.exists():
                return
            file_size = path.stat().st_size
            with path.open("r", encoding="utf-8") as f:
                if file_size > tail_bytes:
                    f.seek(file_size - tail_bytes)
                    f.readline()
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if ev.get(type_field) != type_value:
                            continue
                        text = ev.get("text", "")
                        if not text and "event_repr" in ev:
                            # Historical entries in supervisor.jsonl lack "text";
                            # try to extract task_id at least for presence detection
                            text = ev.get("event_repr", "")[:200]
                        if not text:
                            continue
                        text_hash = hashlib.md5(text.encode()).hexdigest()[:12]
                        tid = ev.get("task_id") or "unknown"
                        if text_hash not in msg_hash_to_tasks:
                            msg_hash_to_tasks[text_hash] = set()
                        msg_hash_to_tasks[text_hash].add(tid)
                    except (json.JSONDecodeError, ValueError):
                        continue

        _scan_file_for_injected(env.drive_path("logs/events.jsonl"))
        # Also check supervisor.jsonl for historically unhandled events
        _scan_file_for_injected(
            env.drive_path("logs/supervisor.jsonl"),
            type_field="event_type",
            type_value="owner_message_injected",
        )

        dupes = {h: tids for h, tids in msg_hash_to_tasks.items() if len(tids) > 1}
        if dupes:
            checks.append(
                f"CRITICAL: DUPLICATE PROCESSING — {len(dupes)} message(s) "
                f"appeared in multiple tasks: {', '.join(str(sorted(tids)) for tids in dupes.values())}"
            )
        else:
            checks.append("OK: no duplicate message processing detected")
    except Exception:
        pass

    # 6. CORRECTNESS INVARIANT (Bible P3: Everything is permitted, as long as correct)
    try:
        from ouroboros.memory import Memory

        mem = Memory(drive_root=env.drive_root)
        stats = mem.get_verification_stats()
        recent = stats.get("recent_verifications", 0)
        total = stats.get("total_verifications", 0)

        if recent == 0 and total > 0:
            checks.append(
                "⚠️ CORRECTNESS: No file/code verifications in 24h. "
                "When asserting facts about code, verify FIRST (repo_read) before claiming."
            )
        elif recent > 0 and total > 0:
            checks.append(f"OK: correctness tracking active ({recent} verifications in 24h, {total} total)")
    except Exception:
        pass

    # 7. Session continuity awareness
    try:
        import time as _time

        events_path = env.drive_path("logs/events.jsonl")
        if events_path.exists():
            try:
                with events_path.open("rb") as f:
                    f.seek(0, 2)
                    f.seek(max(0, f.tell() - 10000))
                    f.readline()
                    last_lines = f.read().decode("utf-8", errors="replace").strip().split("\n")

                last_event_time = None
                for line in reversed(last_lines):
                    if line.strip():
                        try:
                            evt = json.loads(line)
                            if evt.get("ts"):
                                last_event_time = _time.mktime(_time.strptime(evt["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
                                break
                        except Exception:
                            continue

                if last_event_time:
                    hours_since = (_time.time() - last_event_time) / 3600
                    if hours_since < 0.1:
                        checks.append("OK: session active (last event <6min ago)")
                    elif hours_since < 1:
                        checks.append(f"INFO: session idle ({int(hours_since * 60)}min since last event)")
                    elif hours_since < 24:
                        checks.append(f"INFO: session resumed ({hours_since:.1f}h since last event)")
                    else:
                        checks.append(f"INFO: fresh start ({hours_since:.0f}h since last event)")
            except Exception:
                pass
    except Exception:
        pass

    # 8. Vault staleness — check if codebase_overview.md references a stale commit
    try:
        overview_path = env.repo_path("vault/concepts/codebase_overview.md")
        if overview_path.exists():
            import re as _re

            overview_content = read_text(overview_path)
            sha_match = _re.search(r"git:\s*`?([a-f0-9]+)`?", overview_content)
            if sha_match:
                note_sha = sha_match.group(1)
                current_sha = ""
                try:
                    import subprocess as _sp

                    result = _sp.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(env.repo_dir),
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    current_sha = result.stdout.strip()[:12] if result.returncode == 0 else ""
                except Exception:
                    pass
                if current_sha and note_sha and len(note_sha) >= 7:
                    # Normalize both to same length for comparison
                    compare_len = min(len(current_sha), len(note_sha), 12)
                    if current_sha[:compare_len] != note_sha[:compare_len]:
                        checks.append(
                            f"INFO: VAULT STALE — codebase_overview.md references {note_sha[:8]}, HEAD is {current_sha[:8]}. "
                            f"Consider running scan_repo() to refresh."
                        )
                elif current_sha:
                    checks.append(f"OK: vault overview fresh (HEAD={current_sha[:8]})")
    except Exception:
        pass

    if not checks:
        return ""
    return "## Health Invariants\n\n" + "\n".join(f"- {c}" for c in checks)


def build_llm_messages(
    env: Any,
    memory: Memory,
    task: Dict[str, Any],
    review_context_builder: Optional[Any] = None,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Build the full LLM message context for a task.

    Args:
        env: Env instance with repo_path/drive_path helpers
        memory: Memory instance for scratchpad/identity/logs
        task: Task dict with id, type, text, etc.
        review_context_builder: Optional callable for review tasks (signature: () -> str)

    Returns:
        (messages, cap_info) tuple:
            - messages: List of message dicts ready for LLM
            - cap_info: Dict with token trimming metadata
    """
    # --- Extract task type for adaptive context ---
    task_type = str(task.get("type") or "user")

    # --- Read base prompts and state ---
    base_prompt = _safe_read(
        env.repo_path("prompts/SYSTEM.md"), fallback="You are Jo. Your base prompt could not be loaded."
    )
    bible_md = _safe_read(env.repo_path("BIBLE.md"))
    readme_md = _safe_read(env.repo_path("README.md"))
    state_json = _safe_read(env.drive_path("state/state.json"), fallback="{}")

    # --- Load memory ---
    memory.ensure_files()

    # --- Assemble messages with 3-block prompt caching ---
    # Block 1: Static content (SYSTEM.md + BIBLE.md + README) — cached
    # Block 2: Semi-stable content (identity + scratchpad + knowledge) — cached
    # Block 3: Dynamic content (state + runtime + recent logs) — uncached

    # BIBLE.md always included (Constitution requires it for every decision)
    # README.md only for evolution/review (architecture context)
    needs_full_context = task_type in ("evolution", "review", "scheduled")
    static_text = base_prompt + "\n\n" + "## BIBLE.md\n\n" + clip_text(bible_md, 180000)
    if needs_full_context:
        static_text += "\n\n## README.md\n\n" + clip_text(readme_md, 180000)

    # Semi-stable content: identity, scratchpad, knowledge
    # These change ~once per task, not per round
    semi_stable_parts = []
    semi_stable_parts.extend(_build_memory_sections(memory))

    kb_index_path = env.drive_path("memory/knowledge/_index.md")
    if kb_index_path.exists():
        kb_index = kb_index_path.read_text(encoding="utf-8")
        if kb_index.strip():
            semi_stable_parts.append("## Knowledge base\n\n" + clip_text(kb_index, 50000))

    semi_stable_text = "\n\n".join(semi_stable_parts)

    # Dynamic content: changes every round
    dynamic_parts = [
        "## Drive state\n\n" + clip_text(state_json, 90000),
        _build_runtime_section(env, task),
    ]

    # Health invariants — surfaces anomalies for LLM-first self-detection (Bible P0+P3)
    health_section = _build_health_invariants(env)
    if health_section:
        dynamic_parts.append(health_section)

    # Recent git commits — helps agent understand recent changes on restart
    if needs_full_context:
        commits_section = _build_recent_commits_section(env.repo_dir, limit=5)
        if commits_section:
            dynamic_parts.append(commits_section)

    # Vault context — relevant vault notes for this task (makes vault participatory)
    task_text = task.get("text", "") or ""
    if task_text:
        vault_ctx = _build_vault_context(env, task_text)
        if vault_ctx:
            dynamic_parts.append(vault_ctx)

    dynamic_parts.extend(_build_recent_sections(memory, env, task_id=task.get("id", "")))

    if str(task.get("type") or "") == "review" and review_context_builder is not None:
        try:
            review_ctx = review_context_builder()
            if review_ctx:
                dynamic_parts.append(review_ctx)
        except Exception:
            log.debug("Failed to build review context", exc_info=True)
            pass

    dynamic_text = "\n\n".join(dynamic_parts)

    # System message with 3 content blocks for optimal caching
    messages: List[Dict[str, Any]] = [
        {
            "role": "system",
            "content": [
                {
                    "type": "text",
                    "text": static_text,
                    "cache_control": {"type": "ephemeral", "ttl": "1h"},
                },
                {
                    "type": "text",
                    "text": semi_stable_text,
                    "cache_control": {"type": "ephemeral"},
                },
                {
                    "type": "text",
                    "text": dynamic_text,
                },
            ],
        },
        {"role": "user", "content": _build_user_content(task)},
    ]

    # --- Soft-cap token trimming ---
    messages, cap_info = apply_message_token_soft_cap(messages, 200000)

    return messages, cap_info


def apply_message_token_soft_cap(
    messages: List[Dict[str, Any]],
    soft_cap_tokens: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Trim prunable context sections if estimated tokens exceed soft cap.

    Returns (pruned_messages, cap_info_dict).
    """

    def _estimate_message_tokens(msg: Dict[str, Any]) -> int:
        """Estimate tokens for a message, handling multipart content."""
        content = msg.get("content", "")
        if isinstance(content, list):
            # Multipart content: sum tokens from all text blocks
            total = 0
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += estimate_tokens(str(block.get("text", "")))
            return total + 6
        return estimate_tokens(str(content)) + 6

    estimated = sum(_estimate_message_tokens(m) for m in messages)
    info: Dict[str, Any] = {
        "estimated_tokens_before": estimated,
        "estimated_tokens_after": estimated,
        "soft_cap_tokens": soft_cap_tokens,
        "trimmed_sections": [],
    }

    if soft_cap_tokens <= 0 or estimated <= soft_cap_tokens:
        return messages, info

    # Prune log summaries from the dynamic text block in multipart system messages
    prunable = ["## Recent chat", "## Recent progress", "## Recent tools", "## Recent events", "## Supervisor"]
    pruned = copy.deepcopy(messages)
    for prefix in prunable:
        if estimated <= soft_cap_tokens:
            break
        for i, msg in enumerate(pruned):
            content = msg.get("content")

            # Handle multipart content (trim from dynamic text block)
            if isinstance(content, list) and msg.get("role") == "system":
                # Find the dynamic text block (the block without cache_control)
                for j, block in enumerate(content):
                    if isinstance(block, dict) and block.get("type") == "text" and "cache_control" not in block:
                        text = block.get("text", "")
                        if prefix in text:
                            # Remove this section from the dynamic text
                            lines = text.split("\n\n")
                            new_lines = []
                            skip_section = False
                            for line in lines:
                                if line.startswith(prefix):
                                    skip_section = True
                                    info["trimmed_sections"].append(prefix)
                                    continue
                                if line.startswith("##"):
                                    skip_section = False
                                if not skip_section:
                                    new_lines.append(line)

                            block["text"] = "\n\n".join(new_lines)
                            estimated = sum(_estimate_message_tokens(m) for m in pruned)
                            break
                break

            # Handle legacy string content (for backwards compatibility)
            elif isinstance(content, str) and content.startswith(prefix):
                pruned.pop(i)
                info["trimmed_sections"].append(prefix)
                estimated = sum(_estimate_message_tokens(m) for m in pruned)
                break

    info["estimated_tokens_after"] = estimated
    return pruned, info


def _compact_tool_result(msg: dict, content: str) -> dict:
    """
    Compact a single tool result message.

    Args:
        msg: Original tool result message dict
        content: Content string to compact

    Returns:
        Compacted message dict
    """
    is_error = content.startswith("⚠️")
    # Create a short summary
    if is_error:
        summary = content[:200]  # Keep error details
    else:
        # Keep first line or first 80 chars
        first_line = content.split("\n")[0][:80]
        char_count = len(content)
        summary = f"{first_line}... ({char_count} chars)" if char_count > 80 else content[:200]

    return {**msg, "content": summary}


def _compact_assistant_msg(msg: dict) -> dict:
    """
    Compact assistant message content and tool_call arguments.

    Args:
        msg: Original assistant message dict

    Returns:
        Compacted message dict
    """
    compacted_msg = dict(msg)

    # Trim content (progress notes)
    content = msg.get("content") or ""
    if len(content) > 200:
        content = content[:200] + "..."
    compacted_msg["content"] = content

    # Compact tool_call arguments
    if msg.get("tool_calls"):
        compacted_tool_calls = []
        for tc in msg["tool_calls"]:
            compacted_tc = dict(tc)

            # Always preserve id and function name
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


def compact_tool_history(messages: list, keep_recent: int = 6) -> list:
    """
    Compress old tool call/result message pairs into compact summaries.

    Keeps the last `keep_recent` tool-call rounds intact (they may be
    referenced by the LLM). Older rounds get their tool results truncated
    to a short summary line, and tool_call arguments are compacted.

    This dramatically reduces prompt tokens in long tool-use conversations
    without losing important context (the tool names and whether they succeeded
    are preserved).
    """
    # Find all indices that are tool-call assistant messages
    # (messages with tool_calls field)
    tool_round_starts = []
    for i, msg in enumerate(messages):
        if msg.get("role") == "assistant" and msg.get("tool_calls"):
            tool_round_starts.append(i)

    if len(tool_round_starts) <= keep_recent:
        return messages  # Nothing to compact

    # Rounds to compact: all except the last keep_recent
    rounds_to_compact = set(tool_round_starts[:-keep_recent])

    # Build compacted message list
    result = []
    for i, msg in enumerate(messages):
        # Skip system messages with multipart content (prompt caching format)
        if msg.get("role") == "system" and isinstance(msg.get("content"), list):
            result.append(msg)
            continue

        if msg.get("role") == "tool" and i > 0:
            # Check if the preceding assistant message (with tool_calls)
            # is one we want to compact
            # Find which round this tool result belongs to
            parent_round = None
            for rs in reversed(tool_round_starts):
                if rs < i:
                    parent_round = rs
                    break

            if parent_round is not None and parent_round in rounds_to_compact:
                # Compact this tool result
                content = str(msg.get("content") or "")
                result.append(_compact_tool_result(msg, content))
                continue

        # For compacted assistant messages, also trim the content (progress notes)
        # AND compact tool_call arguments
        if i in rounds_to_compact and msg.get("role") == "assistant":
            result.append(_compact_assistant_msg(msg))
            continue

        result.append(msg)

    return result


def create_isolated_context(
    task: str,
    relevant_files: Optional[List[str]] = None,
    max_context_tokens: int = 4000,
) -> List[Dict[str, Any]]:
    """Create an isolated context for sub-agent execution.

    Inspired by DeerFlow's isolated sub-agent context approach.
    Creates a fresh context with only the task and relevant files,
    not the full conversation history.

    Args:
        task: The task description for the sub-agent
        relevant_files: List of file paths to include in context
        max_context_tokens: Maximum tokens for context

    Returns:
        List of messages for the sub-agent
    """
    import pathlib

    messages = []

    # Add system message with task context
    system_msg = {
        "role": "system",
        "content": (
            f"You are a sub-agent working on a specific task. "
            f"Focus only on this task. Do not reference previous conversations.\n\n"
            f"TASK: {task}"
        ),
    }
    messages.append(system_msg)

    # Add relevant file contents if provided
    if relevant_files:
        file_contents = []
        for file_path in relevant_files[:5]:  # Limit to 5 files
            try:
                path = pathlib.Path(file_path)
                if path.exists() and path.is_file():
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    # Truncate long files
                    if len(content) > 2000:
                        content = content[:1000] + "\n... (truncated) ...\n" + content[-1000:]
                    file_contents.append(f"=== {file_path} ===\n{content}")
            except Exception:
                continue

        if file_contents:
            context_msg = {
                "role": "user",
                "content": (
                    f"Here are the relevant files for your task:\n\n"
                    + "\n\n".join(file_contents)
                    + f"\n\nNow complete this task: {task}"
                ),
            }
            messages.append(context_msg)
        else:
            # No files, just give the task
            messages.append({"role": "user", "content": task})
    else:
        messages.append({"role": "user", "content": task})

    return messages


def summarize_completed_task(
    task: str,
    result: str,
    files_changed: Optional[List[str]] = None,
) -> str:
    """Create a concise summary of a completed sub-task.

    Used to replace detailed tool call history with a brief summary,
    keeping the main context lean.

    Args:
        task: Original task description
        result: Task result/output
        files_changed: List of files that were modified

    Returns:
        Concise summary string
    """
    summary_parts = [f"Task: {task[:100]}"]

    # Summarize result (keep first 200 chars)
    result_summary = result[:200].replace("\n", " ").strip()
    if len(result) > 200:
        result_summary += "..."
    summary_parts.append(f"Result: {result_summary}")

    # List files changed
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
    """Smart context compression inspired by DeerFlow.

    Compresses context by:
    1. Summarizing completed sub-tasks
    2. Offloading old tool results
    3. Keeping recent + active context

    Args:
        messages: Full message history
        completed_tasks: List of completed task descriptions
        keep_recent: Number of recent tool rounds to keep intact

    Returns:
        Compressed message list
    """
    if not messages:
        return messages

    # First apply standard compaction
    compacted = compact_tool_history(messages, keep_recent=keep_recent)

    # If we have completed tasks, add a summary
    if completed_tasks:
        task_summary = f"[Context Summary] Completed tasks: " + "; ".join(t[:50] for t in completed_tasks[-5:])
        # Insert after system messages
        insert_idx = 0
        for i, msg in enumerate(compacted):
            if msg.get("role") != "system":
                insert_idx = i
                break
        compacted.insert(insert_idx, {"role": "system", "content": task_summary})

    return compacted


def compact_tool_history_llm(messages: list, keep_recent: int = 6) -> list:
    """LLM-driven compaction: summarize old tool results via a light model.

    Falls back to simple truncation (compact_tool_history) on any error.
    Called when the agent explicitly invokes the compact_context tool.
    """
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


def _compact_tool_call_arguments(tool_name: str, args_json: str) -> Dict[str, Any]:
    """
    Compact tool call arguments for old rounds.

    For tools with large content payloads, remove the large field and add _truncated marker.
    For other tools, truncate arguments if > 500 chars.

    Args:
        tool_name: Name of the tool
        args_json: JSON string of tool arguments

    Returns:
        Dict with 'name' and 'arguments' (JSON string, possibly compacted)
    """
    # Tools with large content fields that should be stripped
    LARGE_CONTENT_TOOLS = {
        "repo_write_commit": "content",
        "drive_write": "content",
        "code_edit": "content",
        "update_scratchpad": "content",
    }

    try:
        args = json.loads(args_json)

        # Check if this tool has a large content field to remove
        if tool_name in LARGE_CONTENT_TOOLS:
            large_field = LARGE_CONTENT_TOOLS[tool_name]
            if large_field in args and args[large_field]:
                args[large_field] = {"_truncated": True}
                return {"name": tool_name, "arguments": json.dumps(args, ensure_ascii=False)}

        # For other tools, if args JSON is > 500 chars, truncate values in dict
        if len(args_json) > 500:
            truncated_args = {}
            for k, v in args.items():
                if isinstance(v, str) and len(v) > 100:
                    truncated_args[k] = v[:100] + "..."
                else:
                    truncated_args[k] = v
            return {"name": tool_name, "arguments": json.dumps(truncated_args, ensure_ascii=False)}

        # Otherwise return unchanged
        return {"name": tool_name, "arguments": args_json}

    except (json.JSONDecodeError, Exception):
        # If we can't parse JSON, truncate safely at last complete key
        if len(args_json) > 500:
            safe_end = args_json.rfind(",", 0, 200)
            if safe_end > 0:
                return {"name": tool_name, "arguments": args_json[:safe_end] + "...}"}
            return {"name": tool_name, "arguments": '{"_truncated": true}'}
        return {"name": tool_name, "arguments": args_json}


def _safe_read(path: pathlib.Path, fallback: str = "") -> str:
    """Read a file, returning fallback if it doesn't exist or errors."""
    try:
        if path.exists():
            return read_text(path)
    except Exception:
        log.debug(f"Failed to read file {path} in _safe_read", exc_info=True)
        pass
    return fallback


# ---------------------------------------------------------------------------
# Auto-summarization for long conversations (inspired by Deep Agents)
# ---------------------------------------------------------------------------

CONTEXT_SUMMARIZATION_THRESHOLD = 0.7  # Trigger at 70% of context limit


def _get_context_token_count(messages: List[Dict[str, Any]]) -> int:
    """Estimate total tokens in messages."""

    def _estimate_msg_tokens(msg: Dict[str, Any]) -> int:
        content = msg.get("content", "")
        if isinstance(content, list):
            total = 0
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    total += estimate_tokens(str(block.get("text", "")))
            return total + 6
        return estimate_tokens(str(content)) + 6

    return sum(_estimate_msg_tokens(m) for m in messages)


def _summarize_chat_history(drive_root: pathlib.Path, keep_recent: int = 50) -> Optional[str]:
    """Summarize older chat history, returning a compact summary string.

    Reads chat.jsonl, summarizes older messages (beyond keep_recent),
    and returns a summary. Returns None if not enough history to summarize.
    """
    try:
        chat_path = drive_root / "memory" / "chat.jsonl"
        if not chat_path.exists():
            return None

        lines = chat_path.read_text(encoding="utf-8").strip().split("\n")
        if len(lines) <= keep_recent + 10:
            return None  # Not enough history to summarize

        # Parse messages
        recent_lines = lines[-keep_recent:] if len(lines) > keep_recent else lines
        older_lines = lines[: len(lines) - keep_recent] if len(lines) > keep_recent else []

        if not older_lines:
            return None

        # Extract key info from older messages
        older_messages = []
        for line in older_lines:
            try:
                msg = json.loads(line)
                direction = msg.get("direction", "?")
                text = msg.get("text", "")[:300]  # Truncate for prompt
                if text:
                    prefix = "Owner:" if direction == "in" else "Jo:"
                    older_messages.append(f"{prefix} {text}")
            except Exception:
                continue

        if not older_messages:
            return None

        # Build summary prompt
        history_text = "\n".join(older_messages[:100])  # Limit to recent 100
        prompt = (
            "Summarize this conversation history into key points:\n"
            "- What did the owner ask about?\n"
            "- What did Jo do or say?\n"
            "- Any important decisions or conclusions?\n"
            "Keep it concise (max 500 words).\n\n"
            f"Conversation:\n{history_text}"
        )

        # Call light model to summarize
        from ouroboros.llm import LLMClient, DEFAULT_LIGHT_MODEL

        light_model = os.environ.get("OUROBOROS_MODEL_LIGHT") or DEFAULT_LIGHT_MODEL
        client = LLMClient()
        resp_msg, _usage = client.chat(
            messages=[{"role": "user", "content": prompt}],
            model=light_model,
            reasoning_effort="low",
            max_tokens=1024,
        )
        summary = resp_msg.get("content", "").strip()
        if summary:
            log.info(f"Auto-summarized {len(older_messages)} chat messages")
            return summary

    except Exception:
        log.debug("Failed to summarize chat history", exc_info=True)

    return None


def auto_summarize_if_needed(
    messages: List[Dict[str, Any]],
    drive_root: pathlib.Path,
    context_limit: int = 120000,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Check if context needs summarization and perform it automatically.

    Inspired by Deep Agents' automatic context compression.
    Triggered when context reaches 70% of the limit.

    Returns (updated_messages, info_dict).
    """
    info: Dict[str, Any] = {
        "auto_summarized": False,
        "reason": "",
    }

    current_tokens = _get_context_token_count(messages)
    threshold = int(context_limit * CONTEXT_SUMMARIZATION_THRESHOLD)

    # Only proceed if we're approaching the threshold
    if current_tokens < threshold:
        return messages, info

    # Check if chat history has been summarized recently (avoid repeated summarization)
    try:
        state_path = drive_root / "state" / "state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            last_summary = state.get("last_chat_summary_ts", "")
            if last_summary:
                from datetime import datetime, timedelta, timezone

                try:
                    last_dt = datetime.fromisoformat(last_summary.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last_dt < timedelta(hours=1):
                        info["reason"] = "recently summarized"
                        return messages, info
                except Exception:
                    pass
    except Exception:
        pass

    return messages, info


# ============================================================================
# DIFFERENTIAL CONTEXT - Inspired by pi-mono's differential rendering
# ============================================================================


def _hash_message(msg: Dict[str, Any]) -> str:
    """Create a hash for a message to track if it's been seen."""
    import hashlib

    # Create a stable representation
    content = msg.get("content", "")
    role = msg.get("role", "")
    tool_calls = msg.get("tool_calls")

    # Build hash input
    parts = [f"role:{role}"]

    if isinstance(content, str):
        parts.append(f"content:{content[:500]}")  # First 500 chars
    elif isinstance(content, list):
        # Multipart content
        for item in content:
            if isinstance(item, dict):
                parts.append(f"part:{item.get('type', '')}:{str(item.get('text', ''))[:200]}")

    if tool_calls:
        for tc in tool_calls[:5]:  # Max 5 tool calls for hash
            func = tc.get("function", {})
            parts.append(f"tool:{func.get('name', '')}:{func.get('arguments', '')[:100]}")

    hash_input = "|".join(parts)
    return hashlib.md5(hash_input.encode()).hexdigest()[:16]


class DifferentialContext:
    """Track what context the LLM has seen and provide incremental updates.

    Inspired by pi-mono's differential rendering approach.
    Only sends messages the LLM hasn't seen yet, reducing token usage.
    """

    def __init__(self):
        self._seen_hashes: Dict[str, int] = {}  # hash -> message index
        self._last_full_context_size: int = 0

    def get_incremental_messages(
        self,
        messages: List[Dict[str, Any]],
        force_full: bool = False,
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """Get only the messages the LLM hasn't seen yet.

        Args:
            messages: Full message list
            force_full: If True, return all messages (for first call or reset)

        Returns:
            Tuple of:
            - Incremental messages (new + system messages)
            - Stats dict with compression info
        """
        if force_full or not self._seen_hashes:
            # First call or forced full - return everything
            hashes = {_hash_message(msg): i for i, msg in enumerate(messages)}
            self._seen_hashes = hashes
            self._last_full_context_size = len(messages)

            return messages, {
                "mode": "full",
                "total_messages": len(messages),
                "new_messages": len(messages),
                "saved_tokens": 0,
            }

        # Find new messages
        new_messages = []
        new_hashes = {}
        system_messages = []  # Always include system messages

        for i, msg in enumerate(messages):
            msg_hash = _hash_message(msg)
            new_hashes[msg_hash] = i

            # Always include system messages (they may have changed)
            if msg.get("role") == "system":
                system_messages.append(msg)
                continue

            # Check if we've seen this message
            if msg_hash not in self._seen_hashes:
                new_messages.append(msg)

        # Update seen hashes
        self._seen_hashes = new_hashes

        # Build result: system messages + new messages
        if new_messages:
            # Include system messages at the start
            result = system_messages + new_messages
            mode = "incremental"
        else:
            # No new messages, just return system messages
            result = system_messages
            mode = "system_only"

        # Estimate token savings
        total_chars = sum(len(str(m.get("content", ""))) for m in messages)
        new_chars = sum(len(str(m.get("content", ""))) for m in result)
        saved_chars = max(0, total_chars - new_chars)

        stats = {
            "mode": mode,
            "total_messages": len(messages),
            "new_messages": len(new_messages),
            "system_messages": len(system_messages),
            "estimated_saved_chars": saved_chars,
        }

        self._last_full_context_size = len(messages)

        return result, stats

    def reset(self) -> None:
        """Reset the differential context (e.g., on new task)."""
        self._seen_hashes.clear()
        self._last_full_context_size = 0

    def get_stats(self) -> Dict[str, Any]:
        """Get current tracking statistics."""
        return {
            "seen_hashes": len(self._seen_hashes),
            "last_context_size": self._last_full_context_size,
        }


def get_differential_context(
    messages: List[Dict[str, Any]],
    context_tracker: Optional[DifferentialContext] = None,
    force_full: bool = False,
) -> Tuple[List[Dict[str, Any]], DifferentialContext, Dict[str, Any]]:
    """Get differential context for LLM calls.

    This is the main entry point for differential context.
    Returns incremental messages and updates the tracker.

    Args:
        messages: Full message list
        context_tracker: Existing tracker (creates new one if None)
        force_full: Force full context on this call

    Returns:
        Tuple of:
        - Messages to send (incremental or full)
        - Updated context tracker
        - Stats dict
    """
    if context_tracker is None:
        context_tracker = DifferentialContext()

    result_messages, stats = context_tracker.get_incremental_messages(messages, force_full=force_full)

    return result_messages, context_tracker, stats


def smart_context_optimize(
    messages: List[Dict[str, Any]],
    max_tokens: int = 8000,
    context_tracker: Optional[DifferentialContext] = None,
) -> Tuple[List[Dict[str, Any]], DifferentialContext, Dict[str, Any]]:
    """Optimize context for LLM calls using multiple strategies.

    Combines:
    1. Differential context (only new messages)
    2. Token budget enforcement
    3. Smart compaction

    Args:
        messages: Full message list
        max_tokens: Maximum tokens to send
        context_tracker: Existing tracker

    Returns:
        Tuple of:
        - Optimized messages
        - Updated context tracker
        - Optimization stats
    """
    # Step 1: Get differential context
    if context_tracker is None:
        context_tracker = DifferentialContext()

    incremental_msgs, diff_stats = context_tracker.get_incremental_messages(messages)

    # Step 2: Check token budget
    estimated_tokens = estimate_tokens(json.dumps(incremental_msgs))

    if estimated_tokens <= max_tokens:
        # Within budget, return as-is
        return (
            incremental_msgs,
            context_tracker,
            {
                **diff_stats,
                "estimated_tokens": estimated_tokens,
                "within_budget": True,
            },
        )

    # Step 3: Over budget - apply compaction
    # First try standard compaction
    compacted = compact_tool_history(incremental_msgs, keep_recent=3)

    estimated_tokens = estimate_tokens(json.dumps(compacted))

    if estimated_tokens <= max_tokens:
        return (
            compacted,
            context_tracker,
            {
                **diff_stats,
                "estimated_tokens": estimated_tokens,
                "within_budget": True,
                "compaction_applied": True,
            },
        )

    # Step 4: Still over budget - aggressive truncation
    # Keep system messages + most recent messages
    system_msgs = [m for m in compacted if m.get("role") == "system"]
    other_msgs = [m for m in compacted if m.get("role") != "system"]

    # Keep only recent messages that fit budget
    result = list(system_msgs)
    budget_remaining = max_tokens - estimate_tokens(json.dumps(system_msgs))

    for msg in reversed(other_msgs):
        msg_tokens = estimate_tokens(json.dumps(msg))
        if msg_tokens <= budget_remaining:
            result.insert(len(system_msgs), msg)  # Insert after system messages
            budget_remaining -= msg_tokens
        else:
            break

    return (
        result,
        context_tracker,
        {
            **diff_stats,
            "estimated_tokens": max_tokens - budget_remaining,
            "within_budget": True,
            "aggressive_truncation": True,
            "messages_truncated": len(other_msgs) - (len(result) - len(system_msgs)),
        },
    )
