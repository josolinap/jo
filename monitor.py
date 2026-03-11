"""
Ouroboros Monitor
Monitors and manages the Ouroboros launcher for continuous operation
"""

import os
import sys
import time
import pathlib
import logging
import subprocess
import signal
from typing import Optional

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - MONITOR - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/monitor.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__)

class OuroborosMonitor:
    """Monitor and manage Ouroboros launcher."""
    
    def __init__(self):
        self.process: Optional[subprocess.Popen] = None
        self.running = True
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self.shutdown)
        signal.signal(signal.SIGTERM, self.shutdown)
    
    def start_launcher(self):
        """Start the Ouroboros launcher."""
        log.info("Starting Ouroboros launcher...")
        
        # Set environment variables for continuous operation
        env = os.environ.copy()
        env['OUROBOROS_NO_GIT_SYNC'] = '1'
        env['OUROBOROS_CONSCIOUSNESS'] = '1'
        
        try:
            self.process = subprocess.Popen(
                [sys.executable, 'colab_launcher.py'],
                cwd='/root/jo-project',
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            log.info(f"Launcher started with PID: {self.process.pid}")
            return True
        except Exception as e:
            log.error(f"Failed to start launcher: {e}")
            return False
    
    def monitor_process(self):
        """Monitor the launcher process."""
        if not self.process:
            return
        
        while self.running:
            if self.process.poll() is not None:
                log.warning(f"Launcher process died with code: {self.process.returncode}")
                log.info("Restarting launcher in 5 seconds...")
                time.sleep(5)
                self.start_launcher()
            
            # Read output
            if self.process.stdout:
                line = self.process.stdout.readline()
                if line:
                    log.info(f"LAUNCHER: {line.strip()}")
            
            time.sleep(0.1)
    
    def shutdown(self, signum=None, frame=None):
        """Shutdown the monitor and launcher."""
        log.info("Shutting down Ouroboros monitor...")
        self.running = False
        
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
        
        sys.exit(0)
    
    def run(self):
        """Main monitoring loop."""
        log.info("Ouroboros Monitor started")
        
        if not self.start_launcher():
            log.error("Failed to start launcher, exiting...")
            return
        
        try:
            self.monitor_process()
        except KeyboardInterrupt:
            self.shutdown()

def main():
    """Main function."""
    monitor = OuroborosMonitor()
    monitor.run()

if __name__ == "__main__":
    main()