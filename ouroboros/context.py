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


def _build_markdown_skills_context(env: Any) -> str:
    """Inject lightweight Markdown-based skills to adapt core prompts on the fly."""
    try:
        skills_dir = env.repo_path(".jo_skills")
        if not skills_dir.exists() or not skills_dir.is_dir():
            return ""

        skill_parts = []
        for md_file in skills_dir.glob("*.md"):
            content = md_file.read_text(encoding="utf-8", errors="ignore")
            if content.strip():
                skill_parts.append(f"### Skill: {md_file.name}\n\n{content}")

        if not skill_parts:
            return ""

        return "## Project Skills & Instructions\n\n" + "\n\n".join(skill_parts)
    except Exception:
        log.debug("Failed to read .jo_skills contents", exc_info=True)
        return ""


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

        # Check cache first (from FACT-inspired caching)
        from ouroboros.context_cache import get_cache
        import hashlib

        cache = get_cache(repo_dir=env.repo_dir)
        cache_key = f"vault_ctx:{hashlib.md5(task_text.encode()).hexdigest()[:12]}"
        hit, cached = cache.get(cache_key)
        if hit:
            return cached or ""

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
            cache.set(cache_key, "", ttl=cache.TTL_DYNAMIC)
            return ""

        matches.sort(reverse=True, key=lambda x: x[0])
        parts = ["## Relevant Vault Notes\n"]
        for score, path, preview in matches[:3]:
            parts.append(f"- **{path}**: {preview}")
        result = "\n".join(parts)
        cache.set(cache_key, result, ttl=cache.TTL_DYNAMIC)
        return result
    except Exception:
        return ""


def _build_hybrid_memory_context(env: Any, task_text: str) -> str:
    """Retrieve relevant facts from hybrid memory for context injection."""
    try:
        from ouroboros.hybrid_memory import get_hybrid_memory

        hm = get_hybrid_memory(env.drive_root)
        if hm is None:
            return ""

        return hm.retrieve(task_text)
    except Exception:
        log.debug("Hybrid memory retrieval failed", exc_info=True)
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
        log.debug("Unexpected error", exc_info=True)

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
        log.debug("Unexpected error", exc_info=True)

    return ""


def _build_health_invariants(env: Any) -> str:
    """Build health invariants section. Delegates to health_invariants.py."""
    from ouroboros.health_invariants import build_health_invariants

    return build_health_invariants(env)


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

    skills_ctx = _build_markdown_skills_context(env)
    if skills_ctx:
        semi_stable_parts.append(skills_ctx)

    # Magic keyword detection and skill injection
    task_text_for_keywords = task.get("text", "") or ""
    if task_text_for_keywords:
        try:
            from ouroboros.skills import get_detector, get_skill_manager

            # Detect magic keywords
            detector = get_detector()
            keyword_ctx = detector.build_context_injection(task_text_for_keywords)
            if keyword_ctx:
                dynamic_parts_insert = keyword_ctx
                # Insert before dynamic content
                semi_stable_parts.append(dynamic_parts_insert)

            # Match and inject skills
            skill_mgr = get_skill_manager(env.repo_dir)
            skill_ctx = skill_mgr.get_active_skills(task_text_for_keywords)
            if skill_ctx:
                semi_stable_parts.append(skill_ctx)
        except Exception:
            log.debug("Failed to build keyword/skill context", exc_info=True)

    # State manager context injection (notepad, project memory, etc.)
    try:
        from ouroboros.skills import get_state_manager

        state_mgr = get_state_manager(env.repo_dir)
        state_ctx = state_mgr.get_full_context()
        if state_ctx:
            semi_stable_parts.append(state_ctx)
    except Exception:
        log.debug("Failed to build state context", exc_info=True)

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

    # Hybrid memory — record user message + retrieve relevant facts
    if task_text:
        try:
            from ouroboros.hybrid_memory import get_hybrid_memory

            hm = get_hybrid_memory(env.drive_root)
            if hm:
                hm.add_message("user", task_text)
        except Exception:
            log.debug("Hybrid memory recording failed", exc_info=True)
        memory_ctx = _build_hybrid_memory_context(env, task_text)
        if memory_ctx:
            dynamic_parts.append(memory_ctx)

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


# Re-export compact functions from context_compact for backward compatibility
from ouroboros.context_compact import (  # noqa: E402
    _compact_tool_result,
    _compact_assistant_msg,
    _compact_tool_call_arguments,
    compact_tool_history,
    summarize_completed_task,
    smart_context_compress,
    compact_tool_history_llm,
)


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
                    log.debug("Unexpected error", exc_info=True)
    except Exception:
        log.debug("Unexpected error", exc_info=True)

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
