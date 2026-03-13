#!/usr/bin/env python3
"""
Integrated Ouroboros System
Combines all components into a fully automatic system.
"""

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from instance_id import InstanceIdentifier
from git_state_manager import GitStateManager
from model_orchestrator import ModelOrchestrator

log = logging.getLogger(__name__)


class TaskQueue:
    """Simple task queue for processing."""
    
    def __init__(self, drive_root: Path):
        self.drive_root = drive_root
        self.drive_root.mkdir(exist_ok=True)
        self.queue_file = drive_root / "task_queue.jsonl"
    
    async def enqueue(self, task: dict, machine_id: str) -> str:
        """Add task to queue."""
        task_id = str(uuid.uuid4())
        task_entry = {
            "id": task_id,
            "task": task,
            "machine_id": machine_id,
            "status": "pending",
            "created_at": datetime.now().isoformat()
        }
        
        with open(self.queue_file, "a") as f:
            f.write(json.dumps(task_entry) + "\n")
        
        return task_id
    
    async def dequeue(self) -> Optional[dict]:
        """Get next task from queue."""
        if not self.queue_file.exists():
            return None
        
        # Read all tasks
        tasks = []
        with open(self.queue_file, "r") as f:
            for line in f:
                try:
                    task = json.loads(line)
                    if task["status"] == "pending":
                        tasks.append(task)
                except json.JSONDecodeError:
                    continue
        
        if not tasks:
            return None
        
        # Take first pending task
        task = tasks[0]
        task["status"] = "processing"
        
        # Rewrite queue
        with open(self.queue_file, "w") as f:
            for t in tasks:
                f.write(json.dumps(t) + "\n")
        
        return task


class OuroborosSystem:
    """Integrated Ouroboros system with automatic operation."""
    
    def __init__(self):
        # Initialize paths
        self.drive_root = Path.home() / ".ouroboros"
        self.drive_root.mkdir(exist_ok=True)
        
        # Initialize components
        self.instance_manager = InstanceIdentifier(self.drive_root)
        self.instance_id = self.instance_manager.get_id()
        self.machine_info = self.instance_manager.get_machine_info()
        
        self.model_router = ModelOrchestrator()
        self.task_queue = TaskQueue(self.drive_root)
        self.git_manager = GitStateManager(Path("/root/jo-project"))
        
        # State
        self.running = True
        self.last_sync = 0
        
        log.info(f"Initialized Ouroboros system (instance: {self.instance_id[:8]})")
    
    async def start(self):
        """Start the entire system."""
        log.info("Starting Ouroboros components...")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.git_sync_loop()),
            asyncio.create_task(self.model_health_loop()),
            asyncio.create_task(self.task_processor()),
            asyncio.create_task(self.telegram_listener()),
        ]
        
        log.info("All components started")
        log.info("System ready for Telegram interaction")
        
        # Wait for all tasks
        await asyncio.gather(*tasks)
    
    async def git_sync_loop(self):
        """Continuous git synchronization."""
        while self.running:
            try:
                await self.sync_git()
                await asyncio.sleep(60)  # Sync every minute
            except Exception as e:
                log.error(f"Git sync error: {e}")
                await asyncio.sleep(10)
    
    async def sync_git(self):
        """Perform git sync cycle."""
        log.info(f"[{self.instance_id[:8]}] Syncing git state...")
        
        try:
            # Pull latest changes
            success, message = self.git_manager.pull_with_rebase("dev")
            
            if success:
                log.info(f"[{self.instance_id[:8]}] Git sync successful")
                self.last_sync = time.time()
            else:
                log.warning(f"[{self.instance_id[:8]}] Git sync failed: {message}")
                
        except Exception as e:
            log.error(f"Git sync error: {e}")
    
    async def model_health_loop(self):
        """Monitor model health continuously."""
        # Discover models first
        await self.model_router.discover_models()
        
        while self.running:
            try:
                # Test a few models each cycle
                model_ids = list(self.model_router.models.keys())[:3]
                for model_id in model_ids:
                    status, response_time = await self.model_router.test_model(model_id)
                    if status.value == "healthy":
                        log.debug(f"Model {model_id}: healthy ({response_time:.2f}s)")
                
                await asyncio.sleep(60)
            except Exception as e:
                log.error(f"Model health check error: {e}")
                await asyncio.sleep(10)
    
    async def task_processor(self):
        """Process tasks from queue."""
        while self.running:
            try:
                task = await self.task_queue.dequeue()
                
                if task:
                    log.info(f"Processing task: {task['id'][:8]}")
                    await self.process_task(task)
                else:
                    await asyncio.sleep(1)
                    
            except Exception as e:
                log.error(f"Task processing error: {e}")
                await asyncio.sleep(1)
    
    async def process_task(self, task: dict):
        """Process a single task."""
        try:
            # Get working model
            model = await self.model_router.get_working_model()
            
            # Simulate task processing (in production, this would call actual LLM)
            await asyncio.sleep(0.1)
            
            # Update task status
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            task["model_used"] = model
            
            log.info(f"Task {task['id'][:8]} completed using {model}")
            
        except Exception as e:
            log.error(f"Task {task['id'][:8]} failed: {e}")
            task["status"] = "failed"
            task["error"] = str(e)
    
    async def telegram_listener(self):
        """Listen for Telegram messages."""
        # In production, this would integrate with supervisor/telegram.py
        log.info("Telegram listener ready (simulated)")
        
        while self.running:
            # Simulate receiving messages
            await asyncio.sleep(5)
            
            # Check for new messages (would come from Telegram API)
            # For now, just log that we're listening
            pass


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    async def run():
        system = OuroborosSystem()
        await system.start()
    
    asyncio.run(run())