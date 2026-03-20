"""Configuration for system awareness module."""

import os
from dataclasses import dataclass


@dataclass
class AwarenessConfig:
    """Configuration for system awareness module."""

    enabled: bool = os.getenv("SYSTEM_AWARENESS_ENABLED", "true").lower() == "true"
    interval: int = int(os.getenv("SYSTEM_AWARENESS_INTERVAL", "300"))
    storage_days: int = int(os.getenv("SYSTEM_AWARENESS_STORAGE_DAYS", "30"))
    max_scans: int = int(os.getenv("SYSTEM_AWARENESS_MAX_SCANS", "100"))
    drive_root: str = os.getenv("DRIVE_ROOT", os.path.join(os.path.expanduser("~"), ".jo_data"))

    def __post_init__(self):
        if self.interval < 30:
            raise ValueError("Awareness interval must be at least 30 seconds")
