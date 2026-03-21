"""Tool discovery meta-tools — lets the agent see and enable non-core tools."""

from __future__ import annotations
import logging
import os
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ouroboros.tools.registry import ToolContext, ToolEntry

if TYPE_CHECKING:
    from ouroboros.tools.registry import ToolRegistry

log = logging.getLogger(__name__)

_registry: Optional["ToolRegistry"] = None
_enabled_tools: Dict[str, List[str]] = {}  # Per-task tracking: task_id -> list of enabled tools


def set_registry(reg: "ToolRegistry") -> None:
    global _registry
    _registry = reg


def _list_available_tools(ctx: ToolContext, **kwargs) -> str:
    if _registry is None:
        return "⚠️ Tool discovery not available in this context."
    non_core = _registry.list_non_core_tools()
    non_core = [t for t in non_core if t["name"] not in ("list_available_tools", "enable_tools")]
    if not non_core:
        return "✅ All tools are available (no separate non-core set)."

    task_id = getattr(ctx, "task_id", "unknown") or "unknown"
    enabled = _enabled_tools.get(task_id, [])

    lines = [f"**{len(non_core)} additional tools available**:\n"]
    for t in non_core:
        status = " ✅" if t["name"] in enabled else ""
        lines.append(f"- **{t['name']}**{status}: {t['description'][:100]}")
    lines.append("\n💡 Use `enable_tools(tools='tool1,tool2')` to activate tools for this task.")
    return "\n".join(lines)


def _enable_tools(ctx: ToolContext, tools: str = "", **kwargs) -> str:
    if _registry is None:
        return "⚠️ Tool enablement not available in this context."

    names = [n.strip() for n in tools.split(",") if n.strip()]
    if not names:
        return "⚠️ No tools specified. Usage: enable_tools(tools='tool1,tool2')"

    task_id = getattr(ctx, "task_id", "unknown") or "unknown"
    if task_id not in _enabled_tools:
        _enabled_tools[task_id] = []

    found = []
    not_found = []
    already_enabled = []

    for name in names:
        schema = _registry.get_schema_by_name(name)
        if schema:
            if name in _enabled_tools[task_id]:
                already_enabled.append(name)
            else:
                _enabled_tools[task_id].append(name)
                found.append(name)
        else:
            not_found.append(name)

    parts = []
    if found:
        parts.append(f"✅ **Enabled for this task** ({task_id[:8]}...): {', '.join(found)}")
    if already_enabled:
        parts.append(f"ℹ️ Already enabled: {', '.join(already_enabled)}")
    if not_found:
        parts.append(f"❌ Not found: {', '.join(not_found)}")

    parts.append(
        f"\n📋 {len(_enabled_tools[task_id])} tools enabled this task. "
        f"Note: Tools reset each task (by design for isolation)."
    )

    return "\n".join(parts)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="list_available_tools",
            schema={
                "name": "list_available_tools",
                "description": (
                    "List all additional tools available but not in core set. "
                    "Shows which are currently enabled. "
                    "Use `enable_tools` to activate tools for the current task."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                    "required": [],
                },
            },
            handler=_list_available_tools,
        ),
        ToolEntry(
            name="enable_tools",
            schema={
                "name": "enable_tools",
                "description": (
                    "Enable additional tools for the current task. "
                    "Tools are added to your active tool set and available immediately. "
                    "Example: enable_tools(tools='multi_model_review,cli_generate') "
                    "Note: Tools are per-task (reset each task for safety)."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tools": {
                            "type": "string",
                            "description": "Comma-separated tool names to enable",
                        }
                    },
                    "required": ["tools"],
                },
            },
            handler=_enable_tools,
        ),
    ]
