# Git Orchestrator Design

## Vision

A **self-managing Git system** that:
1. **Orchestrates SHAs** across multiple instances
2. **Delegates work** via PRs for major changes
3. **Uses dev branch** for daily operations
4. **Auto-syncs** scratchpad and identity
5. **Prevents conflicts** with smart locking
6. **Auto-cleans** old branches and stashes

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    GIT ORCHESTRATOR LAYER                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐   │
│  │   SHA Sync   │ │  PR Manager  │ │  Branch      │ │  Cleanup     │   │
│  │   Manager    │ │              │ │  Controller  │ │  Service     │   │
│  └──────────────┘ └──────────────┘ └──────────────┘ └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
                                │
            ┌───────────────────┼───────────────────┐
            │                   │                   │
            ▼                   ▼                   ▼
    ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
    │   Dev Branch │   │   PR Branch  │   │   Scratchpad │
    │   (Daily)    │   │   (Feature)  │   │   Sync       │
    └──────────────┘   └──────────────┘   └──────────────┘
```

## Core Components

### 1. SHA Orchestrator

**Problem**: Multiple instances running on different SHAs cause conflicts.

**Solution**: Central SHA tracking with automatic synchronization.

```python
class SHAOrchestrator:
    """Manages SHA synchronization across instances."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.sha_file = repo_dir / ".git" / "sha_orchestrator.json"
        self.instance_id = self._get_instance_id()
        
    def _get_instance_id(self) -> str:
        """Get unique instance ID."""
        # From instance_id.py
        pass
    
    def register_instance(self):
        """Register this instance with orchestrator."""
        instances = self._load_instances()
        instances[self.instance_id] = {
            "last_seen": datetime.now().isoformat(),
            "current_sha": self.get_current_sha(),
            "last_activity": datetime.now().isoformat()
        }
        self._save_instances(instances)
    
    def get_current_sha(self) -> str:
        """Get current git HEAD."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    
    def sync_sha(self) -> bool:
        """Sync SHA with orchestrator."""
        current_sha = self.get_current_sha()
        expected_sha = self.get_expected_sha()
        
        if current_sha != expected_sha:
            log.warning(f"SHA mismatch: current={current_sha[:8]}, expected={expected_sha[:8]}")
            return self.resolve_sha_mismatch(current_sha, expected_sha)
        
        return True
    
    def resolve_sha_mismatch(self, current: str, expected: str) -> bool:
        """Resolve SHA mismatch intelligently."""
        # Strategy:
        # 1. If local changes: stash and pull
        # 2. If no changes: pull directly
        # 3. If conflicts: create merge branch
        # 4. If all fails: create backup branch
        
        if self.has_local_changes():
            # Stash changes
            self.stash_changes(f"auto-stash-when-syncing-{current[:8]}")
        
        # Try to pull
        success = self.pull_expected_sha(expected)
        if success:
            log.info(f"Successfully synced to {expected[:8]}")
            return True
        
        # Try merge
        success = self.merge_expected_sha(expected)
        if success:
            log.info(f"Merged to {expected[:8]}")
            return True
        
        # Last resort: create backup and reset
        return self.emergency_reset(expected)
