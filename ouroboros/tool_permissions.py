"""
Ouroboros — Tool Permission Context.

Granular tool-level permissions: deny specific tools or tool prefixes per task/context.
Inspired by Claw-code's ToolPermissionContext pattern.

Integrates with the tool registry to filter available tools based on permissions.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)

# ── Sensitive environment variables to filter from subprocesses ─────────

SENSITIVE_ENV_PATTERNS = frozenset({
    "API_KEY", "APIKEY", "SECRET", "SECRET_KEY", "TOKEN", "PASSWORD",
    "PASSWD", "CREDENTIAL", "PRIVATE_KEY", "ACCESS_KEY", "AUTH",
    "SIGNING_KEY", "ENCRYPTION_KEY", "MASTER_KEY", "GPG_KEY",
    "SSH_KEY", "DEPLOY_KEY", "REGISTRATION_TOKEN", "RUNNER_TOKEN",
})

SENSITIVE_ENV_EXACT = frozenset({
    "OPENROUTER_API_KEY", "TELEGRAM_BOT_TOKEN", "GITHUB_TOKEN",
    "ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY",
    "PLAYWRIGHT_BROWSERS_PATH",
})

# Subprocess-safe environment allowlist
SUBPROCESS_ENV_ALLOWLIST = frozenset({
    "HOME", "USER", "PATH", "SHELL", "LANG", "LC_ALL", "TERM",
    "TMPDIR", "TEMP", "TMP", "PWD", "HOSTNAME", "COLORTERM",
    "DISPLAY", "XDG_RUNTIME_DIR", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
    "REPO_DIR", "PYTHONPATH", "PYTHONIOENCODING",
    "OUROBOROS_MAX_ROUNDS", "OUROBOROS_CONTEXT_LIMIT",
    "OUROBOROS_USE_PIPELINE", "OUROBOROS_ENRICH_CONTEXT",
    "OUROBOROS_SYNTHESIS", "OUROBOROS_TASK_GRAPH",
    "OUROBOROS_EVAL", "OUROBOROS_NORMALIZE_CODE", "OUROBOROS_DSPY",
    "GITHUB_REPOSITORY", "GITHUB_REF", "GITHUB_SHA", "GITHUB_HEAD_REF",
    "GITHUB_BASE_REF", "GITHUB_ACTION", "GITHUB_ACTOR",
    "CI", "RUNNER_OS", "RUNNER_ARCH", "DEBIAN_FRONTEND",
    "LD_LIBRARY_PATH", "GITHUB_SERVER_URL", "GITHUB_API_URL",
    "GITHUB_GRAPHQL_URL", "GITHUB_WORKSPACE", "GITHUB_JOB",
    "GITHUB_RUN_NUMBER", "GITHUB_RUN_ID", "GITHUB_RETENTION_DAYS",
})

# ── Path security ─────────────────────────────────────────────────────

MAX_PATH_LENGTH = 4096

FORBIDDEN_ABSOLUTE_PREFIXES = (
    "/etc/shadow", "/etc/passwd", "/etc/sudoers",
    "/proc/sys", "/sys/", "/dev/",
    "/root/.", "/home/runner/.ssh",
)

# ── Input validation ──────────────────────────────────────────────────

MAX_INPUT_SIZES = {
    "command": 50000,
    "content": 100000,
    "prompt": 50000,
    "value": 10000,
    "text": 50000,
    "query": 5000,
    "reason": 2000,
    "commit_message": 2000,
    "url": 2048,
    "selector": 500,
    "file_path": 2000,
    "path": 2000,
    "name": 200,
    "default": 10000,
}


@dataclass
class ToolPermissionContext:
    """Controls which tools are allowed/blocked for a given context."""

    denied_tools: Set[str] = field(default_factory=set)
    denied_prefixes: Set[str] = field(default_factory=set)
    allowed_tools: Optional[Set[str]] = None  # None = allow all except denied
    sandbox_mode: bool = False  # If True, only read-only tools allowed

    READ_ONLY_PREFIXES = frozenset(
        {
            "repo_read",
            "drive_read",
            "codebase_",
            "vault_search",
            "vault_read",
            "cerebrum_search",
            "cerebrum_summary",
            "buglog_search",
            "buglog_summary",
            "anatomy_",
            "token_ledger",
        }
    )

    def blocks(self, tool_name: str) -> bool:
        if self.sandbox_mode:
            if tool_name in self.READ_ONLY_PREFIXES or any(tool_name.startswith(p) for p in self.READ_ONLY_PREFIXES):
                return False
            return True
        if tool_name in self.denied_tools:
            return True
        if any(tool_name.startswith(p) for p in self.denied_prefixes):
            return True
        if self.allowed_tools is not None and tool_name not in self.allowed_tools:
            return True
        return False

    def filter_tools(self, tool_names: List[str]) -> List[str]:
        return [t for t in tool_names if not self.blocks(t)]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "denied_tools": sorted(self.denied_tools),
            "denied_prefixes": sorted(self.denied_prefixes),
            "allowed_tools": sorted(self.allowed_tools) if self.allowed_tools else None,
            "sandbox_mode": self.sandbox_mode,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> ToolPermissionContext:
        return cls(
            denied_tools=set(data.get("denied_tools", [])),
            denied_prefixes=set(data.get("denied_prefixes", [])),
            allowed_tools=set(data["allowed_tools"]) if data.get("allowed_tools") else None,
            sandbox_mode=data.get("sandbox_mode", False),
        )

    @classmethod
    def from_args(
        cls, deny_tools: Optional[List[str]] = None, deny_prefixes: Optional[List[str]] = None, sandbox: bool = False
    ) -> ToolPermissionContext:
        return cls(
            denied_tools=set(deny_tools or []),
            denied_prefixes=set(deny_prefixes or []),
            sandbox_mode=sandbox,
        )


class PermissionManager:
    """Manages tool permission profiles."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.config_path = repo_dir / "config" / "tool_permissions.json"
        self._profiles: Optional[Dict[str, ToolPermissionContext]] = None

    def _load(self) -> Dict[str, ToolPermissionContext]:
        if self._profiles is not None:
            return self._profiles
        if self.config_path.exists():
            try:
                data = json.loads(self.config_path.read_text(encoding="utf-8"))
                self._profiles = {
                    name: ToolPermissionContext.from_dict(cfg) for name, cfg in data.get("profiles", {}).items()
                }
            except Exception as e:
                log.warning("Failed to load permission profiles: %s", e)
                self._profiles = {}
        else:
            self._profiles = {}
        return self._profiles

    def _save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {"profiles": {name: ctx.to_dict() for name, ctx in self._profiles.items()}}
        self.config_path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_profile(self, name: str) -> Optional[ToolPermissionContext]:
        return self._load().get(name)

    def create_profile(
        self,
        name: str,
        deny_tools: Optional[List[str]] = None,
        deny_prefixes: Optional[List[str]] = None,
        sandbox: bool = False,
    ) -> str:
        profiles = self._load()
        profiles[name] = ToolPermissionContext.from_args(deny_tools, deny_prefixes, sandbox)
        self._save()
        return f"Created permission profile '{name}'"

    def list_profiles(self) -> str:
        profiles = self._load()
        if not profiles:
            return "No permission profiles configured."
        lines = [f"Permission profiles ({len(profiles)}):"]
        for name, ctx in profiles.items():
            denied = len(ctx.denied_tools) + len(ctx.denied_prefixes)
            lines.append(f"- {name}: {denied} denied, sandbox={ctx.sandbox_mode}")
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _managers: Dict[str, PermissionManager] = {}

    def _get_manager(repo_dir: pathlib.Path) -> PermissionManager:
        key = str(repo_dir)
        if key not in _managers:
            _managers[key] = PermissionManager(repo_dir)
        return _managers[key]

    def permissions_create(ctx, name: str, deny_tools: str = "", deny_prefixes: str = "", sandbox: bool = False) -> str:
        tools_list = [t.strip() for t in deny_tools.split(",") if t.strip()] if deny_tools else []
        prefixes_list = [p.strip() for p in deny_prefixes.split(",") if p.strip()] if deny_prefixes else []
        return _get_manager(ctx.repo_dir).create_profile(name, tools_list, prefixes_list, sandbox)

    def permissions_list(ctx) -> str:
        return _get_manager(ctx.repo_dir).list_profiles()

    def permissions_check(ctx, profile: str, tool_name: str) -> str:
        mgr = _get_manager(ctx.repo_dir)
        p = mgr.get_profile(profile)
        if p is None:
            return f"Profile '{profile}' not found."
        blocked = p.blocks(tool_name)
        return f"Tool '{tool_name}' is {'BLOCKED' if blocked else 'ALLOWED'} by profile '{profile}'."

    return [
        ToolEntry(
            "permissions_create",
            {
                "name": "permissions_create",
                "description": "Create a tool permission profile with denied tools/prefixes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Profile name"},
                        "deny_tools": {"type": "string", "description": "Comma-separated tool names to deny"},
                        "deny_prefixes": {
                            "type": "string",
                            "description": "Comma-separated tool name prefixes to deny",
                        },
                        "sandbox": {
                            "type": "boolean",
                            "default": False,
                            "description": "Sandbox mode: only read-only tools",
                        },
                    },
                    "required": ["name"],
                },
            },
            permissions_create,
        ),
        ToolEntry(
            "permissions_list",
            {
                "name": "permissions_list",
                "description": "List all configured permission profiles.",
                "parameters": {"type": "object", "properties": {}},
            },
            permissions_list,
        ),
        ToolEntry(
            "permissions_check",
            {
                "name": "permissions_check",
                "description": "Check if a tool is allowed by a permission profile.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "profile": {"type": "string", "description": "Profile name"},
                        "tool_name": {"type": "string", "description": "Tool name to check"},
                    },
                    "required": ["profile", "tool_name"],
                },
            },
            permissions_check,
        ),
    ]
