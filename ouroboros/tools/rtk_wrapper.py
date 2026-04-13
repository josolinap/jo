"""
RTK Wrapper Tool for Ouroboros.

This tool provides RTK (Rust Token Killer) integration for token-efficient
shell command execution in Ouroboros.
"""

from __future__ import annotations

import json
import os
import pathlib
import shlex
import subprocess
from typing import Any

from ouroboros.utils import (
    utc_now_iso,
    append_jsonl,
    truncate_for_log,
)

from ouroboros.tools.registry import ToolContext


def _get_rtk_path() -> str:
    """Get the path to the RTK executable."""
    # Check common installation locations
    possible_paths = [
        # User local bin
        os.path.expanduser("~/.local/bin/rtk"),
        os.path.expanduser("~/bin/rtk"),
        # Windows specific
        os.path.expanduser("~\\bin\\rtk.exe"),
        # Direct in PATH (if installed globally)
        "rtk",
    ]

    for path in possible_paths:
        if os.path.isfile(path) and os.access(path, os.X_OK):
            return path
        # Also check without extension on Windows
        if os.name == "nt":
            path_exe = path + ".exe"
            if os.path.isfile(path_exe) and os.access(path_exe, os.X_OK):
                return path_exe

    # Fallback to just "rtk" and let subprocess handle PATH resolution
    return "rtk"


def _run_rtk_command(
    ctx: ToolContext,
    base_cmd: str,
    args: list[str] | None = None,
    timeout: int = 120,
    cwd: str = "",
) -> str:
    """
    Run a command through RTK for token-efficient output.

    Args:
        ctx: Tool context
        base_cmd: Base command (e.g., "git", "ls", "cargo")
        args: Command arguments
        timeout: Timeout in seconds
        cwd: Working directory (relative to repo_dir)

    Returns:
        Command output as string
    """
    rtk_path = _get_rtk_path()

    # Build the command: rtk <base_cmd> [args...]
    cmd_parts = [rtk_path, base_cmd]
    if args:
        cmd_parts.extend(args)

    # Log the command being executed
    log_cmd = " ".join(shlex.quote(part) for part in cmd_parts)
    ctx.emit_progress_fn(f"[RTK] Executing: {log_cmd}")

    try:
        # Determine working directory
        work_dir = ctx.repo_dir
        if cwd:
            candidate = (ctx.repo_dir / cwd).resolve()
            if candidate.exists() and candidate.is_dir():
                work_dir = candidate

        # Execute the command
        result = subprocess.run(
            cmd_parts,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        # Combine stdout and stderr
        output = result.stdout
        if result.stderr:
            output += "\n--- STDERR ---\n" + result.stderr

        # Add exit code prefix like the original run_shell
        prefix = f"exit_code={result.returncode}\n"
        final_output = prefix + output

        # Truncate if too large (matching original behavior)
        if len(final_output) > 50000:
            final_output = final_output[:25000] + "\n...(truncated)...\n" + final_output[-25000:]

        return final_output

    except subprocess.TimeoutExpired:
        return f"⚠️ TIMEOUT: RTK command exceeded {timeout}s."
    except FileNotFoundError:
        return f"⚠️ RTK not found at {rtk_path}. Please install RTK: https://github.com/rtk-ai/rtk"
    except Exception as e:
        return f"⚠️ RTK_ERROR: {e}"


def _rtk_git(ctx: ToolContext, *args: str) -> str:
    """Run git command through RTK."""
    return _run_rtk_command(ctx, "git", list(args))


def _rtk_ls(ctx: ToolContext, *args: str) -> str:
    """Run ls command through RTK."""
    return _run_rtk_command(ctx, "ls", list(args))


def _rtk_find(ctx: ToolContext, *args: str) -> str:
    """Run find command through RTK."""
    return _run_rtk_command(ctx, "find", list(args))


def _rtk_grep(ctx: ToolContext, *args: str) -> str:
    """Run grep command through RTK."""
    return _run_rtk_command(ctx, "grep", list(args))


def _rtk_cargo(ctx: ToolContext, *args: str) -> str:
    """Run cargo command through RTK."""
    return _run_rtk_command(ctx, "cargo", list(args))


def _rtk_pytest(ctx: ToolContext, *args: str) -> str:
    """Run pytest command through RTK."""
    return _run_rtk_command(ctx, "pytest", list(args))


def _rtk_npm(ctx: ToolContext, *args: str) -> str:
    """Run npm command through RTK."""
    return _run_rtk_command(ctx, "npm", list(args))


def _rtk_docker(ctx: ToolContext, *args: str) -> str:
    """Run docker command through RTK."""
    return _run_rtk_command(ctx, "docker", list(args))


def _rtk_read(ctx: ToolContext, file_path: str, *args: str) -> str:
    """Run rtk read command for efficient file reading."""
    cmd_args = [file_path] + list(args)
    return _run_rtk_command(ctx, "read", cmd_args)


def _rtk_smart(ctx: ToolContext, file_path: str) -> str:
    """Run rtk smart command for 2-line code summary."""
    return _run_rtk_command(ctx, "smart", [file_path])


# Tool schema for the registry
RTK_TOOL_SCHEMA = {
    "name": "rtk_wrapper",
    "description": "Execute commands through RTK (Rust Token Killer) for 60-90% token reduction",
    "input_schema": {
        "type": "object",
        "properties": {
            "command": {
                "type": "string",
                "description": "Base command to run (git, ls, find, grep, cargo, pytest, npm, docker, read, smart)",
                "enum": ["git", "ls", "find", "grep", "cargo", "pytest", "npm", "docker", "read", "smart"],
            },
            "args": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Arguments for the command",
                "default": [],
            },
            "file_path": {
                "type": "string",
                "description": "File path for read/smart commands",
            },
            "timeout": {
                "type": "integer",
                "description": "Timeout in seconds",
                "default": 120,
            },
        },
        "required": ["command"],
        "dependencies": {
            "read": ["file_path"],
            "smart": ["file_path"],
        },
    },
}


