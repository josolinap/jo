"""
System Awareness Configuration
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class AwarenessConfig:
    """Configuration for system awareness module."""
    
    enabled: bool = os.getenv("SYSTEM_AWARENESS_ENABLED", "true").lower() == "true"
    interval: int = int(os.getenv("SYSTEM_AWARENESS_INTERVAL", "300"))  # seconds
    storage_days: int = int(os.getenv("SYSTEM_AWARENESS_STORAGE_DAYS", "30"))
    max_scans: int = int(os.getenv("SYSTEM_AWARENESS_MAX_SCANS", "100"))
    drive_root: str = os.getenv("DRIVE_ROOT", "/root/.ouroboros")
    
    # Scanner-specific intervals (in seconds)
    file_scan_interval: int = int(os.getenv("FILE_SCAN_INTERVAL", "600"))
    component_scan_interval: int = int(os.getenv("COMPONENT_SCAN_INTERVAL", "300"))
    env_scan_interval: int = int(os.getenv("ENV_SCAN_INTERVAL", "300"))
    
    def __post_init__(self):
        """Validate configuration."""
        if self.interval < 30:
            raise ValueError("Awareness interval must be at least 30 seconds")
        if self.storage_days < 1:
            raise ValueError("Storage days must be at least 1")
        if self.max_scans < 10:
            raise ValueError("Max scans must be at least 10")