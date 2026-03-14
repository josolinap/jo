#!/usr/bin/env python3
"""
Automatic Ouroboros Startup System
Starts the entire Ouroboros system automatically without manual intervention.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).parent))

from ouroboros_system import OuroborosSystem

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/tmp/ouroboros.log'),
        logging.StreamHandler()
    ]
)

log = logging.getLogger(__name__)


async def main():
    """Start Ouroboros automatically."""
    log.info("Starting Ouroboros System...")
    
    try:
        system = OuroborosSystem()
        await system.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    except Exception as e:
        log.error(f"Fatal error: {e}")
        log.info("Restarting in 5 seconds...")
        await asyncio.sleep(5)
        await main()


if __name__ == "__main__":
    asyncio.run(main())