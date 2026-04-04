"""Semantic Tool Routing — Learn optimal tool selection per task type.

Inspired by RuVector's SONA (Self-Optimizing Neural Architecture):
- Routes tasks to the best tools based on learned patterns
- Uses temporal learning data for scoring
- Integrates with cache-first context for performance
- Adapts in real-time as tool patterns evolve

Architecture:
    Task → Classify → Score Tools → Route → Execute
              ↑            ↑
         Task Type    Temporal Learning
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# Task type classification keywords
_TASK_KEYWORDS = {
    "code": [
        "code",
        "file",
        "function",
        "class",
        "implement",
        "edit",
        "fix",
        "refactor",
        "module",
        "import",
        "error",
        "bug",
        "compile",
        "test",
        "python",
        "script",
        "program",
        "develop",
        "patch",
    ],
    "research": [
        "research",
        "search",
        "find",
        "look up",
        "investigate",
        "analyze",
        "compare",
        "evaluate",
        "understand",
        "explain",
        "study",
        "explore",
    ],
    "vault": [
        "vault",
        "note",
        "concept",
        "wiki",
        "knowledge",
        "document",
        "journal",
        "identity",
        "memory",
        "learn",
        "remember",
    ],
    "git": [
        "git",
        "commit",
        "push",
        "pull",
        "branch",
        "merge",
        "diff",
        "status",
        "log",
        "tag",
        "rebase",
        "cherry-pick",
    ],
    "web": [
        "web",
        "url",
        "fetch",
        "browse",
        "scrape",
        "download",
        "http",
        "website",
        "page",
        "link",
        "search web",
    ],
    "system": [
        "health",
        "status",
        "system",
        "config",
        "setting",
        "monitor",
        "performance",
        "drift",
        "version",
        "budget",
        "cost",
    ],
}


def classify_task(task_text: str) -> str:
    """Classify a task into a task type based on keywords."""
    text_lower = task_text.lower()
    scores: Dict[str, int] = {}

    for task_type, keywords in _TASK_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[task_type] = score

    if not scores:
        return "general"

    return max(scores, key=scores.get)


def get_default_tool_order(task_type: str) -> List[str]:
    """Get default tool ordering for a task type (before learning kicks in)."""
    defaults = {
        "code": [
            "codebase_impact",
            "symbol_context",
            "code_edit",
            "repo_read",
            "run_shell",
            "repo_commit_push",
        ],
        "research": [
            "web_search",
            "web_fetch",
            "query_knowledge",
            "vault_search",
            "find_connections",
        ],
        "vault": [
            "vault_read",
            "vault_write",
            "vault_search",
            "vault_link",
            "vault_backlinks",
            "vault_graph",
        ],
        "git": [
            "git_status",
            "git_diff",
            "repo_commit_push",
            "git_graph",
            "list_github_issues",
        ],
        "web": [
            "web_search",
            "web_fetch",
            "browse_page",
            "browser_action",
            "analyze_screenshot",
        ],
        "system": [
            "codebase_health",
            "drift_detector",
            "health_alert",
            "get_evolution_status",
            "system_map",
        ],
        "general": [
            "repo_read",
            "query_knowledge",
            "web_search",
            "symbol_context",
            "vault_search",
        ],
    }
    return defaults.get(task_type, defaults["general"])


def route_tools(
    task_text: str,
    available_tools: List[str],
    learner: Optional[Any] = None,
    top_n: int = 5,
) -> Tuple[str, List[str]]:
    """Route tools for a task using semantic classification + learned patterns.

    When OUROBOROS_DSPY=1, uses DSPy signatures for classification and tool
    selection instead of keyword matching.

    Args:
        task_text: The task description
        available_tools: List of available tool names
        learner: TemporalToolLearner instance (optional)
        top_n: Number of tools to return

    Returns:
        Tuple of (task_type, ordered_tool_list)
    """
    # Standard keyword-based routing
    task_type = classify_task(task_text)

    # Feed classification into ontology tracker for cross-system learning
    _feed_ontology(task_type, get_default_tool_order(task_type))

    if learner:
        try:
            from ouroboros.temporal_learning import TemporalToolLearner

            if isinstance(learner, TemporalToolLearner):
                suggested = learner.suggest_tools(task_type, available_tools, top_n=top_n)
                if suggested and len(suggested) >= 2:
                    return task_type, suggested
        except Exception:
            log.debug("Unexpected error", exc_info=True)

    # Fallback to default ordering
    defaults = get_default_tool_order(task_type)
    ordered = [t for t in defaults if t in available_tools]

    # Use learned tool chain patterns to improve ordering
    try:
        from ouroboros.auto_system import suggest_tool_chain

        suggested_chain = suggest_tool_chain(ordered[:2])
        if suggested_chain:
            # Reorder to prioritize learned patterns
            for tool in suggested_chain:
                if tool in ordered:
                    ordered.remove(tool)
            ordered = suggested_chain + ordered
    except Exception:
        pass

    # Fill remaining slots with any available tools not yet included
    remaining = [t for t in available_tools if t not in ordered]
    ordered.extend(remaining)

    selected = ordered[:top_n]

    # Make DSPy tools always available to Jo
    for t in available_tools:
        if t.startswith("dspy_") and t not in selected:
            selected.append(t)

    return task_type, selected


def _feed_ontology(task_type: str, tools: List[str]) -> None:
    """Feed tool usage patterns into the ontology tracker."""
    try:
        from ouroboros.codebase_graph import get_ontology_tracker

        tracker = get_ontology_tracker()
        for tool in tools:
            tracker.record(task_type, tool, "uses_tool", strength=0.6)
    except Exception:
        pass


def get_routing_report(task_text: str, available_tools: List[str]) -> str:
    """Get human-readable routing report for a task."""
    task_type = classify_task(task_text)
    defaults = get_default_tool_order(task_type)

    lines = [
        f"## Tool Routing: {task_type}",
        "",
        f"**Task:** {task_text[:100]}",
        f"**Classified as:** {task_type}",
        f"**Default tool order:**",
    ]
    for i, tool in enumerate(defaults[:8], 1):
        available = "✅" if tool in available_tools else "❌"
        lines.append(f"  {i}. {available} {tool}")

    return "\n".join(lines)