def register_tools(register_func):
    """Register RTK wrapper tools with the provided register function."""
    # Register the main RTK wrapper
    register_func(
        name="rtk_wrapper",
        desc=RTK_TOOL_SCHEMA["description"],
        input_schema=RTK_TOOL_SCHEMA["input_schema"],
        handler=_rtk_wrapper_handler,
    )

    # Register convenience tools for common operations
    register_func(
        name="rtk_git",
        desc="Run git command through RTK for token-efficient output",
        input_schema={
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Git command arguments",
                    "default": [],
                },
            },
        },
        handler=_rtk_git,
    )

    register_func(
        name="rtk_ls",
        desc="Run ls command through RTK for token-efficient output",
        input_schema={
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ls command arguments",
                    "default": [],
                },
            },
        },
        handler=_rtk_ls,
    )

    register_func(
        name="rtk_grep",
        desc="Run grep command through RTK for token-efficient output",
        input_schema={
            "type": "object",
            "properties": {
                "args": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Grep command arguments",
                    "default": [],
                },
            },
        },
        handler=_rtk_grep,
    )


def _rtk_wrapper_handler(ctx: ToolContext, **kwargs: Any) -> str:
    """Main handler for the RTK wrapper tool."""
    command = kwargs.get("command")
    args = kwargs.get("args", [])
    file_path = kwargs.get("file_path")
    timeout = kwargs.get("timeout", 120)

    # Handle special commands that need file_path
    if command == "read":
        if not file_path:
            return "⚠️ ERROR: file_path required for read command"
        return _rtk_read(ctx, file_path, *args)

    if command == "smart":
        if not file_path:
            return "⚠️ ERROR: file_path required for smart command"
        return _rtk_smart(ctx, file_path)

    # Handle standard commands
    command_map = {
        "git": _rtk_git,
        "ls": _rtk_ls,
        "find": _rtk_find,
        "grep": _rtk_grep,
        "cargo": _rtk_cargo,
        "pytest": _rtk_pytest,
        "npm": _rtk_npm,
        "docker": _rtk_docker,
    }

    handler = command_map.get(command)
    if handler:
        return handler(ctx, *args)

    return f"⚠️ ERROR: Unsupported command '{command}'"
