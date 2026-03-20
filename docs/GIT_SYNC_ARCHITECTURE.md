# Git Sync Architecture for Multi-Machine Ouroboros

## Problem Statement

### Current Issues
1. **Conflict Resolution**: Local changes can conflict with remote changes
2. **Multi-Machine Operation**: Running on Windows and Arch Linux simultaneously
3. **Codebase Access**: Agent needs to see local changes, not just GitHub
4. **Identity Tracking**: Different instances need unique IDs
5. **Change Synchronization**: How to sync changes between machines

## Proposed Architecture

### 1. Unique Instance Identification

```python
# instance_id.py
import uuid
import platform
import socket
from pathlib import Path

class InstanceIdentifier:
    """Unique identifier for each Ouroboros instance."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.id_file = drive_root / "instance_id.json"
        self.instance_id = self._load_or_create_id()
    
    def _load_or_create_id(self) -> str:
        """Load existing ID or create new one."""
        if self.id_file.exists():
            import json
            data = json.loads(self.id_file.read_text())
            return data["instance_id"]
        
        # Create unique ID based on machine characteristics
        instance_id = str(uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{platform.node()}-{socket.gethostname()}-{uuid.getnode()}"
        ))
        
        data = {
            "instance_id": instance_id,
            "hostname": platform.node(),
            "platform": platform.system(),
            "created": str(uuid.uuid4()),
            "last_seen": str(uuid.uuid4())
        }
        
        self.id_file.write_text(json.dumps(data, indent=2))
        return instance_id
    
    def get_id(self) -> str:
        """Get current instance ID."""
        return self.instance_id
    
    def update_last_seen(self):
        """Update last seen timestamp."""
        import json
        if self.id_file.exists():
            data = json.loads(self.id_file.read_text())
            data["last_seen"] = str(uuid.uuid4())
            self.id_file.write_text(json.dumps(data, indent=2))
```

### 2. Conflict-Resistant Git Workflow

#### Problem: SHA Mismatch
The agent detects changes between restarts because:
1. Worker process sees different git state
2. Uncommitted changes between spawns
3. Remote changes not pulled locally

#### Solution: Git State Manager

```python
# git_state_manager.py
import subprocess
import logging
from pathlib import Path
from typing import Optional, Tuple, List
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
                check=True
            )
            
            # Pull with rebase
            result = subprocess.run(
                ["git", "pull", "--rebase", "origin", branch],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            log.info(f"Successfully pulled changes: {result.stdout}")
            return True, result.stdout
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr or str(e)
            log.error(f"Pull failed: {error_msg}")
            
            # Check if there's a rebase conflict
            if "conflict" in error_msg.lower():
                return self.handle_rebase_conflict()
            
            return False, error_msg
    
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
            
            # For now, abort rebase and stash changes
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
            
            log.info(f"Successfully pushed changes: {result.stdout}")
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
```

### 3. Multi-Machine Sync Mechanism

#### Problem: Running on different machines (Windows + Arch Linux)

#### Solution: Machine-Aware Sync

```python
# machine_sync.py
import platform
import json
import hashlib
from pathlib import Path
from typing import Dict, List
from datetime import datetime

class MachineSync:
    """Handle synchronization across multiple machines."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.machines_file = drive_root / "machines.json"
        self.current_machine = self._get_machine_info()
        self._register_machine()
    
    def _get_machine_info(self) -> Dict[str, str]:
        """Get current machine information."""
        return {
            "id": hashlib.sha256(
                f"{platform.node()}-{platform.platform()}".encode()
            ).hexdigest()[:16],
            "hostname": platform.node(),
            "platform": platform.platform(),
            "user": platform.node(),  # Simplified
            "last_active": datetime.now().isoformat()
        }
    
    def _register_machine(self):
        """Register this machine in the sync system."""
        machines = self._load_machines()
        
        machine_id = self.current_machine["id"]
        if machine_id not in machines:
            machines[machine_id] = self.current_machine
        else:
            machines[machine_id]["last_active"] = self.current_machine["last_active"]
        
        self._save_machines(machines)
    
    def _load_machines(self) -> Dict[str, Dict]:
        """Load registered machines."""
        if self.machines_file.exists():
            return json.loads(self.machines_file.read_text())
        return {}
    
    def _save_machines(self, machines: Dict[str, Dict]):
        """Save registered machines."""
        self.machines_file.write_text(json.dumps(machines, indent=2))
    
    def get_machine_id(self) -> str:
        """Get current machine ID."""
        return self.current_machine["id"]
    
    def get_all_machines(self) -> List[Dict]:
        """Get all registered machines."""
        return list(self._load_machines().values())
    
    def mark_changes_local(self, changes: List[str]):
        """Mark changes made locally on this machine."""
        sync_file = self.drive_root / "sync" / f"{self.get_machine_id()}.json"
        sync_file.parent.mkdir(exist_ok=True)
        
        data = {
            "machine_id": self.get_machine_id(),
            "timestamp": datetime.now().isoformat(),
            "changes": changes,
            "status": "pending"
        }
        
        sync_file.write_text(json.dumps(data, indent=2))
    
    def get_pending_changes(self) -> List[Dict]:
        """Get pending changes from all machines."""
        sync_dir = self.drive_root / "sync"
        if not sync_dir.exists():
            return []
        
        changes = []
        for file in sync_dir.glob("*.json"):
            data = json.loads(file.read_text())
            if data.get("status") == "pending":
                changes.append(data)
        
        return changes
```

