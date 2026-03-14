"""
Git State Manager for Conflict-Resistant Operations
"""

import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, List, Dict
import json

log = logging.getLogger(__name__)


class GitStateManager:
    """Manages git state with conflict resolution."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.conflict_dir = repo_dir / ".git" / "conflicts"
        self.conflict_dir.mkdir(exist_ok=True)
    
    def get_clean_state(self) -> bool:
        """Check if working directory is clean."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        return len(result.stdout.strip()) == 0
    
    def stash_changes(self, message: str = "auto-stash") -> bool:
        """Stash local changes safely."""
        try:
            subprocess.run(
                ["git", "stash", "push", "-m", message],
                cwd=self.repo_dir,
                check=True,
                capture_output=True
            )
            log.info(f"Stashed changes: {message}")
            return True
        except subprocess.CalledProcessError:
            log.warning("Failed to stash changes")
            return False
    
    def pull_with_rebase(self, branch: str = "dev") -> Tuple[bool, str]:
        """Pull changes with automatic rebase."""
        try:
            # First, ensure we're on the right branch
            subprocess.run(
                ["git", "checkout", branch],
                cwd=self.repo_dir,
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Pull with rebase
            result = subprocess.run(
                ["git", "pull", "--rebase", "origin", branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True,
                timeout=30
            )
            
            log.info(f"Successfully pulled changes")
            return True, result.stdout
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            log.error(f"Pull failed: {error_msg}")
            
            # Check if there's a rebase conflict
            if "conflict" in error_msg.lower():
                return self.handle_rebase_conflict()
            
            return False, error_msg
        except subprocess.TimeoutExpired:
            log.error("Pull timed out")
            return False, "Timeout"
    
    def handle_rebase_conflict(self) -> Tuple[bool, str]:
        """Handle rebase conflict automatically."""
        log.info("Rebase conflict detected, attempting resolution...")
        
        try:
            # Get conflict files
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=U"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            )
            
            conflict_files = result.stdout.strip().split('\n')
            log.info(f"Conflict files: {conflict_files}")
            
            # Abort rebase
            subprocess.run(
                ["git", "rebase", "--abort"],
                cwd=self.repo_dir,
                check=True
            )
            
            # Stash current changes
            self.stash_changes("conflict-resolution-stash")
            
            # Try pull again
            return self.pull_with_rebase()
            
        except Exception as e:
            log.error(f"Failed to handle conflict: {e}")
            return False, str(e)
    
    def push_changes(self, branch: str = "dev", force: bool = False) -> Tuple[bool, str]:
        """Push changes with conflict handling."""
        try:
            cmd = ["git", "push"]
            if force:
                cmd.append("--force")
            
            cmd.extend(["origin", branch])
            
            result = subprocess.run(
                cmd,
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            log.info(f"Successfully pushed changes")
            return True, result.stdout
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            log.error(f"Push failed: {error_msg}")
            
            if "non-fast-forward" in error_msg or "rejected" in error_msg:
                return self.handle_push_rejection(branch)
            
            return False, error_msg
    
    def handle_push_rejection(self, branch: str) -> Tuple[bool, str]:
        """Handle push rejection by pulling and retrying."""
        log.info("Push rejected, pulling latest changes...")
        
        # Pull with rebase
        success, message = self.pull_with_rebase(branch)
        if not success:
            return False, f"Failed to pull after push rejection: {message}"
        
        # Try pushing again
        return self.push_changes(branch)
    
    def get_conflict_status(self) -> dict:
        """Get current conflict status."""
        status = {
            "has_conflicts": False,
            "conflict_files": [],
            "rebase_in_progress": False,
            "stash_exists": False
        }
        
        # Check for rebase in progress
        if (self.repo_dir / ".git" / "rebase-apply").exists():
            status["rebase_in_progress"] = True
            status["has_conflicts"] = True
        
        # Check for conflict files
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            status["has_conflicts"] = True
            status["conflict_files"] = result.stdout.strip().split('\n')
        
        # Check for stashes
        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        status["stash_exists"] = len(result.stdout.strip()) > 0
        
        return status
    
    def get_local_changes(self) -> Dict[str, List[str]]:
        """Get all local changes (staged, unstaged, untracked)."""
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        changes = {
            "staged": [],
            "unstaged": [],
            "untracked": []
        }
        
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            
            status = line[:2].strip()
            file_path = line[3:]
            
            if status == "M":
                changes["staged"].append(file_path)
            elif status == " A":
                changes["untracked"].append(file_path)
            else:
                changes["unstaged"].append(file_path)
        
        return changes


if __name__ == "__main__":
    import sys
    repo_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    
    manager = GitStateManager(repo_dir)
    
    print("Git State Manager")
    print(f"Clean state: {manager.get_clean_state()}")
    print(f"Conflict status: {manager.get_conflict_status()}")
    print(f"Local changes: {manager.get_local_changes()}")