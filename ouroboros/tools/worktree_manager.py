"""Git worktree management for Jo.

Enables task isolation by creating temporary git worktrees.
Adapted from agent-orchestrator and aidevops patterns.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import List, Optional, Tuple

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.utils import utc_now_iso, append_jsonl

log = logging.getLogger(__name__)

def _run_git(ctx: ToolContext, args: List[str]) -> Tuple[int, str, str]:
    """Helper to run git commands in repo root."""
    res = subprocess.run(
        ["git"] + args,
        cwd=str(ctx.repo_dir),
        capture_output=True,
        text=True,
        timeout=60
    )
    return res.returncode, res.stdout, res.stderr

def _worktree_create(ctx: ToolContext, branch_name: str, path: Optional[str] = None) -> str:
    """Create a new git worktree for a branch."""
    if not path:
        # Create in .jo_worktrees/ directory
        worktree_root = ctx.repo_dir / ".jo_worktrees"
        worktree_root.mkdir(exist_ok=True)
        path = str(worktree_root / branch_name)
    
    ctx.emit_progress_fn(f"Creating worktree for {branch_name} at {path}...")
    
    # 1. Check if branch exists, if not create it
    rc, out, err = _run_git(ctx, ["branch", "--list", branch_name])
    if not out.strip():
        rc, out, err = _run_git(ctx, ["checkout", "-b", branch_name])
        if rc != 0:
            return f"⚠️ ERROR: Failed to create branch {branch_name}: {err}"
        # Go back to previous branch
        _run_git(ctx, ["checkout", "-"])

    # 2. Add worktree
    rc, out, err = _run_git(ctx, ["worktree", "add", path, branch_name])
    if rc != 0:
        return f"⚠️ ERROR: Failed to add worktree: {err}"
    
    return f"✅ SUCCESS: Worktree created for '{branch_name}' at {path}"

def _worktree_list(ctx: ToolContext) -> str:
    """List all active git worktrees."""
    rc, out, err = _run_git(ctx, ["worktree", "list"])
    if rc != 0:
        return f"⚠️ ERROR: Failed to list worktrees: {err}"
    return out

def _worktree_remove(ctx: ToolContext, path: str, force: bool = False) -> str:
    """Remove a git worktree."""
    args = ["worktree", "remove", path]
    if force:
        args.append("--force")
    
    rc, out, err = _run_git(ctx, args)
    if rc != 0:
        return f"⚠️ ERROR: Failed to remove worktree: {err}"
    
    # Try to cleanup directory if it still exists
    try:
        if os.path.exists(path):
            shutil.rmtree(path)
    except Exception:
        pass
        
    return f"✅ SUCCESS: Worktree at {path} removed"

def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "worktree_create",
            {
                "name": "worktree_create",
                "description": "Create a new git worktree for a specific branch. Use for task isolation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "branch_name": {"type": "string"},
                        "path": {"type": "string", "description": "Optional custom path for worktree"},
                    },
                    "required": ["branch_name"],
                },
            },
            _worktree_create,
            is_code_tool=True,
        ),
        ToolEntry(
            "worktree_list",
            {
                "name": "worktree_list",
                "description": "List all active git worktrees and their paths.",
                "parameters": {"type": "object", "properties": {}},
            },
            _worktree_list,
            is_code_tool=True,
        ),
        ToolEntry(
            "worktree_remove",
            {
                "name": "worktree_remove",
                "description": "Remove an existing git worktree by path.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "force": {"type": "boolean", "default": False},
                    },
                    "required": ["path"],
                },
            },
            _worktree_remove,
            is_code_tool=True,
        )
    ]
