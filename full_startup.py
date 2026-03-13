#!/usr/bin/env python3
"""
Full Startup - Starts both integrated system AND launcher
This ensures the system runs continuously with all components
"""

import asyncio
import logging
import subprocess
import sys
import os
import signal
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from ouroboros_system import OuroborosSystem
from git_orchestrator import GitOrchestrator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - FULL_STARTUP - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/full_startup.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__)


class FullStartup:
    """Starts both the integrated system and the launcher."""
    
    def __init__(self):
        self.system = None
        self.launcher_process = None
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    async def start(self):
        """Start all components."""
        log.info("Starting Ouroboros Full System...")
        
        # 1. Start Git Orchestrator
        self.git_orchestrator = GitOrchestrator(
            repo_dir=Path("/root/jo-project"),
            drive_root=Path.home() / ".ouroboros"
        )
        
        # Start continuous sync
        asyncio.create_task(self.git_orchestrator.continuous_sync())
        
        # 2. Start integrated system (model routing, git sync, etc.)
        self.system = OuroborosSystem()
        system_task = asyncio.create_task(self.system.start())
        
        # 3. Start launcher (colab_launcher.py)
        launcher_task = asyncio.create_task(self.start_launcher())
        
        # Wait for both
        await asyncio.gather(system_task, launcher_task)
    
    async def start_launcher(self):
        """Start the colab launcher in background."""
        log.info("Starting colab launcher...")
        
        # Set environment variables
        env = os.environ.copy()
        env['OUROBOROS_NO_GIT_SYNC'] = '1'  # Git sync handled by integrated system
        env['OUROBOROS_CONSCIOUSNESS'] = '1'
        
        try:
            self.launcher_process = subprocess.Popen(
                [sys.executable, 'colab_launcher.py'],
                cwd='/root/jo-project',
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            log.info(f"Launcher started with PID: {self.launcher_process.pid}")
            
            # Monitor launcher output
            while self.running:
                if self.launcher_process.poll() is not None:
                    log.warning(f"Launcher died with code: {self.launcher_process.returncode}")
                    log.info("Restarting launcher in 5 seconds...")
                    await asyncio.sleep(5)
                    await self.start_launcher()
                    return
                
                # Read output
                line = self.launcher_process.stdout.readline()
                if line:
                    log.info(f"LAUNCHER: {line.strip()}")
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            log.error(f"Failed to start launcher: {e}")
    
    def shutdown(self, signum=None, frame=None):
        """Shutdown all components."""
        log.info("Shutting down...")
        self.running = False
        
        if self.launcher_process:
            self.launcher_process.terminate()
            try:
                self.launcher_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.launcher_process.kill()
        
        sys.exit(0)


async def main():
    """Main entry point."""
    startup = FullStartup()
    await startup.start()


if __name__ == "__main__":
    asyncio.run(main())