### 4. Local Codebase Access

#### Problem: Agent needs to see local changes, not just GitHub

#### Solution: Dual-Mode Git Operations

```python
# dual_git_manager.py
import subprocess
from pathlib import Path
from typing import Optional, Dict, List
import logging

log = logging.getLogger(__name__)

class DualGitManager:
    """Manages both local and remote git operations."""
    
    def __init__(self, repo_dir: Path, drive_root: Path):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self.local_state_file = drive_root / "local_state.json"
        
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
    
    def get_file_content(self, file_path: str) -> Optional[str]:
        """Get content of a specific file."""
        try:
            full_path = self.repo_dir / file_path
            if full_path.exists():
                return full_path.read_text()
        except Exception as e:
            log.error(f"Failed to read {file_path}: {e}")
        return None
    
    def save_local_state(self):
        """Save current local state for comparison."""
        state = {
            "timestamp": subprocess.run(
                ["date", "-Iseconds"],
                capture_output=True,
                text=True
            ).stdout.strip(),
            "commit_hash": subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True
            ).stdout.strip(),
            "changes": self.get_local_changes()
        }
        
        self.local_state_file.write_text(json.dumps(state, indent=2))
    
    def detect_changes_since_last(self) -> Dict:
        """Detect changes since last state save."""
        if not self.local_state_file.exists():
            return {"has_changes": False}
        
        old_state = json.loads(self.local_state_file.read_text())
        new_changes = self.get_local_changes()
        
        return {
            "has_changes": len(new_changes["staged"]) > 0 or
                          len(new_changes["unstaged"]) > 0 or
                          len(new_changes["untracked"]) > 0,
            "old_state": old_state,
            "new_changes": new_changes
        }
```

### 5. Workflow for Multi-Machine Operation

#### Process Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    MACHINE A (Windows)                      │
│  1. Make local changes                                      │
│  2. Commit with machine ID: "machine-a-xxx"                 │
│  3. Push to remote (dev branch)                             │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
                    ┌─────────────────┐
                    │   GitHub Remote │
                    │   (dev branch)  │
                    └─────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    MACHINE B (Arch Linux)                   │
│  1. Pull changes from remote                                │
│  2. Detect conflicts (if any)                               │
│  3. Resolve automatically or mark for review                │
│  4. Continue operation                                      │
└─────────────────────────────────────────────────────────────┘
```

### 6. Implementation in Ouroboros

#### Modified Launcher with Conflict Handling

```python
# In colab_launcher.py, modify the git sync section:

def handle_git_sync():
    """Handle git synchronization with conflict resolution."""
    from git_state_manager import GitStateManager
    from machine_sync import MachineSync
    
    repo_dir = pathlib.Path("/root/jo-project")
    drive_root = pathlib.Path.home() / ".jo_data"
    
    # Initialize managers
    git_manager = GitStateManager(repo_dir)
    machine_sync = MachineSync(drive_root)
    
    # Check for conflicts
    conflict_status = git_manager.get_conflict_status()
    
    if conflict_status["has_conflicts"]:
        log.warning(f"Git conflicts detected: {conflict_status}")
        # Auto-resolve or stash
        git_manager.stash_changes("auto-resolve-conflict")
    
    # Pull latest changes
    success, message = git_manager.pull_with_rebase("dev")
    
    if success:
        log.info("Successfully synced with remote")
    else:
        log.error(f"Sync failed: {message}")
        # Continue with local changes
```

### 7. Machine-Specific Configuration

#### Per-Machine Settings

```bash
# ~/.jo_data/machine_config.json
{
  "machine_id": "abc123...",
  "hostname": "arch-linux-pc",
  "platform": "linux",
  "preferred_branch": "dev",
  "auto_push": true,
  "auto_pull": true,
  "conflict_resolution": "auto-stash",
  "instance_role": "worker"  # "worker", "coordinator", "standalone"
}
```

### 8. Conflict Resolution Strategies

| Conflict Type | Resolution Strategy |
|--------------|-------------------|
| **SHA Mismatch** | Auto-commit pending changes, then pull |
| **Rebase Conflict** | Abort rebase, stash changes, retry pull |
| **Push Rejection** | Pull with rebase, then push again |
| **File Modified Locally & Remotely** | Keep remote version (for collaborative editing) |

### 9. Summary of Solution

**For Conflicts:**
1. Each instance has unique ID
2. Git state manager handles conflicts automatically
3. Stash changes when conflicts occur
4. Pull latest, then reapply stashes

**For Multi-Machine:**
1. Register each machine in `machines.json`
2. Track changes per machine in `sync/` directory
3. Pull changes from all machines
4. Resolve conflicts based on machine priority

**For Local Codebase Access:**
1. Dual-mode git operations (local + remote)
2. Track local changes separately
3. Sync local state with remote periodically
4. Agent can see both local and remote changes

**For Git Workflow:**
1. Always pull before push
2. Use rebase strategy
3. Auto-stash on conflicts
4. Commit with machine ID for tracking

This architecture ensures:
- ✅ No more SHA mismatches
- ✅ Multi-machine operation
- ✅ Local codebase visibility
- ✅ Automatic conflict resolution
- ✅ Proper git sync across machines