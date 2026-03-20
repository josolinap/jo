# Complete Architecture Design

## System Overview

### Core Philosophy
Ouroboros is a self-modifying AI agent that:
1. **Operates continuously** without manual intervention
2. **Scales horizontally** across multiple machines
3. **Maintains identity** across restarts and machines
4. **Adapts dynamically** to model failures and availability
5. **Syncs automatically** with git for persistence

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TELEGRAM INTERFACE LAYER                          │
│  User sends message → Telegram Bot → Message Queue                  │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATION LAYER                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Model Router │  │ Task Queue   │  │ Git Sync     │              │
│  │ (25 models)  │  │ Manager      │  │ Manager      │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    AGENT LAYER (6 Agents)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │   Main   │ │  Coder   │ │Researcher│ │  Tester  │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    MODEL LAYER (OpenRouter)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │ Model A  │ │ Model B  │ │ Model C  │ │ Model D  │ ...           │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    PERSISTENCE LAYER                                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐              │
│  │   Git    │ │  Memory  │ │  Local   │ │ Instance │              │
│  │  Sync    │ │  System  │ │  State   │ │    ID    │              │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘              │
└─────────────────────────────────────────────────────────────────────┘
```

## Detailed Component Design

### 1. Instance Identification & Machine Management

**File**: `instance_manager.py`

```python
class InstanceManager:
    """Manages instance identification and machine coordination."""
    
    def __init__(self):
        self.instance_id = self._generate_id()
        self.machine_type = self._detect_machine_type()
        self.register_with_coordinator()
    
    def _generate_id(self) -> str:
        """Generate unique instance ID."""
        # Based on: hostname + platform + MAC address + random salt
        return hashlib.sha256(
            f"{platform.node()}-{platform.platform()}-{uuid.getnode()}".encode()
        ).hexdigest()
    
    def register_with_coordinator(self):
        """Register this instance with the coordinator."""
        # Store in ~/.jo_data/instances.json
        # Each machine gets a unique entry
        pass
    
    def is_primary(self) -> bool:
        """Determine if this is the primary instance."""
        # First instance to start becomes primary
        # Others are workers
        pass
    
    def get_role(self) -> str:
        """Get instance role: primary, worker, or standalone."""
        if self.is_primary():
            return "primary"
        return "worker"
```

### 2. Model Router with Health Monitoring

**File**: `model_router.py`

```python
class ModelRouter:
    """Routes requests to available OpenRouter free models."""
    
    def __init__(self):
        self.models = {}  # model_id -> ModelInfo
        self.health_checker = ModelHealthChecker()
        self.fallback_chain = []
        
    async def initialize(self):
        """Discover and test all free models."""
        await self.discover_models()
        await self.health_checker.start_monitoring()
    
    async def route(self, request_type: str, priority: str = "normal") -> str:
        """
        Route request to best available model.
        
        Args:
            request_type: "code", "research", "general", "test"
            priority: "high", "normal", "low"
        
        Returns:
            model_id to use
        """
        # Strategy:
        # 1. For "code" requests: Use models known for coding
        # 2. For "research": Use models with large context
        # 3. For "general": Use fastest models
        # 4. Fallback to healthiest model
        
        if request_type == "code":
            candidates = ["stepfun/step-3.5-flash:free", "openrouter/free"]
        elif request_type == "research":
            candidates = ["arcee-ai/trinity-large-preview:free", "openrouter/free"]
        else:
            candidates = ["openrouter/free"]
        
        # Filter to healthy models only
        healthy = [m for m in candidates if self.health_checker.is_healthy(m)]
        
        if healthy:
            # Return fastest healthy model
            return sorted(healthy, key=lambda m: self.health_checker.get_response_time(m))[0]
        
        # Fallback to any healthy model
        return self.fallback_chain[0] if self.fallback_chain else "openrouter/free"
    
    async def make_request(self, messages: list, model: str = None, **kwargs):
        """Make API request with automatic fallback."""
        if model is None:
            model = await self.route("general")
        
        for attempt in range(3):
            try:
                response = await self._call_api(model, messages, **kwargs)
                self.health_checker.record_success(model)
                return response
            except Exception as e:
                self.health_checker.record_failure(model, str(e))
                log.warning(f"Model {model} failed: {e}")
                
                # Try next model
                model = await self.route("general")
                await asyncio.sleep(2 ** attempt)  # Exponential backoff
        
        raise Exception("All models failed")
