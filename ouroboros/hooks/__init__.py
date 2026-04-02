"""
Ouroboros — Hook Architecture.

Lifecycle hooks that fire on tool execution events.
Inspired by OpenWolf's 6 hook scripts and claw-code's PreToolUse/PostToolUse pattern.

Hook types:
- pre_tool: before tool execution (can mutate/deny/rewrite)
- post_tool: after tool execution (can transform results)
- pre_read: before file read
- post_read: after file read
- pre_write: before file write
- post_write: after file write
- on_error: when tool execution fails
- on_session_start: when a new session begins
- on_session_end: when a session ends

Hook actions:
- allow: proceed normally
- deny: block execution with message
- rewrite: modify tool args before execution
- transform: modify result after execution
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

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


class HookAction(Enum):
    ALLOW = "allow"
    DENY = "deny"
    REWRITE = "rewrite"
    TRANSFORM = "transform"


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


@dataclass
class HookResult:
    """Result from a hook execution."""

    action: HookAction
    message: str = ""
    modified_args: Optional[Dict[str, Any]] = None
    modified_result: Optional[str] = None


HookHandler = Callable[[HookContext], Optional[HookResult]]


@dataclass
class Hook:
    name: str
    hook_type: HookType
    handler: HookHandler
    priority: int = 0  # Higher = runs first
    enabled: bool = True
    description: str = ""
    tool_filter: Optional[str] = None  # Only fire for specific tool


class HookManager:
    """Manages lifecycle hooks with PreToolUse/PostToolUse mutation support."""

    def __init__(self):
        self._hooks: Dict[HookType, List[Hook]] = {ht: [] for ht in HookType}
        self._stats: Dict[str, int] = {
            "total_fired": 0,
            "total_errors": 0,
            "denied": 0,
            "rewritten": 0,
            "transformed": 0,
        }

    def register(self, hook: Hook) -> None:
        self._hooks[hook.hook_type].append(hook)
        self._hooks[hook.hook_type].sort(key=lambda h: -h.priority)
        log.debug("Registered hook '%s' for %s", hook.name, hook.hook_type.value)

    def unregister(self, name: str) -> bool:
        for hook_type, hooks in self._hooks.items():
            self._hooks[hook_type] = [h for h in hooks if h.name != name]
        return True

    def _should_fire(self, hook: Hook, context: HookContext) -> bool:
        if not hook.enabled:
            return False
        if hook.tool_filter and context.tool_name != hook.tool_filter:
            return False
        return True

    def fire_pre_tool(self, tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Dict[str, Any], str]:
        """Fire pre-tool hooks. Returns (allowed, possibly_modified_args, deny_message)."""
        ctx = HookContext(hook_type=HookType.PRE_TOOL, tool_name=tool_name, args=args.copy())
        current_args = args.copy()

        for hook in self._hooks[HookType.PRE_TOOL]:
            if not self._should_fire(hook, ctx):
                continue
            try:
                result = hook.handler(ctx)
                self._stats["total_fired"] += 1
                if result:
                    if result.action == HookAction.DENY:
                        self._stats["denied"] += 1
                        return False, current_args, result.message or f"Denied by hook '{hook.name}'"
                    elif result.action == HookAction.REWRITE and result.modified_args:
                        self._stats["rewritten"] += 1
                        current_args = result.modified_args
                        ctx.args = current_args.copy()
            except Exception as e:
                log.warning("PreTool hook '%s' failed: %s", hook.name, e)
                self._stats["total_errors"] += 1

        return True, current_args, ""

    def fire_post_tool(self, tool_name: str, args: Dict[str, Any], result: str) -> str:
        """Fire post-tool hooks. Returns possibly_modified_result."""
        ctx = HookContext(hook_type=HookType.POST_TOOL, tool_name=tool_name, args=args, result=result)
        current_result = result

        for hook in self._hooks[HookType.POST_TOOL]:
            if not self._should_fire(hook, ctx):
                continue
            try:
                hook_result = hook.handler(ctx)
                self._stats["total_fired"] += 1
                if hook_result and hook_result.action == HookAction.TRANSFORM and hook_result.modified_result:
                    self._stats["transformed"] += 1
                    current_result = hook_result.modified_result
                    ctx.result = current_result
            except Exception as e:
                log.warning("PostTool hook '%s' failed: %s", hook.name, e)
                self._stats["total_errors"] += 1

        return current_result

    def fire_on_error(self, tool_name: str, args: Dict[str, Any], error: str) -> List[str]:
        ctx = HookContext(hook_type=HookType.ON_ERROR, tool_name=tool_name, args=args, error=error)
        messages = []
        for hook in self._hooks[HookType.ON_ERROR]:
            if not self._should_fire(hook, ctx):
                continue
            try:
                result = hook.handler(ctx)
                self._stats["total_fired"] += 1
                if result and result.message:
                    messages.append(result.message)
            except Exception as e:
                log.warning("OnError hook '%s' failed: %s", hook.name, e)
                self._stats["total_errors"] += 1
        return messages

    def list_hooks(self) -> str:
        lines = ["## Registered Hooks"]
        total = sum(len(hooks) for hooks in self._hooks.values())
        lines.append(f"Total: {total} hooks")
        lines.append(f"Fired: {self._stats['total_fired']} times")
        lines.append(
            f"Denied: {self._stats['denied']} | Rewritten: {self._stats['rewritten']} | Transformed: {self._stats['transformed']}"
        )
        lines.append(f"Errors: {self._stats['total_errors']}")
        for ht in HookType:
            hooks = self._hooks[ht]
            if hooks:
                lines.append(f"\n### {ht.value} ({len(hooks)} hooks)")
                for h in hooks:
                    status = "✅" if h.enabled else "❌"
                    filter_info = f" [filter: {h.tool_filter}]" if h.tool_filter else ""
                    lines.append(f"- {status} {h.name} (priority={h.priority}){filter_info}: {h.description}")
        return "\n".join(lines)

    def stats(self) -> Dict[str, Any]:
        return {
            "total_hooks": sum(len(hooks) for hooks in self._hooks.values()),
            "by_type": {ht.value: len(hooks) for ht, hooks in self._hooks.items()},
            "stats": self._stats.copy(),
        }

    def load_config(self, config_path: pathlib.Path) -> str:
        """Load hook configuration from JSON file."""
        if not config_path.exists():
            return f"Config not found: {config_path}"
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
            loaded = 0
            for hook_cfg in data.get("hooks", []):
                self._register_from_config(hook_cfg)
                loaded += 1
            return f"Loaded {loaded} hooks from {config_path}"
        except Exception as e:
            return f"Failed to load hooks config: {e}"

    def _register_from_config(self, cfg: Dict[str, Any]) -> None:
        hook_type = HookType(cfg.get("type", "pre_tool"))
        tool_filter = cfg.get("tool_filter")
        action = HookAction(cfg.get("action", "allow"))
        message = cfg.get("message", "")
        priority = cfg.get("priority", 0)

        def make_handler(
            act: HookAction,
            msg: str,
            mod_args: Optional[Dict],
            mod_result: Optional[str],
            deny_tools: Optional[List[str]],
        ):
            def handler(ctx: HookContext) -> Optional[HookResult]:
                if deny_tools and ctx.tool_name in deny_tools:
                    return HookResult(action=HookAction.DENY, message=f"Tool '{ctx.tool_name}' is denied")
                if act == HookAction.DENY:
                    return HookResult(action=HookAction.DENY, message=msg)
                elif act == HookAction.REWRITE and mod_args:
                    return HookResult(action=HookAction.REWRITE, modified_args={**ctx.args, **mod_args})
                elif act == HookAction.TRANSFORM and mod_result:
                    return HookResult(action=HookAction.TRANSFORM, modified_result=mod_result)
                return None

            return handler

        self.register(
            Hook(
                name=cfg.get("name", f"hook_{len(self._hooks[hook_type])}"),
                hook_type=hook_type,
                handler=make_handler(
                    action,
                    message,
                    cfg.get("modified_args"),
                    cfg.get("modified_result"),
                    cfg.get("deny_tools"),
                ),
                priority=priority,
                description=cfg.get("description", ""),
                tool_filter=tool_filter,
            )
        )


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
        return json.dumps(get_hook_manager().stats(), indent=2)

    def hooks_deny_tool(ctx, tool_name: str, message: str = "") -> str:
        mgr = get_hook_manager()

        def deny_handler(hook_ctx: HookContext) -> HookResult:
            return HookResult(action=HookAction.DENY, message=message or f"Tool '{hook_ctx.tool_name}' is denied")

        mgr.register(
            Hook(
                name=f"deny_{tool_name}",
                hook_type=HookType.PRE_TOOL,
                handler=deny_handler,
                description=f"Deny tool: {tool_name}",
                tool_filter=tool_name,
            )
        )
        return f"Added deny hook for tool '{tool_name}'"

    def hooks_allow_tool(ctx, tool_name: str) -> str:
        mgr = get_hook_manager()
        if mgr.unregister(f"deny_{tool_name}"):
            return f"Removed deny hook for tool '{tool_name}'"
        return f"No deny hook found for '{tool_name}'"

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
        ToolEntry(
            "hooks_deny_tool",
            {
                "name": "hooks_deny_tool",
                "description": "Add a PreToolUse hook to deny a specific tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Tool to deny"},
                        "message": {"type": "string", "default": "", "description": "Deny message"},
                    },
                    "required": ["tool_name"],
                },
            },
            hooks_deny_tool,
        ),
        ToolEntry(
            "hooks_allow_tool",
            {
                "name": "hooks_allow_tool",
                "description": "Remove a deny hook for a specific tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Tool to allow"},
                    },
                    "required": ["tool_name"],
                },
            },
            hooks_allow_tool,
        ),
    ]
