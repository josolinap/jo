"""Shell tools: run_shell, code_edit, code_edit_lines."""

from __future__ import annotations

import json
import logging
import os
import pathlib
import shlex
import shutil
import subprocess
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import utc_now_iso, run_cmd, append_jsonl, truncate_for_log, safe_relpath

log = logging.getLogger(__name__)


def _check_shell_for_protected_files(cmd: List[str]) -> str:
    """Check if a shell command might modify protected files.

    Returns warning message if protected files detected, empty string otherwise.
    Does NOT block execution - only logs warning.
    """
    if not cmd:
        return ""

    # Read .jo_protected file
    protected_list = []
    try:
        protected_path = pathlib.Path(".jo_protected")
        if protected_path.exists():
            protected_list = [
                p.strip().lower()
                for p in protected_path.read_text(encoding="utf-8").splitlines()
                if p.strip() and not p.startswith("#")
            ]
    except Exception:
        pass

    if not protected_list:
        return ""

    # Check each token in command for protected file references
    protected_files = []
    for token in cmd:
        token_lower = str(token).lower().replace("\\", "/").strip("./")
        for protected in protected_list:
            protected_normalized = protected.replace("\\", "/").strip("./")
            if token_lower == protected_normalized or token_lower.endswith("/" + protected_normalized):
                protected_files.append(str(token))

    if protected_files:
        files_str = ", ".join(protected_files[:3])
        if len(protected_files) > 3:
            files_str += f" (+{len(protected_files) - 3} more)"
        return f"⚠️ WARNING: run_shell may modify protected file(s): {files_str}. Proceed with caution."

    return ""


def _run_shell(ctx: ToolContext, cmd, cwd: str = "") -> str:
    # Recover from LLM sending cmd as JSON string instead of list
    if isinstance(cmd, str):
        raw_cmd = cmd
        warning = "run_shell_cmd_string"
        try:
            parsed = json.loads(cmd)
            if isinstance(parsed, list):
                cmd = parsed
                warning = "run_shell_cmd_string_json_list_recovered"
            elif isinstance(parsed, str):
                try:
                    cmd = shlex.split(parsed)
                except ValueError:
                    cmd = parsed.split()
                warning = "run_shell_cmd_string_json_string_split"
            else:
                try:
                    cmd = shlex.split(cmd)
                except ValueError:
                    cmd = cmd.split()
                warning = "run_shell_cmd_string_json_non_list_split"
        except Exception:
            try:
                cmd = shlex.split(cmd)
            except ValueError:
                cmd = cmd.split()
            warning = "run_shell_cmd_string_split_fallback"

        try:
            append_jsonl(
                ctx.drive_logs() / "events.jsonl",
                {
                    "ts": utc_now_iso(),
                    "type": "tool_warning",
                    "tool": "run_shell",
                    "warning": warning,
                    "cmd_preview": truncate_for_log(raw_cmd, 500),
                },
            )
        except Exception:
            log.debug("Failed to log run_shell warning to events.jsonl", exc_info=True)
            pass

    if not isinstance(cmd, list):
        return "⚠️ SHELL_ARG_ERROR: cmd must be a list of strings."
    cmd = [str(x) for x in cmd]

    # Check for protected file modifications (warning only, not blocking)
    prot_warning = _check_shell_for_protected_files(cmd)
    if prot_warning:
        log.warning(prot_warning)
        ctx.emit_progress_fn(prot_warning)

    work_dir = ctx.repo_dir
    if cwd and cwd.strip() not in ("", ".", "./"):
        candidate = (ctx.repo_dir / cwd).resolve()
        if candidate.exists() and candidate.is_dir():
            work_dir = candidate

    try:
        res = subprocess.run(
            cmd,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=120,
        )
        out = res.stdout + ("\n--- STDERR ---\n" + res.stderr if res.stderr else "")
        if len(out) > 50000:
            out = out[:25000] + "\n...(truncated)...\n" + out[-25000:]
        prefix = f"exit_code={res.returncode}\n"
        return prefix + out
    except subprocess.TimeoutExpired:
        return "⚠️ TIMEOUT: command exceeded 120s."
    except Exception as e:
        return f"⚠️ SHELL_ERROR: {e}"


def _run_claude_cli(work_dir: str, prompt: str, env: dict) -> subprocess.CompletedProcess:
    """Run Claude CLI with permission-mode fallback."""
    claude_bin = shutil.which("claude")
    cmd = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--max-turns",
        "12",
        "--tools",
        "Read,Edit,Grep,Glob",
    ]

    # Try --permission-mode first, fallback to --dangerously-skip-permissions
    perm_mode = os.environ.get("OUROBOROS_CLAUDE_CODE_PERMISSION_MODE", "bypassPermissions").strip()
    primary_cmd = cmd + ["--permission-mode", perm_mode]
    legacy_cmd = cmd + ["--dangerously-skip-permissions"]

    res = subprocess.run(
        primary_cmd,
        cwd=work_dir,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
    )

    if res.returncode != 0:
        combined = ((res.stdout or "") + "\n" + (res.stderr or "")).lower()
        if "--permission-mode" in combined and any(
            m in combined for m in ("unknown option", "unknown argument", "unrecognized option", "unexpected argument")
        ):
            res = subprocess.run(
                legacy_cmd,
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=300,
                env=env,
            )

    return res


