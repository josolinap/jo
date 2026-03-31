"""
Ouroboros — Hook Architecture.

Lifecycle hooks that fire on tool execution events.
Inspired by OpenWolf's 6 hook scripts pattern.

Hook types:
- pre_tool: before tool execution
- post_tool: after tool execution
- pre_read: before file read
- post_read: after file read
- pre_write: before file write
- post_write: after file write
- on_error: when tool execution fails
- on_session_start: when a new session begins
- on_session_end: when a session ends
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class HookType(Enum):
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    PRE_READ = "pre_read"
    POST_READ = "post_read"
    PRE_WRITE = "pre_write"
    POST_WRITE = "post_write"
    ON_ERROR = "on_error"
    ON_SESSION_START = "on_session_start"
    ON_SESSION_END = "on_session_end"


@dataclass
class HookContext:
    """Context passed to hook handlers."""

    hook_type: HookType
    tool_name: str = ""
    args: Dict[str, Any] = field(default_factory=dict)
    result: Optional[str] = None
    error: Optional[str] = None
    session_id: str = ""
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


HookHandler = Callable[[HookContext], Optional[str]]


@dataclass
class Hook:
    name: str
    hook_type: HookType
    handler: HookHandler
    priority: int = 0  # Higher = runs first
    enabled: bool = True
    description: str = ""


class HookManager:
    """Manages lifecycle hooks for tool execution."""

    def __init__(self):
        self._hooks: Dict[HookType, List[Hook]] = {ht: [] for ht in HookType}
        self._stats: Dict[str, int] = {"total_fired": 0, "total_errors": 0}

    def register(self, hook: Hook) -> None:
        self._hooks[hook.hook_type].append(hook)
        self._hooks[hook.hook_type].sort(key=lambda h: -h.priority)
        log.debug("Registered hook '%s' for %s", hook.name, hook.hook_type.value)

    def unregister(self, name: str) -> bool:
        for hook_type, hooks in self._hooks.items():
            self._hooks[hook_type] = [h for h in hooks if h.name != name]
        return True

    def fire(self, hook_type: HookType, context: HookContext) -> List[str]:
        results = []
        context.hook_type = hook_type
        context.timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        for hook in self._hooks[hook_type]:
            if not hook.enabled:
                continue
            try:
                result = hook.handler(context)
                if result:
                    results.append(result)
                self._stats["total_fired"] += 1
            except Exception as e:
                log.warning("Hook '%s' failed: %s", hook.name, e)
                self._stats["total_errors"] += 1
        return results

    def fire_pre_tool(self, tool_name: str, args: Dict[str, Any]) -> List[str]:
        ctx = HookContext(hook_type=HookType.PRE_TOOL, tool_name=tool_name, args=args)
        return self.fire(HookType.PRE_TOOL, ctx)

    def fire_post_tool(self, tool_name: str, args: Dict[str, Any], result: str) -> List[str]:
        ctx = HookContext(hook_type=HookType.POST_TOOL, tool_name=tool_name, args=args, result=result)
        return self.fire(HookType.POST_TOOL, ctx)

    def fire_on_error(self, tool_name: str, args: Dict[str, Any], error: str) -> List[str]:
        ctx = HookContext(hook_type=HookType.ON_ERROR, tool_name=tool_name, args=args, error=error)
        return self.fire(HookType.ON_ERROR, ctx)

    def list_hooks(self) -> str:
        lines = ["## Registered Hooks"]
        total = sum(len(hooks) for hooks in self._hooks.values())
        lines.append(f"Total: {total} hooks")
        lines.append(f"Fired: {self._stats['total_fired']} times")
        lines.append(f"Errors: {self._stats['total_errors']}")
        for ht in HookType:
            hooks = self._hooks[ht]
            if hooks:
                lines.append(f"\n### {ht.value} ({len(hooks)} hooks)")
                for h in hooks:
                    status = "✅" if h.enabled else "❌"
                    lines.append(f"- {status} {h.name} (priority={h.priority}): {h.description}")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        return {
            "total_hooks": sum(len(hooks) for hooks in self._hooks.values()),
            "by_type": {ht.value: len(hooks) for ht, hooks in self._hooks.items()},
            "stats": self._stats.copy(),
        }


# Global hook manager instance
_manager: Optional[HookManager] = None


def get_hook_manager() -> HookManager:
    global _manager
    if _manager is None:
        _manager = HookManager()
    return _manager


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def hooks_list(ctx) -> str:
        return get_hook_manager().list_hooks()

    def hooks_stats(ctx) -> str:
        import json

        return json.dumps(get_hook_manager().stats(), indent=2)

    return [
        ToolEntry(
            "hooks_list",
            {
                "name": "hooks_list",
                "description": "List all registered lifecycle hooks and their status.",
                "parameters": {"type": "object", "properties": {}},
            },
            hooks_list,
        ),
        ToolEntry(
            "hooks_stats",
            {
                "name": "hooks_stats",
                "description": "Get hook execution statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            hooks_stats,
        ),
    ]