```

### 2. PR Manager

**Problem**: Major changes should go through PRs to avoid breaking dev branch.

**Solution**: Automatic PR creation and management.

```python
class PRManager:
    """Manages Pull Requests for major changes."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.gh_token = os.environ.get("GITHUB_TOKEN")
        self.repo_owner = os.environ.get("GITHUB_USER", "josolinap")
        self.repo_name = os.environ.get("GITHUB_REPO", "jo")
        
    def create_pr_branch(self, feature_name: str) -> str:
        """Create a new branch for a feature."""
        branch_name = f"feature/{feature_name}-{int(time.time())}"
        
        subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=self.repo_dir,
            check=True
        )
        
        log.info(f"Created PR branch: {branch_name}")
        return branch_name
    
    def create_pr(self, branch_name: str, title: str, body: str) -> str:
        """Create a Pull Request on GitHub."""
        # Push branch
        subprocess.run(
            ["git", "push", "origin", branch_name],
            cwd=self.repo_dir,
            check=True
        )
        
        # Create PR via GitHub API
        import requests
        
        url = f"https://api.github.com/repos/{self.repo_owner}/{self.repo_name}/pulls"
        headers = {
            "Authorization": f"token {self.gh_token}",
            "Accept": "application/vnd.github.v3+json"
        }
        
        data = {
            "title": title,
            "body": body,
            "head": branch_name,
            "base": "dev"
        }
        
        response = requests.post(url, headers=headers, json=data)
        
        if response.status_code == 201:
            pr_data = response.json()
            log.info(f"Created PR #{pr_data['number']}: {title}")
            return pr_data["html_url"]
        else:
            log.error(f"Failed to create PR: {response.text}")
            return None
    
    def monitor_prs(self):
        """Monitor open PRs and merge when ready."""
        # Get open PRs
        # Check for approval/merge conditions
        # Auto-merge if conditions met
        pass
    
    def should_use_pr(self, change_type: str, change_size: int) -> bool:
        """Determine if change should go through PR."""
        # Use PR for:
        # - Major features (change_size > 10 files)
        # - Breaking changes
        # - Model configuration changes
        # - Architecture changes
        
        pr_types = ["feature", "breaking", "architecture", "config"]
        return change_type in pr_types or change_size > 10
```

### 3. Branch Controller

**Problem**: Need different workflows for different operations.

**Solution**: Smart branch management with automatic switching.

```python
class BranchController:
    """Controls branch usage based on operation type."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        
    def get_branch_for_operation(self, operation: str) -> str:
        """Get appropriate branch for operation."""
        branches = {
            "telegram_message": "dev",           # Daily operations
            "major_feature": "feature/auto-{ts}", # New feature branch
            "bug_fix": "dev",                     # Direct to dev
            "model_update": "dev",                # Model config (small)
            "identity_update": "dev",             # Identity changes
            "scratchpad_update": "dev",           # Scratchpad updates
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
            # Branch doesn't exist, create it
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
        
        # Pull latest
        subprocess.run(
            ["git", "pull", "--rebase", "origin", branch],
            cwd=self.repo_dir,
            check=False  # May fail if branch doesn't exist on remote
        )
    
    def auto_pr_for_major_changes(self, files_changed: list) -> bool:
        """Determine if major changes should use PR."""
        if len(files_changed) > 10:
            return True
        
        # Check for critical files
        critical_files = [
            "ouroboros/agent.py",
            "ouroboros/llm.py",
            "colab_launcher.py",
            "pyproject.toml"
        ]
        
        for file in files_changed:
            if any(critical in file for critical in critical_files):
                return True
        
        return False
```

### 4. Scratchpad Sync Manager

**Problem**: Scratchpad needs to sync across instances and PRs.

**Solution**: Central scratchpad with automatic updates.

```python
class ScratchpadSyncManager:
    """Manages scratchpad synchronization."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.scratchpad_file = drive_root / "memory" / "scratchpad.md"
        self.sync_file = drive_root / "sync" / "scratchpad_sync.json"
        
    def update_scratchpad(self, updates: dict):
        """Update scratchpad with new information."""
        scratchpad = self.load_scratchpad()
        
        # Apply updates
        for key, value in updates.items():
            scratchpad[key] = value
        
        # Add timestamp
        scratchpad["updated_at"] = datetime.now().isoformat()
        scratchpad["updated_by"] = self.get_instance_id()
        
        # Save
        self.save_scratchpad(scratchpad)
        
        # Sync to git
        self.sync_to_git()
    
    def sync_to_git(self):
        """Sync scratchpad changes to git."""
        # Check if scratchpad changed
        if self.has_changes():
            # Commit with special message
            subprocess.run(
                ["git", "add", str(self.scratchpad_file)],
                cwd=self.scratchpad_file.parent.parent,
                check=True
            )
            
            subprocess.run(
                ["git", "commit", "-m", "[scratchpad-sync] Auto-update"],
                cwd=self.scratchpad_file.parent.parent,
                check=True
            )
            
            # Pull and push
            subprocess.run(
                ["git", "pull", "--rebase", "origin", "dev"],
                cwd=self.scratchpad_file.parent.parent,
                check=False
            )
            
            subprocess.run(
                ["git", "push", "origin", "dev"],
                cwd=self.scratchpad_file.parent.parent,
                check=False
            )
    
    def merge_scratchpads(self, other_scratchpad: dict):
        """Merge scratchpad from another instance."""
        current = self.load_scratchpad()
        
        # Merge intelligently
        merged = {
            **current,
            **other_scratchpad,
            "merged_at": datetime.now().isoformat(),
            "sources": current.get("sources", []) + [other_scratchpad.get("instance_id")]
        }
        
        self.save_scratchpad(merged)
```

### 5. Cleanup Service

**Problem**: Old branches, stashes, and temporary files accumulate.

**Solution**: Automatic cleanup service.

```python
class CleanupService:
    """Automatic cleanup of git artifacts."""
    
    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        
    def cleanup_old_branches(self, days_old: int = 7):
        """Remove old merged branches."""
        # Get merged branches
        result = subprocess.run(
            ["git", "branch", "--merged", "origin/dev"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        branches = result.stdout.strip().split('\n')
        
        for branch in branches:
            branch = branch.strip().replace("* ", "")
            if branch and branch != "dev" and branch != "main":
                # Check branch age
                if self.is_branch_old(branch, days_old):
                    log.info(f"Removing old branch: {branch}")
                    subprocess.run(
                        ["git", "branch", "-d", branch],
                        cwd=self.repo_dir,
                        check=False
                    )
    
    def cleanup_stashes(self, max_stashes: int = 10):
        """Clean up old stashes."""
        result = subprocess.run(
            ["git", "stash", "list"],
            cwd=self.repo_dir,
            capture_output=True,
            text=True
        )
        
        stashes = result.stdout.strip().split('\n')
        
        if len(stashes) > max_stashes:
            # Remove oldest stashes
            for stash in stashes[max_stashes:]:
                stash_id = stash.split(':')[0]
                subprocess.run(
                    ["git", "stash", "drop", stash_id],
                    cwd=self.repo_dir,
                    check=False
                )
    
    def cleanup_temp_files(self):
        """Clean up temporary files."""
        temp_patterns = [
            "*.pyc",
            "__pycache__",
            ".pytest_cache",
            ".coverage",
            "htmlcov/",
        ]
        
        for pattern in temp_patterns:
            subprocess.run(
                ["rm", "-rf", pattern],
                cwd=self.repo_dir,
                check=False
            )
    
    def run_cleanup(self):
        """Run all cleanup tasks."""
        log.info("Starting cleanup...")
        
        self.cleanup_old_branches(days_old=7)
        self.cleanup_stashes(max_stashes=10)
        self.cleanup_temp_files()
        
        log.info("Cleanup complete")
```

### 6. Git Orchestrator (Main)

**Problem**: Need a central orchestrator to coordinate everything.

**Solution**: Main orchestrator class.

```python
class GitOrchestrator:
    """Central orchestrator for all Git operations."""
    
    def __init__(self, repo_dir: Path, drive_root: Path):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        
        # Initialize components
        self.sha_orchestrator = SHAOrchestrator(repo_dir)
        self.pr_manager = PRManager(repo_dir)
        self.branch_controller = BranchController(repo_dir)
        self.scratchpad_sync = ScratchpadSyncManager(drive_root)
        self.cleanup_service = CleanupService(repo_dir)
        
        # Initialize instance
        self.instance_id = self.sha_orchestrator.instance_id
        self.register_instance()
    
    def register_instance(self):
        """Register this instance with orchestrator."""
        self.sha_orchestrator.register_instance()
        log.info(f"Instance {self.instance_id[:8]} registered")
    
    def process_operation(self, operation: dict):
        """Process an operation with appropriate git workflow."""
        op_type = operation.get("type", "general")
        
        # Determine workflow
        if op_type == "telegram_message":
            return self.process_telegram_message(operation)
        elif op_type == "major_feature":
            return self.process_major_feature(operation)
        elif op_type == "scratchpad_update":
            return self.process_scratchpad_update(operation)
        else:
            return self.process_general(operation)
    
    def process_telegram_message(self, operation: dict):
        """Process Telegram message on dev branch."""
        branch = "dev"
        self.branch_controller.ensure_branch_ready(branch)
        
        # Execute operation
        result = self.execute_operation(operation)
        
        # Commit with instance ID
        self.commit_with_instance_id(result, operation)
        
        # Sync to remote
        self.sync_to_remote(branch)
        
        return result
    
    def process_major_feature(self, operation: dict):
        """Process major feature via PR."""
        # Create feature branch
        feature_name = operation.get("feature_name", "auto-feature")
        branch = self.pr_manager.create_pr_branch(feature_name)
        
        # Execute operation on feature branch
        result = self.execute_operation(operation)
        
        # Commit changes
        self.commit_changes(result)
        
        # Create PR
        pr_url = self.pr_manager.create_pr(
            branch_name=branch,
            title=operation.get("title", f"Feature: {feature_name}"),
            body=operation.get("description", "Auto-generated PR")
        )
        
        return {
            "branch": branch,
            "pr_url": pr_url,
            "status": "pr_created"
        }
    
    def process_scratchpad_update(self, operation: dict):
        """Update scratchpad and sync to git."""
        updates = operation.get("updates", {})
        self.scratchpad_sync.update_scratchpad(updates)
        
        return {"status": "scratchpad_updated"}
    
    def execute_operation(self, operation: dict):
        """Execute the actual operation."""
        # This would call the appropriate agent or tool
        # For now, placeholder
        return {"result": "operation_executed"}
    
    def commit_with_instance_id(self, result: dict, operation: dict):
        """Commit changes with instance ID."""
        message = f"[{self.instance_id[:8]}] {operation.get('type', 'auto')}"
        
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_dir,
            check=True
        )
        
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.repo_dir,
            check=True
        )
    
    def sync_to_remote(self, branch: str = "dev"):
        """Sync changes to remote."""
        try:
            subprocess.run(
                ["git", "pull", "--rebase", "origin", branch],
                cwd=self.repo_dir,
                check=True
            )
            
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
        # Stash local changes
        self.cleanup_service.stash_changes("sync-conflict-resolution")
        
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
    
    def continuous_sync(self):
        """Continuous synchronization loop."""
        while True:
            try:
                # Sync SHA
                self.sha_orchestrator.sync_sha()
                
                # Sync scratchpad
                self.scratchpad_sync.sync_to_git()
                
                # Monitor PRs
                self.pr_manager.monitor_prs()
                
                # Run cleanup (hourly)
                if datetime.now().minute == 0:
                    self.cleanup_service.run_cleanup()
                
                time.sleep(60)  # Sync every minute
                
            except Exception as e:
                log.error(f"Sync error: {e}")
                time.sleep(10)
```

## Workflow Examples

### Daily Telegram Operations

```
1. User sends message to Telegram bot
2. Orchestrator detects: operation_type = "telegram_message"
3. Uses dev branch (no PR needed)
4. Executes operation on dev branch
5. Commits with instance ID: [eed403ff] telegram_message
6. Syncs to remote
7. Other instances pull changes
```

### Major Feature Development

```
1. User requests major feature (e.g., "add vision support")
2. Orchestrator detects: operation_type = "major_feature"
3. Creates feature branch: feature/vision-support-1234567890
4. Executes feature on branch
5. Creates PR on GitHub
6. Other instances can review PR
7. Once approved, merge to dev
```

### Scratchpad Updates

```
1. Agent updates scratchpad with new information
2. Orchestrator detects: operation_type = "scratchpad_update"
3. Updates scratchpad.md
4. Commits with message: "[scratchpad-sync] Auto-update"
5. Syncs to remote
6. Other instances pull and merge
```

## Conflict Prevention

### Locking Mechanism

```python
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
                    # Lock expired, remove it
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
```

### Operation Queue

```python
class OperationQueue:
    """Queue operations to prevent conflicts."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.queue_file = drive_root / "git_queue.jsonl"
        
    def enqueue(self, operation: dict):
        """Add operation to queue."""
        op_id = str(uuid.uuid4())
        operation["id"] = op_id
        operation["status"] = "pending"
        operation["created_at"] = datetime.now().isoformat()
        
        with open(self.queue_file, "a") as f:
            f.write(json.dumps(operation) + "\n")
        
        return op_id
    
    def process_queue(self):
        """Process queued operations."""
        while True:
            operation = self.dequeue()
            if operation:
                # Process with lock
                lock = GitLock(self.repo_dir)
                if lock.acquire(operation["type"]):
                    try:
                        # Execute operation
                        self.execute_operation(operation)
                        operation["status"] = "completed"
                    finally:
                        lock.release()
            else:
                time.sleep(1)
```

## Integration with Current System

### Modified `full_startup.py`

```python
class FullStartup:
    """Starts all components including Git Orchestrator."""
    
    async def start(self):
        # Start Git Orchestrator
        git_orchestrator = GitOrchestrator(
            repo_dir=Path("/root/jo-project"),
            drive_root=Path.home() / ".ouroboros"
        )
        
        # Start continuous sync
        asyncio.create_task(
            asyncio.to_thread(git_orchestrator.continuous_sync)
        )
        
        # Start operation queue processor
        asyncio.create_task(
            asyncio.to_thread(git_orchestrator.process_queue)
        )
        
        # Start launcher
        await self.start_launcher()
```

### Telegram Integration

```python
class TelegramHandler:
    """Handle Telegram messages with Git Orchestrator."""
    
    async def handle_message(self, message: dict):
        """Process Telegram message via orchestrator."""
        operation = {
            "type": "telegram_message",
            "content": message["text"],
            "chat_id": message["chat_id"]
        }
        
        # Queue operation
        operation_id = git_orchestrator.operation_queue.enqueue(operation)
        
        # Wait for result
        result = await self.wait_for_result(operation_id)
        
        return result
```

## Benefits

### 1. No More SHA Mismatches
- Central SHA tracking
- Automatic sync across instances
- Intelligent conflict resolution

### 2. Clean Branch Management
- Daily work on dev branch
- Major features on PR branches
- Automatic branch cleanup

### 3. Automatic PR Creation
- Major changes automatically go through PR
- GitHub integration for review
- Safe merging process

### 4. Scratchpad Sync
- Central scratchpad updates
- Cross-instance synchronization
- Merge conflict resolution

### 5. Auto-Cleanup
- Old branches removed automatically
- Stashes cleaned up
- Temporary files deleted

### 6. Conflict Prevention
- Distributed locking
- Operation queue
- Smart conflict resolution

## Implementation Plan

### Phase 1: Core Components
- [ ] SHA Orchestrator
- [ ] Branch Controller
- [ ] Git Lock

### Phase 2: Advanced Features
- [ ] PR Manager
- [ ] Scratchpad Sync
- [ ] Cleanup Service

### Phase 3: Integration
- [ ] Full startup integration
- [ ] Telegram handler integration
- [ ] Continuous sync

### Phase 4: Testing
- [ ] Multi-machine testing
- [ ] Conflict scenarios
- [ ] PR workflow testing

## Conclusion

This Git Orchestrator design provides:
- ✅ **Centralized SHA management**
- ✅ **Automatic PR creation** for major changes
- ✅ **Dev branch for daily operations**
- ✅ **Scratchpad synchronization**
- ✅ **Automatic cleanup**
- ✅ **Conflict prevention**

**The result: A self-managing Git system that handles everything automatically!**