def _is_protected_file(path: str) -> bool:
    """Check if a file is protected and cannot be modified without approval."""
    protected_file = pathlib.Path(".jo_protected")
    if not protected_file.exists():
        return False

    try:
        protected_list = protected_file.read_text(encoding="utf-8").splitlines()
        # Normalize path for comparison (case-insensitive for Windows compatibility)
        normalized_path = path.replace("\\", "/").strip("./").lower()
        for protected in protected_list:
            protected = protected.strip()
            if protected and not protected.startswith("#"):
                protected_normalized = protected.replace("\\", "/").strip("./").lower()
                # Exact match
                if normalized_path == protected_normalized:
                    return True
                # Directory prefix match (e.g., "ouroboros/" protects "ouroboros/loop.py")
                if protected_normalized.endswith("/") and normalized_path.startswith(protected_normalized):
                    return True
    except Exception:
        pass
    return False


def _code_edit(ctx: ToolContext, path: str, content: str, commit_message: str) -> str:
    """Edit a file directly using Jo's native code editing.

    This is Jo's primary code editing tool. It writes file content directly and commits the change.

    Args:
        path: File path relative to repo root
        content: New file content
        commit_message: Git commit message

    Returns:
        Success/error message with details
    """
    from ouroboros.tools.git import _repo_write_commit

    ctx.emit_progress_fn(f"Editing {path}...")

    # Check if file is protected
    if _is_protected_file(path):
        return f"⚠️ PROTECTED_FILE: {path} is protected and cannot be modified without human approval. Ask the creator first."

    # Validate path is within repo
    try:
        safe_path = safe_relpath(path)
    except ValueError as e:
        return f"⚠️ PATH_ERROR: {e}"

    # Validate commit message
    if not commit_message or not commit_message.strip():
        return "⚠️ ERROR: commit_message must be non-empty."

    # Use the existing repo_write_commit function
    return _repo_write_commit(ctx, path, content, commit_message)


def _code_edit_lines(ctx: ToolContext, path: str, old_lines: str, new_lines: str, commit_message: str) -> str:
    """Edit specific lines in a file.

    This is a line-based editor that replaces old_lines with new_lines.
    Useful for small, targeted changes without rewriting entire files.

    Args:
        path: File path relative to repo root
        old_lines: Lines to find and replace
        new_lines: Replacement lines
        commit_message: Git commit message

    Returns:
        Success/error message with details
    """
    from ouroboros.tools.git import _repo_write_commit

    ctx.emit_progress_fn(f"Editing lines in {path}...")

    # Check if file is protected
    if _is_protected_file(path):
        return f"⚠️ PROTECTED_FILE: {path} is protected and cannot be modified without human approval. Ask the creator first."

    # Validate path
    try:
        safe_path = safe_relpath(path)
    except ValueError as e:
        return f"⚠️ PATH_ERROR: {e}"

    # Read current file
    file_path = ctx.repo_path(path)
    if not file_path.exists():
        return f"⚠️ FILE_NOT_FOUND: {path}"

    try:
        current_content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return f"⚠️ FILE_READ_ERROR: {e}"

    # Find and replace
    if old_lines not in current_content:
        return f"⚠️ PATTERN_NOT_FOUND: Could not find the specified lines in {path}"

    # Replace only the first occurrence
    new_content = current_content.replace(old_lines, new_lines, 1)

    # Check if content actually changed
    if new_content == current_content:
        return f"⚠️ NO_CHANGE: The specified lines match existing content in {path}"

    # Write and commit
    return _repo_write_commit(ctx, path, new_content, commit_message)


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "run_shell",
            {
                "name": "run_shell",
                "description": "Run a shell command (list of args) inside the repo. Returns stdout+stderr.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "cmd": {"type": "array", "items": {"type": "string"}},
                        "cwd": {"type": "string", "default": ""},
                    },
                    "required": ["cmd"],
                },
            },
            _run_shell,
            is_code_tool=True,
        ),
        ToolEntry(
            "code_edit",
            {
                "name": "code_edit",
                "description": "Edit a file directly using Jo's native code editing. Write entire file content and commit.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to repo root"},
                        "content": {"type": "string", "description": "New file content"},
                        "commit_message": {"type": "string", "description": "Git commit message"},
                    },
                    "required": ["path", "content", "commit_message"],
                },
            },
            _code_edit,
            is_code_tool=True,
        ),
        ToolEntry(
            "code_edit_lines",
            {
                "name": "code_edit_lines",
                "description": "Edit specific lines in a file (Claude-free). Replace old_lines with new_lines for targeted changes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "File path relative to repo root"},
                        "old_lines": {"type": "string", "description": "Lines to find and replace"},
                        "new_lines": {"type": "string", "description": "Replacement lines"},
                        "commit_message": {"type": "string", "description": "Git commit message"},
                    },
                    "required": ["path", "old_lines", "new_lines", "commit_message"],
                },
            },
            _code_edit_lines,
            is_code_tool=True,
        ),
    ]
