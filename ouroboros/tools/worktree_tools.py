import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any, Dict, List
from ouroboros.tools.registry import ToolEntry

def _run_git(cmd: List[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git"] + cmd, cwd=str(cwd), capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Git error: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()

def _handle_enter_worktree(ctx: Any, branch_name: str = "", **kwargs: Any) -> str:
    # Ensure they aren't already in a secondary worktree
    if getattr(ctx, "in_worktree_experiment", False):
        return "⚠️ You are already actively in a worktree experiment. Call exit_worktree first."
    
    repo_dir = ctx.repo_dir
    parent_dir = repo_dir.parent
    
    if not branch_name:
        uid = str(uuid.uuid4())[:8]
        branch_name = f"experiment-{uid}"
        
    worktree_path = parent_dir / f"{repo_dir.name}-{branch_name}"
    
    try:
        # Check if the repo is clean
        status = _run_git(["status", "--porcelain"], cwd=repo_dir)
        if status:
            return "⚠️ Repository is not clean. Please commit or stash your changes before creating a worktree."
            
        # Create worktree
        _run_git(["worktree", "add", "-b", branch_name, str(worktree_path)], cwd=repo_dir)
        
        # Save original states
        ctx.original_repo_dir = ctx.repo_dir
        ctx.in_worktree_experiment = True
        ctx.worktree_branch = branch_name
        ctx.repo_dir = worktree_path
        
        return (f"Successfully created and entered worktree at {worktree_path} on new branch '{branch_name}'.\n"
                f"Your working directory is now isolated. You can experiment safely.\n"
                f"When finished, call exit_worktree with action='merge' to merge your changes back, "
                f"or action='discard' to abort.")
    except Exception as e:
        return f"⚠️ Failed to create worktree: {e}"

def _handle_exit_worktree(ctx: Any, action: str = "discard", **kwargs: Any) -> str:
    if not getattr(ctx, "in_worktree_experiment", False):
        return "⚠️ You are not currently in a worktree experiment."
        
    if action not in ("merge", "discard"):
        return "⚠️ Action must be either 'merge' or 'discard'."
        
    worktree_path = ctx.repo_dir
    original_repo_dir = ctx.original_repo_dir
    branch_name = ctx.worktree_branch
    
    try:
        # First commit any outstanding changes in the worktree just in case
        try:
            _run_git(["add", "."], cwd=worktree_path)
            _run_git(["commit", "-m", "Temporary commit before exiting worktree"], cwd=worktree_path)
        except Exception:
            pass # might just be clean

        # reset context immediately to go back to original repo for further commands
        ctx.repo_dir = original_repo_dir
        ctx.in_worktree_experiment = False
        del ctx.original_repo_dir
        del ctx.worktree_branch
        
        # Remove worktree to free it from git's lock
        _run_git(["worktree", "remove", "--force", str(worktree_path)], cwd=original_repo_dir)
        
        msg = f"Worktree removed. Back to original repo directory."
        
        if action == "merge":
            try:
                _run_git(["merge", branch_name, "--no-ff", "-m", f"Merge experiment branch {branch_name}"], cwd=original_repo_dir)
                msg += f"\nSuccessfully merged branch '{branch_name}' into current."
            except Exception as e:
                msg += f"\n⚠️ Error merging branch '{branch_name}': {e}. The branch still exists if you need to merge it manually."
        
        if action == "discard":
            try:
                _run_git(["branch", "-D", branch_name], cwd=original_repo_dir)
                msg += f"\nDiscarded and deleted branch '{branch_name}'."
            except Exception as e:
                msg += f"\n⚠️ Failed to delete branch '{branch_name}': {e}"
                
        # Clean up directory if it's still there
        if worktree_path.exists():
            shutil.rmtree(worktree_path, ignore_errors=True)
            
        return msg
        
    except Exception as e:
        return f"⚠️ Failed to exit worktree: {e}"

def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            name="enter_worktree",
            schema={
                "name": "enter_worktree",
                "description": "Create an isolated git worktree and switch the agent's context to it. Useful for experimenting with complex code securely.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "branch_name": {
                            "type": "string",
                            "description": "Optional branch name for the experiment. If empty, a random one is generated."
                        }
                    },
                    "required": []
                }
            },
            handler=_handle_enter_worktree,
        ),
        ToolEntry(
            name="exit_worktree",
            schema={
                "name": "exit_worktree",
                "description": "Exit the current isolated worktree environment.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["merge", "discard"],
                            "description": "Whether to 'merge' the experimental changes back into the main branch, or 'discard' them."
                        }
                    },
                    "required": ["action"]
                }
            },
            handler=_handle_exit_worktree,
        ),
    ]