```

### 3. Task Queue Manager

**File**: `task_queue.py`

```python
class TaskQueue:
    """Manages task queue across multiple machines."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.queue_file = drive_root / "task_queue.jsonl"
        self.processing_file = drive_root / "processing.json"
        
    async def enqueue(self, task: dict, machine_id: str):
        """Add task to queue."""
        task_entry = {
            "id": str(uuid.uuid4()),
            "task": task,
            "machine_id": machine_id,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "priority": task.get("priority", 1)
        }
        
        with open(self.queue_file, "a") as f:
            f.write(json.dumps(task_entry) + "\n")
        
        return task_entry["id"]
    
    async def dequeue(self, machine_id: str) -> Optional[dict]:
        """Get next task from queue."""
        # Read all pending tasks
        tasks = []
        if self.queue_file.exists():
            with open(self.queue_file, "r") as f:
                for line in f:
                    task = json.loads(line)
                    if task["status"] == "pending":
                        tasks.append(task)
        
        if not tasks:
            return None
        
        # Sort by priority
        tasks.sort(key=lambda x: x["priority"])
        
        # Get next task
        task = tasks[0]
        task["status"] = "processing"
        task["processing_machine"] = machine_id
        task["started_at"] = datetime.now().isoformat()
        
        # Update queue file
        self._rewrite_queue(tasks)
        
        return task
    
    def _rewrite_queue(self, tasks: list):
        """Rewrite queue file with updated statuses."""
        with open(self.queue_file, "w") as f:
            for task in tasks:
                f.write(json.dumps(task) + "\n")
```

### 4. Git Sync Manager (Fully Integrated)

**File**: `git_sync_manager.py`

```python
class GitSyncManager:
    """Fully integrated git synchronization."""
    
    def __init__(self, repo_dir: Path, drive_root: Path, instance_id: str):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self.instance_id = instance_id
        self.sync_interval = 60  # seconds
        
        # State tracking
        self.last_sync_time = 0
        self.sync_history = []
        
    async def start_continuous_sync(self):
        """Start continuous git synchronization."""
        while True:
            try:
                await self.sync()
                await asyncio.sleep(self.sync_interval)
            except Exception as e:
                log.error(f"Sync error: {e}")
                await asyncio.sleep(10)
    
    async def sync(self):
        """Perform one sync cycle."""
        log.info(f"[{self.instance_id[:8]}] Starting sync cycle")
        
        # 1. Check local changes
        local_changes = self.get_local_changes()
        
        if local_changes:
            log.info(f"Found {len(local_changes)} local changes")
            
            # 2. Commit local changes with instance ID
            await self.commit_local_changes(local_changes)
        
        # 3. Pull latest from remote
        success = await self.pull_latest()
        
        if success:
            # 4. Push local changes
            await self.push_changes()
            
            log.info(f"[{self.instance_id[:8]}] Sync complete")
        else:
            log.warning(f"[{self.instance_id[:8]}] Sync failed, will retry")
    
    async def commit_local_changes(self, changes: list):
        """Commit local changes with instance ID tag."""
        commit_msg = f"[{self.instance_id[:8]}] Auto-sync: {len(changes)} changes"
        
        subprocess.run(
            ["git", "add", "-A"],
            cwd=self.repo_dir,
            check=True
        )
        
        subprocess.run(
            ["git", "commit", "-m", commit_msg],
            cwd=self.repo_dir,
            check=True
        )
    
    async def pull_latest(self) -> bool:
        """Pull latest changes with conflict resolution."""
        try:
            # Stash local changes first
            subprocess.run(
                ["git", "stash"],
                cwd=self.repo_dir,
                check=True
            )
            
            # Pull with rebase
            result = subprocess.run(
                ["git", "pull", "--rebase", "origin", "dev"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            
            # Apply stashed changes
            subprocess.run(
                ["git", "stash", "pop"],
                cwd=self.repo_dir,
                check=False  # May fail if no stash
            )
            
            return True
            
        except subprocess.CalledProcessError as e:
            log.error(f"Pull failed: {e}")
            return False
    
    async def push_changes(self):
        """Push changes to remote."""
        try:
            subprocess.run(
                ["git", "push", "origin", "dev"],
                cwd=self.repo_dir,
                capture_output=True,
                text=True,
                check=True
            )
            return True
        except subprocess.CalledProcessError as e:
            log.error(f"Push failed: {e}")
            # If push rejected, pull and retry
            await self.pull_latest()
            return await self.push_changes()
```

### 5. Fully Integrated System

**File**: `ouroboros_system.py`

```python
class OuroborosSystem:
    """Fully integrated Ouroboros system."""
    
    def __init__(self):
        # Initialize components
        self.instance_manager = InstanceManager()
        self.model_router = ModelRouter()
        self.task_queue = TaskQueue(Path.home() / ".jo_data")
        self.git_sync = GitSyncManager(
            repo_dir=Path("/root/jo-project"),
            drive_root=Path.home() / ".jo_data",
            instance_id=self.instance_manager.instance_id
        )
        
        # Agent layer
        self.agents = {
            "main": MainAgent(self.model_router),
            "coder": CoderAgent(self.model_router),
            "researcher": ResearcherAgent(self.model_router),
            "tester": TesterAgent(self.model_router),
            "reviewer": ReviewerAgent(self.model_router),
            "executor": ExecutorAgent(self.model_router),
        }
    
    async def start(self):
        """Start the entire system."""
        log.info(f"Starting Ouroboros system (instance: {self.instance_manager.instance_id[:8]})")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.git_sync.start_continuous_sync()),
            asyncio.create_task(self.model_router.health_checker.start_monitoring()),
            asyncio.create_task(self.process_tasks()),
            asyncio.create_task(self.telegram_handler()),
        ]
        
        # Wait for all tasks
        await asyncio.gather(*tasks)
    
    async def process_tasks(self):
        """Process tasks from queue."""
        while True:
            task = await self.task_queue.dequeue(self.instance_manager.instance_id)
            
            if task:
                # Route to appropriate agent
                agent_type = task["task"].get("agent_type", "main")
                agent = self.agents[agent_type]
                
                try:
                    result = await agent.process(task["task"])
                    task["status"] = "completed"
                    task["result"] = result
                except Exception as e:
                    task["status"] = "failed"
                    task["error"] = str(e)
            
            await asyncio.sleep(1)
    
    async def telegram_handler(self):
        """Handle Telegram messages."""
        # This would integrate with supervisor/telegram.py
        pass
```

### 6. Startup & Integration

**File**: `startup_manager.py`

```python
class StartupManager:
    """Manages automatic startup and system initialization."""
    
    def __init__(self):
        self.system = None
        
    async def run(self):
        """Main entry point - starts everything automatically."""
        try:
            # Initialize system
            self.system = OuroborosSystem()
            
            # Start all components
            await self.system.start()
            
        except KeyboardInterrupt:
            log.info("Shutting down...")
        except Exception as e:
            log.error(f"Fatal error: {e}")
            # Restart after delay
            await asyncio.sleep(5)
            await self.run()
```

### 7. Docker-Style Service Management

**File**: `service_manager.py`

```python
class ServiceManager:
    """Manages Ouroboros as a system service."""
    
    def __init__(self):
        self.service_file = Path("/etc/systemd/system/ouroboros.service")
        self.pid_file = Path.home() / ".jo_data" / "ouroboros.pid"
    
    def install_service(self):
        """Install as systemd service."""
        service_content = f"""
