# Multi-Machine Ouroboros Solution

## Problem Overview

You're running Ouroboros on multiple machines (Windows + Arch Linux) and encountering:

1. **Git Conflicts**: Local changes conflict with remote changes
2. **SHA Mismatch**: Worker processes detect different git states
3. **Codebase Access**: Agent needs to see local changes, not just GitHub
4. **Sync Issues**: Changes on one machine don't reflect on another

## Solution Architecture

### 1. Unique Instance Identification

**File**: `instance_id.py`

Each machine gets a unique ID based on:
- Hostname
- Platform (Windows/Linux/Mac)
- MAC address (for hardware uniqueness)
- UUID generation

```python
# Creates: ~/.jo_data/instance_id.json
{
  "instance_id": "abc123...",
  "hostname": "arch-linux-pc",
  "platform": "linux",
  "machine_id": "arch-linux-pc-...",
  "created": "...",
  "last_seen": "..."
}
```

### 2. Git State Management

**File**: `git_state_manager.py`

**Conflict Resolution Strategies:**

| Scenario | Action |
|----------|--------|
| Rebase conflict | Abort rebase, stash changes, pull again |
| Push rejection | Pull with rebase, then push |
| Uncommitted changes | Auto-commit with machine ID |
| Multiple machines editing same file | Keep remote version, merge locally |

**Key Functions:**
- `pull_with_rebase()`: Auto-resolve conflicts
- `stash_changes()`: Safe backup of local changes
- `handle_conflicts()`: Automatic resolution
- `push_changes()`: With retry on rejection

### 3. Multi-Machine Sync Flow

```
Machine A (Windows)
├── Make changes locally
├── Commit with machine ID: "machine-a-xxx"
├── Push to origin/dev
└── Changes available remotely

Machine B (Arch Linux)
├── Pull from origin/dev (every 60 seconds)
├── Detect conflicts (if any)
├── Auto-resolve or mark for review
└── Continue operation
```

### 4. Implementation Files

#### A. `instance_id.py` - Unique Machine Identification
```python
# Usage in Ouroboros
from instance_id import InstanceIdentifier

identifier = InstanceIdentifier()
machine_id = identifier.get_id()
print(f"Running on machine: {machine_id}")
```

#### B. `git_state_manager.py` - Git Operations with Conflict Handling
```python
# Usage in monitor.py
from git_state_manager import GitStateManager

manager = GitStateManager(Path("/root/jo-project"))
manager.pull_with_rebase("dev")  # Auto-resolves conflicts
```

#### C. Modified `monitor.py` - Git Sync Integration
```python
class OuroborosMonitor:
    def __init__(self):
        self.git_manager = GitStateManager(self.repo_dir)
    
    def sync_git_state(self):
        """Sync git state before starting launcher."""
        # Pull latest changes
        success, message = self.git_manager.pull_with_rebase("dev")
        
        if not success:
            log.warning(f"Git sync failed: {message}")
            # Continue anyway - local changes OK
```

#### D. `machine_sync.py` - Cross-Machine State Tracking
```python
# Tracks which machine made which changes
~/.jo_data/sync/
├── machine-a-xxx.json  # Changes from Windows machine
├── machine-b-yyy.json  # Changes from Arch Linux
└── pending.json        # Changes awaiting sync
```

### 5. Git Workflow for Multi-Machine

#### Daily Workflow

**On Machine A (Windows):**
```bash
# 1. Start Ouroboros (auto-syncs)
python3 monitor.py

# 2. Make changes via Telegram
# (Agent commits and pushes automatically)

# 3. When done, ensure clean state
git status  # Should be clean
```

**On Machine B (Arch Linux):**
```bash
# 1. Start Ouroboros (auto-pulls from remote)
python3 monitor.py

# 2. Agent sees changes from Machine A
# 3. Continue working seamlessly
```

#### Conflict Resolution

**Scenario 1: Both machines edited same file**
- Machine A pushes changes
- Machine B pulls (conflict detected)
- System automatically:
  1. Stashes local changes
  2. Pulls remote changes
  3. Applies stashed changes
  4. Prompts for merge if needed

**Scenario 2: SHA mismatch**
- Agent detects different git state
- System automatically:
  1. Commits pending changes with machine ID
  2. Pulls latest from remote
  3. Continues operation

### 6. Configuration

#### Machine-Specific Settings

**File**: `~/.jo_data/machine_config.json`
```json
{
  "machine_id": "abc123...",
  "hostname": "arch-linux-pc",
  "platform": "linux",
  "preferred_branch": "dev",
  "auto_push": true,
  "auto_pull": true,
  "conflict_resolution": "auto-stash",
  "instance_role": "worker"
}
```

#### Environment Variables

```bash
# .env file
ENABLE_GIT_SYNC=1
AUTO_PULL_INTERVAL=60  # seconds
CONFLICT_RESOLUTION=auto-stash
MACHINE_ID=$(python3 instance_id.py)
```

### 7. Handling Different Scenarios

#### Scenario 1: Running on Windows + Arch Linux

**Solution:**
1. Each machine has unique ID
2. Changes are committed with machine ID in commit message
3. Pull requests auto-merge with conflict resolution
4. Local changes are preserved during sync

**Commit Format:**
```
[machine-a-xxx] Fix: Update launcher configuration
[machine-b-yyy] Feat: Add model orchestration
```

#### Scenario 2: Agent Needs Local Codebase Access

**Solution:**
1. Agent can read local files via `repo_read` tool
2. Changes are tracked locally before pushing
3. Dual-mode: Can work offline, sync when online
4. Local state saved to `~/.jo_data/local_state.json`

#### Scenario 3: Multiple Instances Running Simultaneously

**Solution:**
1. Each instance has unique ID
2. Git operations are atomic (with retries)
3. Conflict resolution prioritizes:
   - Local changes (preserved)
   - Remote changes (pulled)
   - Manual merge if needed

### 8. Monitoring and Logging

**Log Files:**
- `/tmp/monitor.log` - Monitor activity
- `~/.jo_data/logs/git_sync.log` - Git operations
- `~/.jo_data/logs/conflicts.log` - Conflict resolution

**Status Dashboard:**
```bash
python3 -c "
from git_state_manager import GitStateManager
from instance_id import InstanceIdentifier

manager = GitStateManager(Path('/root/jo-project'))
identifier = InstanceIdentifier()

print(f'Machine ID: {identifier.get_id()}')
print(f'Clean state: {manager.get_clean_state()}')
print(f'Conflicts: {manager.get_conflict_status()}')
"
```

### 9. Testing the Solution

```bash
# Test 1: Check instance ID
python3 instance_id.py

# Test 2: Check git state
python3 git_state_manager.py /root/jo-project

# Test 3: Simulate multi-machine sync
# On Machine A:
git add -A
git commit -m "Test from machine A"
git push origin dev

# On Machine B (wait 60 seconds or pull manually):
git pull --rebase origin dev
```

### 10. Summary

**Key Components:**
1. ✅ **Instance ID**: Unique identifier per machine
2. ✅ **Git State Manager**: Automatic conflict resolution
3. ✅ **Dual-Mode Operation**: Works online/offline
4. ✅ **Machine-Aware Sync**: Tracks changes per machine
5. ✅ **Auto-Resolution**: Handles most conflicts automatically

**Benefits:**
- No more SHA mismatches
- Seamless multi-machine operation
- Agent can see local and remote changes
- Automatic conflict resolution
- Machine-specific tracking

**This architecture ensures Ouroboros can run on multiple machines without conflicts while maintaining codebase synchronization.**