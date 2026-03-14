#!/usr/bin/env python3
"""
Git Orchestrator - Centralized Git management for Ouroboros
Handles SHA sync, PR creation, branch management, and auto-cleanup
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from instance_id import InstanceIdentifier

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - GIT_ORCH - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/git_orchestrator.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__)


class GitLock:
    """Distributed lock for Git operations."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.lock_file = repo_dir / ".git" / "lock.json"
        
    def acquire(self, operation: str, timeout: int = 30) -> bool:
        """Acquire lock for operation."""
        start = time.time()
        
        while time.time() - start < timeout:
            if not self.lock_file.exists():
                # Create lock file
                lock_data = {
                    "instance_id": self.get_instance_id(),
                    "operation": operation,
                    "acquired_at": datetime.now().isoformat(),
                    "expires_at": (datetime.now() + timedelta(seconds=30)).isoformat()
                }
                
                self.lock_file.write_text(json.dumps(lock_data))
                return True
            
            # Check if lock expired
            try:
                lock_data = json.loads(self.lock_file.read_text())
                expires = datetime.fromisoformat(lock_data["expires_at"])
                
                if datetime.now() > expires:
                    self.lock_file.unlink()
                    continue
                    
            except:
                self.lock_file.unlink()
                continue
            
            time.sleep(1)
        
        return False
    
    def release(self):
        """Release lock."""
        if self.lock_file.exists():
            self.lock_file.unlink()
    
    def get_instance_id(self) -> str:
        """Get current instance ID."""
        try:
            identifier = InstanceIdentifier()
            return identifier.get_id()
        except:
            return "unknown"


class SHAOrchestrator:
    """Manages SHA synchronization across instances."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.instance_id = self._get_instance_id()
        
    def _get_instance_id(self) -> str:
        """Get unique instance ID."""
        try:
            identifier = InstanceIdentifier()
            return identifier.get_id()
        except:
            return "unknown"
    
    def get_current_sha(self) -> str:
        """Get current git HEAD."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout.strip()
        except:
            return ""
    
    def sync_sha(self) -> bool:
        """Sync SHA with orchestrator."""
        current_sha = self.get_current_sha()
        
        # Update state.json
        state_file = Path.home() / ".ouroboros" / "state" / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                data["current_sha"] = current_sha
                data["last_sha_sync"] = datetime.now().isoformat()
                state_file.write_text(json.dumps(data, indent=2))
                log.info(f"Updated state.json with SHA: {current_sha[:8]}")
                return True
            except Exception as e:
                log.error(f"Failed to update state.json: {e}")
                return False
        
        return False


