"""
Unique Instance Identification for Multi-Machine Ouroboros
"""

import uuid
import platform
import socket
import json
from pathlib import Path
from typing import Optional


class InstanceIdentifier:
    """Unique identifier for each Ouroboros instance."""
    
    def __init__(self, drive_root: Optional[Path] = None):
        if drive_root is None:
            drive_root = Path.home() / ".ouroboros"
        
        self.drive_root = drive_root
        self.drive_root.mkdir(exist_ok=True)
        self.id_file = drive_root / "instance_id.json"
        self.instance_id = self._load_or_create_id()
    
    def _load_or_create_id(self) -> str:
        """Load existing ID or create new one."""
        if self.id_file.exists():
            try:
                data = json.loads(self.id_file.read_text())
                return data["instance_id"]
            except (json.JSONDecodeError, KeyError):
                pass
        
        # Create unique ID based on machine characteristics
        # Combine multiple identifiers for uniqueness
        machine_id = f"{platform.node()}-{socket.gethostname()}-{uuid.getnode()}"
        instance_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, machine_id))
        
        data = {
            "instance_id": instance_id,
            "hostname": platform.node(),
            "platform": platform.system(),
            "machine_id": machine_id,
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
        if self.id_file.exists():
            try:
                data = json.loads(self.id_file.read_text())
                data["last_seen"] = str(uuid.uuid4())
                self.id_file.write_text(json.dumps(data, indent=2))
            except (json.JSONDecodeError, KeyError):
                pass
    
    def get_machine_info(self) -> dict:
        """Get complete machine information."""
        if self.id_file.exists():
            try:
                return json.loads(self.id_file.read_text())
            except (json.JSONDecodeError, KeyError):
                pass
        
        return {
            "instance_id": self.instance_id,
            "hostname": platform.node(),
            "platform": platform.system()
        }


if __name__ == "__main__":
    import sys
    drive_root = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    identifier = InstanceIdentifier(drive_root)
    print(f"Instance ID: {identifier.get_id()}")
    print(f"Machine Info: {identifier.get_machine_info()}")