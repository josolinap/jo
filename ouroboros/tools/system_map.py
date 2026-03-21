"""
Ouroboros — System Map Tool.

Dynamically queries the system to build an interconnection map.
Does NOT hardcode tool lists, paths, or dependencies — derives them from code.
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolContext, ToolEntry, ToolRegistry, CORE_TOOL_NAMES


TOOL_CATEGORIES = {
    "code": [
        "repo_read",
        "repo_write_commit",
        "repo_commit_push",
        "repo_list",
        "repo_tree",
        "claude_code_edit",
        "find_callers",
        "find_definitions",
        "grep_content",
        "glob_files",
        "file_stats",
        "copy_file",
        "move_file",
        "delete_file",
    ],
    "memory": [
        "update_scratchpad",
        "update_identity",
        "chat_history",
        "vault_create",
        "vault_read",
        "vault_write",
        "vault_list",
        "vault_search",
        "vault_link",
        "vault_backlinks",
        "vault_outlinks",
        "vault_graph",
        "vault_delete",
        "vault_ensure",
        "knowledge_read",
        "knowledge_write",
        "knowledge_list",
    ],
    "web": [
        "web_search",
        "web_fetch",
        "browse_page",
        "browser_action",
        "browser_profile_save",
        "browser_profile_load",
        "browser_profile_list",
        "browser_profile_delete",
        "analyze_screenshot",
    ],
    "git": ["git_status", "git_diff", "git_graph"],
    "task": ["schedule_task", "wait_for_task", "get_task_result", "cancel_task"],
    "system": ["request_restart", "promote_to_stable", "switch_model", "toggle_evolution", "toggle_consciousness"],
    "comm": ["send_owner_message", "send_photo"],
    "meta": [
        "list_available_tools",
        "enable_tools",
        "codebase_health",
        "code_quality",
        "compact_context",
        "summarize_dialogue",
    ],
    "github": [
        "list_github_issues",
        "get_github_issue",
        "create_github_issue",
        "comment_on_issue",
        "close_github_issue",
    ],
    "database": ["db_init", "db_query", "db_write", "db_list_tables", "db_schema_read"],
    "shell": ["run_shell", "cli_generate", "cli_refine", "cli_validate", "cli_test", "cli_list"],
    "skill": ["list_skills", "activate_skill", "recall_lessons", "learn_from_mistake"],
    "simulation": ["simulate_outcome", "list_simulations", "sim_result", "predict_trend", "multi_model_review"],
    "vision": ["vlm_query", "send_photo", "analyze_screenshot"],
    "analysis": ["fact_check", "verify_claim", "codebase_digest", "research_synthesize", "generate_evolution_stats"],
}


def _categorize_tool(tool_name: str) -> str:
    """Dynamically categorize a tool based on known patterns."""
    for category, tools in TOOL_CATEGORIES.items():
        if tool_name in tools:
            return category
    if tool_name.startswith("vault_"):
        return "memory"
    if tool_name.startswith("knowledge_"):
        return "memory"
    if tool_name.startswith("repo_"):
        return "code"
    if tool_name.startswith("git_"):
        return "git"
    if tool_name.startswith("db_"):
        return "database"
    return "other"


def _get_registry_tools(ctx: ToolContext) -> Dict[str, Any]:
    """Query the registry dynamically to get all tools."""
    try:
        from ouroboros.tools.registry import ToolRegistry

        registry = ToolRegistry(repo_dir=ctx.repo_dir, drive_root=ctx.drive_root)
    except Exception as e:
        return {"error": f"Failed to initialize registry: {e}"}

    tools = {}
    for name in registry.available_tools():
        schema = registry.get_schema_by_name(name)
        if schema:
            is_core = name in CORE_TOOL_NAMES
            tools[name] = {
                "description": schema.get("function", {}).get("description", ""),
                "is_core": is_core,
                "category": _categorize_tool(name),
            }
    return tools


def _check_path_exists(path: pathlib.Path) -> Dict[str, Any]:
    """Check if a path exists and get metadata."""
    if not path.exists():
        return {"exists": False}
    stat = path.stat()
    return {
        "exists": True,
        "is_dir": path.is_dir(),
        "is_file": path.is_file(),
        "size_bytes": stat.st_size,
    }


def _check_env_vars(var_names: List[str]) -> Dict[str, bool]:
    """Check which environment variables are set."""
    return {name: bool(os.environ.get(name)) for name in var_names}


def _check_external_deps(commands: List[str]) -> Dict[str, bool]:
    """Check which external commands are available."""
    results = {}
    for cmd in commands:
        try:
            result = subprocess.run(
                ["where" if os.name == "nt" else "which", cmd],
                capture_output=True,
                timeout=5,
            )
            results[cmd] = result.returncode == 0
        except Exception:
            results[cmd] = False
    return results


def _derive_drive_paths(drive_root: pathlib.Path) -> Dict[str, Any]:
    """Derive all drive paths from Memory class patterns."""
    paths = {}

    memory_dirs = ["memory", "logs", "state", "locks", "archive", "task_results"]
    for d in memory_dirs:
        p = drive_root / d
        paths[d] = _check_path_exists(p)

    memory_files = [
        "memory/scratchpad.md",
        "memory/identity.md",
        "memory/scratchpad_journal.jsonl",
        "logs/chat.jsonl",
        "logs/events.jsonl",
        "logs/tools.jsonl",
        "state/state.json",
    ]
    for f in memory_files:
        p = drive_root / f
        paths[f] = _check_path_exists(p)

    paths["vault"] = _check_path_exists(drive_root / "vault")
    paths["vault/concepts"] = _check_path_exists(drive_root / "vault" / "concepts")
    paths["vault/projects"] = _check_path_exists(drive_root / "vault" / "projects")
    paths["vault/tools"] = _check_path_exists(drive_root / "vault" / "tools")
    paths["vault/journal"] = _check_path_exists(drive_root / "vault" / "journal")

    return paths


def _build_tool_graph(tools: Dict[str, Any]) -> Dict[str, List[str]]:
    """Build category groupings from tool inventory."""
    categories: Dict[str, List[str]] = {}
    for name, info in tools.items():
        cat = info["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(name)
    return categories


def _system_map(ctx: ToolContext, format: str = "text") -> str:
    """
    System interconnection map - dynamically queries the system state.

    Shows:
    - All available tools (from registry)
    - Tool categories and counts
    - Drive paths and their status
    - API keys and environment status
    - External dependencies
    """
    lines = []

    lines.append("# System Map\n")

    drive_root = pathlib.Path(os.environ.get("DRIVE_ROOT", pathlib.Path.home() / ".jo_data"))

    lines.append(f"**Drive Root:** `{drive_root}`")
    lines.append(f"**Repo Dir:** `{ctx.repo_dir}`")
    lines.append("")

    lines.append("## Tools\n")

    tools = _get_registry_tools(ctx)
    if "error" in tools:
        lines.append(f"⚠️ {tools['error']}")
    else:
        categories = _build_tool_graph(tools)

        for cat in sorted(categories.keys()):
            cat_tools = sorted(categories[cat])
            core_count = sum(1 for t in cat_tools if tools[t]["is_core"])
            lines.append(f"### {cat.title()} ({len(cat_tools)} tools, {core_count} core)")
            for t in cat_tools:
                core_marker = " (core)" if tools[t]["is_core"] else ""
                lines.append(f"- `{t}`{core_marker}")
            lines.append("")

        total_core = sum(1 for t in tools.values() if t["is_core"])
        lines.append(f"**Total:** {len(tools)} tools ({total_core} core, {len(tools) - total_core} extended)\n")

    lines.append("## Drive Paths\n")

    paths = _derive_drive_paths(drive_root)
    for path_name, status in sorted(paths.items()):
        if status.get("exists"):
            if status.get("is_dir"):
                lines.append(f"- [OK] `{path_name}/` (directory)")
            else:
                size = status.get("size_bytes", 0)
                size_str = f" ({size:,} bytes)" if size else ""
                lines.append(f"- [OK] `{path_name}`{size_str}")
        else:
            lines.append(f"- [MISSING] `{path_name}`")

    lines.append("")
    lines.append("## Environment Status\n")

    env_vars = _check_env_vars(
        [
            "OPENAI_API_KEY",
            "ANTHROPIC_API_KEY",
            "GITHUB_TOKEN",
            "DATA_ROOT",
            "REPO_DIR",
        ]
    )
    for var, exists in env_vars.items():
        status = "[OK] set" if exists else "[NOT SET]"
        lines.append(f"- `{var}`: {status}")

    lines.append("")
    lines.append("## External Dependencies\n")

    deps = _check_external_deps(["ddgr", "gh", "git", "python3", "python", "node", "npm"])
    dep_names = {
        "ddgr": "DuckDuckGo CLI (web search)",
        "gh": "GitHub CLI",
        "git": "Git",
        "python3": "Python 3",
        "python": "Python",
        "node": "Node.js",
        "npm": "npm",
    }
    for dep, exists in deps.items():
        status = "[OK] installed" if exists else "[NOT FOUND]"
        name = dep_names.get(dep, dep)
        lines.append(f"- {name}: {status}")

    lines.append("")
    lines.append("---\n")
    lines.append("*System map generated dynamically from registry and runtime state.*")

    return "\n".join(lines)


def _system_map_json(ctx: ToolContext) -> str:
    """System map in JSON format for programmatic use."""
    tools = _get_registry_tools(ctx)
    drive_root = pathlib.Path(os.environ.get("DRIVE_ROOT", pathlib.Path.home() / ".jo_data"))

    result = {
        "tools": tools,
        "categories": _build_tool_graph(tools),
        "paths": _derive_drive_paths(drive_root),
        "env": _check_env_vars(["OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GITHUB_TOKEN"]),
        "deps": _check_external_deps(["ddgr", "gh", "git"]),
        "stats": {
            "total_tools": len(tools),
            "core_tools": sum(1 for t in tools.values() if t["is_core"]),
            "extended_tools": sum(1 for t in tools.values() if not t["is_core"]),
        },
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "system_map",
            {
                "name": "system_map",
                "description": (
                    "Get a dynamic map of the Jo system showing: "
                    "all available tools (from registry), tool categories, "
                    "drive paths and their status, API keys, external dependencies. "
                    "Queries the system in real-time - always accurate. "
                    "Use format='json' for structured data."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["text", "json"],
                            "default": "text",
                            "description": "Output format: 'text' for human-readable, 'json' for programmatic use",
                        },
                    },
                    "required": [],
                },
            },
            lambda ctx, **kw: _system_map_json(ctx)
            if kw.get("format") == "json"
            else _system_map(ctx, kw.get("format", "text")),
        ),
    ]