class BranchController:
    """Controls branch usage based on operation type."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        
    def get_branch_for_operation(self, operation: str) -> str:
        """Get appropriate branch for operation."""
        branches = {
            "telegram_message": "dev",
            "major_feature": "feature/auto",
            "bug_fix": "dev",
            "model_update": "dev",
            "identity_update": "dev",
            "scratchpad_update": "dev",
        }
        
        return branches.get(operation, "dev")
    
    def ensure_branch_ready(self, branch: str):
        """Ensure branch is ready for work."""
        # Check if branch exists
        result = subprocess.run(
            ["git", "branch", "--list", branch],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        if not result.stdout.strip():
            # Create branch
            subprocess.run(
                ["git", "checkout", "-b", branch],
                cwd=self.repo_dir,
                check=True
            )
        else:
            # Switch to branch
            subprocess.run(
                ["git", "checkout", branch],
                cwd=self.repo_dir,
                check=True
            )


class PRManager:
    """Manages Pull Requests."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.gh_token = os.environ.get("GITHUB_TOKEN")
        self.repo_owner = os.environ.get("GITHUB_USER", "josolinap")
        self.repo_name = os.environ.get("GITHUB_REPO", "jo")
    
    def should_use_pr(self, operation: dict) -> bool:
        """Determine if operation should use PR."""
        op_type = operation.get("type", "")
        files_changed = operation.get("files_changed", [])
        
        # Use PR for major features
        if "feature" in op_type.lower():
            return True
        
        # Use PR if many files changed
        if len(files_changed) > 5:
            return True
        
        return False
    
    def create_pr_branch(self, feature_name: str) -> str:
        """Create feature branch for PR."""
        branch_name = f"feature/{feature_name}-{int(time.time())}"
        
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.repo_dir,
            check=True
        )
        
        log.info(f"Created PR branch: {branch_name}")
        return branch_name
    
    def create_pr(self, branch_name: str, title: str, body: str) -> Optional[str]:
        """Create PR on GitHub using gh CLI."""
        if not self.gh_token:
            log.warning("GitHub token not configured")
            return None
        
        try:
            # Push branch
            subprocess.run(
                ["git", "push", "origin", branch_name],
                cwd=self.repo_dir,
                check=True,
                capture_output=True
            )
            
            # Create PR using gh CLI
            result = subprocess.run(
                [
                    "gh", "pr", "create",
                    "--title", title,
                    "--body", body,
                    "--head", branch_name,
                    "--base", "dev",
                    "--web"  # Don't open browser, just get URL
                ],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            pr_url = result.stdout.strip()
            log.info(f"Created PR: {title}")
            log.info(f"PR URL: {pr_url}")
            return pr_url
            
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to create PR: {e.stderr}")
            return None
        except Exception as e:
            log.error(f"PR creation error: {e}")
            return None
    
    def list_prs(self, state: str = "open") -> List[Dict]:
        """List PRs using gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "pr", "list", "--state", state, "--json", "number,title,author,url"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            import json
            return json.loads(result.stdout)
        except Exception as e:
            log.error(f"Failed to list PRs: {e}")
            return []
    
    def check_pr_status(self, pr_number: int) -> Optional[Dict]:
        """Check PR status using gh CLI."""
        try:
            result = subprocess.run(
                ["gh", "pr", "view", str(pr_number), "--json", "state,mergeable,url"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            import json
            return json.loads(result.stdout)
        except Exception as e:
            log.error(f"Failed to check PR status: {e}")
            return None


class CleanupService:
    """Automatic cleanup of git artifacts."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
    
    def cleanup_old_branches(self, days_old: int = 7):
        """Remove old merged branches."""
        try:
            result = subprocess.run(
                ["git", "branch", "--merged", "origin/dev"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            branches = result.stdout.strip().split('\n')
            
            for branch in branches:
                branch = branch.strip().replace("* ", "")
                if branch and branch not in ["dev", "main", "master"]:
                    if self.is_branch_old(branch, days_old):
                        log.info(f"Removing old branch: {branch}")
                        subprocess.run(
                            ["git", "branch", "-d", branch],
                            cwd=self.repo_dir,
                            check=False
                        )
        except Exception as e:
            log.error(f"Branch cleanup error: {e}")
    
    def is_branch_old(self, branch: str, days_old: int) -> bool:
        """Check if branch is old enough to remove."""
        try:
            result = subprocess.run(
                ["git", "log", f"{branch}...origin/dev", "--oneline"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return len(result.stdout.strip()) == 0
        except:
            return False
    
    def cleanup_stashes(self, max_stashes: int = 5):
        """Clean up old stashes."""
        try:
            result = subprocess.run(
                ["git", "stash", "list"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            stashes = result.stdout.strip().split('\n')
            
            if len(stashes) > max_stashes:
                for stash in stashes[max_stashes:]:
                    if stash:
                        stash_id = stash.split(':')[0]
                        subprocess.run(
                            ["git", "stash", "drop", stash_id],
                            cwd=self.repo_dir,
                            check=False
                        )
        except Exception as e:
            log.error(f"Stash cleanup error: {e}")
    
    def run_cleanup(self):
        """Run all cleanup tasks."""
        log.info("Starting cleanup...")
        
        self.cleanup_old_branches(days_old=7)
        self.cleanup_stashes(max_stashes=5)
        
        log.info("Cleanup complete")


class GitOrchestrator:
    """Central orchestrator for all Git operations."""
    
    def __init__(self, repo_dir: Path, drive_root: Path):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        
        # Initialize components
        self.sha_orchestrator = SHAOrchestrator(repo_dir)
        self.pr_manager = PRManager(repo_dir)
        self.branch_controller = BranchController(repo_dir)
        self.cleanup_service = CleanupService(repo_dir)
        self.lock = GitLock(repo_dir)
        
        # Instance info
        self.instance_id = self.sha_orchestrator.instance_id
        
        log.info(f"GitOrchestrator initialized (instance: {self.instance_id[:8]})")
    
    async def continuous_sync(self):
        """Continuous synchronization loop."""
        while True:
            try:
                # Sync SHA
                self.sha_orchestrator.sync_sha()
                
                # Run cleanup (hourly)
                if datetime.now().minute == 0:
                    self.cleanup_service.run_cleanup()
                
                await asyncio.sleep(60)
                
            except Exception as e:
                log.error(f"Sync error: {e}")
                await asyncio.sleep(10)
    
    def process_operation(self, operation: dict) -> dict:
        """Process an operation with appropriate workflow."""
        op_type = operation.get("type", "general")
        
        log.info(f"Processing operation: {op_type}")
        
        # Get appropriate branch
        branch = self.branch_controller.get_branch_for_operation(op_type)
        self.branch_controller.ensure_branch_ready(branch)
        
        # Determine if PR is needed
        if self.pr_manager.should_use_pr(operation):
            return self.process_with_pr(operation, branch)
        else:
            return self.process_on_branch(operation, branch)
    
    def process_on_branch(self, operation: dict, branch: str) -> dict:
        """Process operation directly on branch."""
        # Acquire lock
        if not self.lock.acquire(operation.get("type", "general")):
            log.warning("Could not acquire lock, operation queued")
            return {"status": "queued"}
        
        try:
            # Execute operation (placeholder)
            result = {"result": "operation_executed"}
            
            # Commit with instance ID
            self.commit_with_instance_id(result, operation)
            
            # Sync to remote
            self.sync_to_remote(branch)
            
            log.info(f"Operation completed on {branch}")
            
            return {
                "status": "completed",
                "branch": branch,
                "instance_id": self.instance_id
            }
            
        finally:
            self.lock.release()
    
    def process_with_pr(self, operation: dict, base_branch: str) -> dict:
        """Process operation via PR."""
        # Create feature branch
        feature_name = operation.get("feature_name", "auto-feature")
        branch = self.pr_manager.create_pr_branch(feature_name)
        
        # Execute operation
        result = {"result": "feature_executed"}
        
        # Commit changes
        self.commit_with_instance_id(result, operation)
        
        # Create PR
        pr_url = self.pr_manager.create_pr(
            branch_name=branch,
            title=operation.get("title", f"Feature: {feature_name}"),
            body=operation.get("description", "Auto-generated PR")
        )
        
        # Switch back to dev
        subprocess.run(
            ["git", "checkout", "dev"],
            cwd=self.repo_dir,
            check=True
        )
        
        return {
            "status": "pr_created",
            "branch": branch,
            "pr_url": pr_url,
            "instance_id": self.instance_id
        }
    
    def commit_with_instance_id(self, result: dict, operation: dict):
        """Commit changes with instance ID."""
        message = f"[{self.instance_id[:8]}] {operation.get('type', 'auto')}"
        
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_dir,
            check=True
        )
        
        # Check if there are changes to commit
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        if result.stdout.strip():
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_dir,
                check=True
            )
            log.info(f"Committed: {message}")
        else:
            log.info("No changes to commit")
    
    def sync_to_remote(self, branch: str = "dev"):
        """Sync changes to remote."""
        try:
            # Pull with rebase
            subprocess.run(
                ["git", "pull", "--rebase", "origin", branch],
                cwd=self.repo_dir,
                check=True
            )
            
            # Push
            subprocess.run(
                ["git", "push", "origin", branch],
                cwd=self.repo_dir,
                check=True
            )
            
            log.info(f"Synced to remote {branch}")
            
        except subprocess.CalledProcessError as e:
            log.error(f"Sync failed: {e}")
            # Try to resolve
            self.resolve_sync_conflict(branch)
    
    def resolve_sync_conflict(self, branch: str):
        """Resolve sync conflicts."""
        log.info("Attempting to resolve sync conflict...")
        
        # Stash local changes
        subprocess.run(
            ["git", "stash", "push", "-m", "sync-conflict-resolution"],
            cwd=self.repo_dir,
            check=False
        )
        
        # Pull latest
        subprocess.run(
            ["git", "pull", "--rebase", "origin", branch],
            cwd=self.repo_dir,
            check=False
        )
        
        # Apply stashed changes
        subprocess.run(
            ["git", "stash", "pop"],
            cwd=self.repo_dir,
            check=False
        )


if __name__ == "__main__":
    import asyncio
    
    async def main():
        orchestrator = GitOrchestrator(
            repo_dir=Path("/root/jo-project"),
            drive_root=Path.home() / ".ouroboros"
        )
        
        # Test operation
        operation = {
            "type": "telegram_message",
            "content": "Test message"
        }
        
        result = orchestrator.process_operation(operation)
        print(f"Result: {result}")
    
    asyncio.run(main())