"""Tool Lifecycle Hooks — PreToolUse and PostToolUse hooks.

Inspired by ECC's hook system:
- PreToolUse: runs before tool execution (proof_gate, validation)
- PostToolUse: runs after tool execution (episodic memory, learning)

Architecture:
    Tool call → PreToolUse hooks → Execute → PostToolUse hooks → Result

Hooks are registered globally and run in order. If a PreToolUse hook
returns a non-None result, the tool execution is skipped (hook intercept).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class HookResult:
    """Result of a hook execution."""

    hook_name: str
    success: bool
    intercepted: bool = False  # If True, tool execution should be skipped
    result: Optional[str] = None  # If intercepted, this replaces tool result
    duration_ms: float = 0.0


@dataclass
class ToolCall:
    """Represents a tool call for hook context."""

    name: str
    arguments: Dict[str, Any]
    call_id: str = ""
    timestamp: float = field(default_factory=time.time)


class HookRegistry:
    """Registry for tool lifecycle hooks."""

    def __init__(self) -> None:
        self._pre_hooks: List[Callable[[ToolCall], Optional[str]]] = []
        self._post_hooks: List[Callable[[ToolCall, str, bool], None]] = []

    def register_pre(self, hook: Callable[[ToolCall], Optional[str]]) -> None:
        """Register a PreToolUse hook. Return non-None to intercept."""
        self._pre_hooks.append(hook)

    def register_post(self, hook: Callable[[ToolCall, str, bool], None]) -> None:
        """Register a PostToolUse hook."""
        self._post_hooks.append(hook)

    def run_pre(self, tool_call: ToolCall) -> Optional[HookResult]:
        """Run all PreToolUse hooks. Returns intercept result if any hook intercepts."""
        for hook in self._pre_hooks:
            start = time.time()
            try:
                result = hook(tool_call)
                elapsed = (time.time() - start) * 1000
                if result is not None:
                    return HookResult(
                        hook_name=hook.__name__,
                        success=True,
                        intercepted=True,
                        result=result,
                        duration_ms=elapsed,
                    )
            except Exception as e:
                elapsed = (time.time() - start) * 1000
                log.warning("[Hook] PreToolUse %s failed: %s", hook.__name__, e)
                return HookResult(
                    hook_name=hook.__name__,
                    success=False,
                    result=f"Hook error: {e}",
                    duration_ms=elapsed,
                )
        return None

    def run_post(self, tool_call: ToolCall, result: str, success: bool) -> None:
        """Run all PostToolUse hooks."""
        for hook in self._post_hooks:
            try:
                hook(tool_call, result, success)
            except Exception as e:
                log.warning("[Hook] PostToolUse %s failed: %s", hook.__name__, e)

    def get_hook_count(self) -> Dict[str, int]:
        return {
            "pre_hooks": len(self._pre_hooks),
            "post_hooks": len(self._post_hooks),
        }


# Global registry
_registry: Optional[HookRegistry] = None


def get_hook_registry() -> HookRegistry:
    global _registry
    if _registry is None:
        _registry = HookRegistry()
        _register_default_hooks(_registry)
    return _registry


def _register_default_hooks(registry: HookRegistry) -> None:
    """Register default hooks for proof_gate and episodic memory."""

    # PreToolUse: Proof gate check
    def proof_gate_hook(tool_call: ToolCall) -> Optional[str]:
        write_tools = {"repo_write_commit", "repo_commit_push", "code_edit", "vault_write", "vault_create"}
        if tool_call.name not in write_tools:
            return None  # Not a write tool, skip

        try:
            from ouroboros.proof_gate import get_gate
            from pathlib import Path
            import os

            files_to_write = []
            for key in ("file_path", "path", "files"):
                val = tool_call.arguments.get(key, "")
                if isinstance(val, str) and val:
                    files_to_write.append(val)
                elif isinstance(val, list):
                    files_to_write.extend(val)

            if files_to_write:
                gate = get_gate(repo_dir=Path(os.environ.get("REPO_DIR", ".")))
                if gate:
                    report = gate.validate_and_report(files_to_write)
                    if "FAILED" in report:
                        return f"PROOF GATE BLOCKED: {report[:500]}"
        except Exception:
            pass
        return None

    registry.register_pre(proof_gate_hook)

    # PostToolUse: Record to episodic memory
    def episodic_memory_hook(tool_call: ToolCall, result: str, success: bool) -> None:
        # Only record significant tools (not simple reads)
        skip_tools = {
            "repo_read",
            "repo_list",
            "vault_read",
            "vault_list",
            "git_status",
            "chat_history",
            "update_scratchpad",
        }
        if tool_call.name in skip_tools:
            return

        try:
            from ouroboros.episodic_memory import get_episodic_memory
            import os

            repo_dir = Path(os.environ.get("REPO_DIR", "."))
            em = get_episodic_memory(repo_dir=repo_dir)
            em.record(
                decision=f"Called {tool_call.name}",
                action=str(tool_call.arguments)[:200],
                outcome=result[:200] if result else "",
                context="tool_call",
                success=success,
                tools_used=[tool_call.name],
            )
        except Exception:
            pass

    from pathlib import Path

    registry.register_post(episodic_memory_hook)