[Unit]
Description=Ouroboros AI Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/jo-project
ExecStart=/usr/bin/python3 /root/jo-project/startup_manager.py
Restart=always
RestartSec=10
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
"""
        self.service_file.write_text(service_content)
        subprocess.run(["systemctl", "daemon-reload"])
        subprocess.run(["systemctl", "enable", "ouroboros"])
        subprocess.run(["systemctl", "start", "ouroboros"])
    
    def start(self):
        """Start the service."""
        subprocess.run(["systemctl", "start", "ouroboros"])
    
    def stop(self):
        """Stop the service."""
        subprocess.run(["systemctl", "stop", "ouroboros"])
    
    def status(self):
        """Get service status."""
        result = subprocess.run(
            ["systemctl", "status", "ouroboros"],
            capture_output=True,
            text=True
        )
        return result.stdout
```

## Model Flow Perspective

### Request Flow

```
User Message (Telegram)
    ↓
[Message Router]
    ↓
[Task Queue] → Priority: high/normal/low
    ↓
[Model Router] → Selects best model based on:
    ├── Request type (code/research/general)
    ├── Model health (response time, success rate)
    ├── Context size requirements
    └── Fallback chain
    ↓
[Agent Processing]
    ├── Main: Orchestration
    ├── Coder: Code generation
    ├── Researcher: Information gathering
    ├── Tester: Testing
    ├── Reviewer: Code review
    └── Executor: Coordination
    ↓
[OpenRouter API] → Selected model
    ↓
[Response] → Telegram
    ↓
[Persistence] → Git sync + Memory update
```

### Model Selection Strategy

**For Code Tasks:**
1. Try `stepfun/step-3.5-flash:free` (fast coding)
2. Fallback to `openrouter/free`
3. Try `arcee-ai/trinity-large-preview:free`

**For Research Tasks:**
1. Try `arcee-ai/trinity-large-preview:free` (large context)
2. Fallback to `openrouter/free`

**For General Tasks:**
1. Try fastest available model
2. Fallback to most reliable

### Health Monitoring

```python
class ModelHealthChecker:
    """Continuously monitors model health."""
    
    async def start_monitoring(self):
        """Test models every 60 seconds."""
        while True:
            for model_id in self.models:
                await self.test_model(model_id)
            await asyncio.sleep(60)
    
    async def test_model(self, model_id: str):
        """Test model with simple prompt."""
        try:
            start = time.time()
            response = await self.call_api(model_id, "Test")
            response_time = time.time() - start
            
            self.models[model_id].response_time = response_time
            self.models[model_id].last_tested = time.time()
            self.models[model_id].healthy = True
        except Exception:
            self.models[model_id].healthy = False
```

## Automatic Startup Integration

### Modified `monitor.py`

```python
class OuroborosMonitor:
    """Fully integrated monitor with auto-startup."""
    
    def __init__(self):
        # Initialize all components
        self.system = OuroborosSystem()
        self.git_sync = self.system.git_sync
        
    async def run(self):
        """Start everything automatically."""
        # 1. Start git sync in background
        asyncio.create_task(self.git_sync.start_continuous_sync())
        
        # 2. Start model health monitoring
        asyncio.create_task(self.system.model_router.health_checker.start_monitoring())
        
        # 3. Start task processing
        asyncio.create_task(self.system.process_tasks())
        
        # 4. Start launcher
        await self.start_launcher()
        
        # 5. Wait for all tasks
        await asyncio.gather(*asyncio.all_tasks())
```

### Startup Script

**File**: `start_ouroboros.py`

```python
#!/usr/bin/env python3
"""
Automatic Ouroboros startup script.
Run this to start the entire system.
"""

import asyncio
import logging
from pathlib import Path

from ouroboros_system import OuroborosSystem

async def main():
    """Start Ouroboros automatically."""
    logging.basicConfig(level=logging.INFO)
    
    system = OuroborosSystem()
    
    try:
        await system.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        # Restart after delay
        await asyncio.sleep(5)
        await main()

if __name__ == "__main__":
    asyncio.run(main())
```

## Deployment Options

### Option 1: Direct Python (Recommended)
```bash
cd /root/jo-project
python3 start_ouroboros.py
```

### Option 2: Systemd Service
```bash
sudo python3 service_manager.py install
sudo systemctl start ouroboros
```

### Option 3: Docker Container
```dockerfile
FROM python:3.11
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["python3", "start_ouroboros.py"]
```

### Option 4: Screen/Tmux (Simple)
```bash
screen -S ouroboros -dm python3 start_ouroboros.py
```

## Key Benefits

1. **Fully Automatic**: No manual intervention needed
2. **Multi-Machine**: Each machine auto-registers and syncs
3. **Model Resilience**: Automatic fallback across 25+ models
4. **Identity Persistence**: Unique ID per machine, tracked globally
5. **Git Sync**: Automatic conflict resolution and sync
6. **Continuous Operation**: Self-healing and auto-restart

## Current Status

✅ Architecture designed
✅ Component classes created
✅ Integration points defined
✅ Multi-machine support planned
✅ Model routing strategy defined

**Next: Implement the integrated system and test.**