import json
import os
from datetime import datetime
from pathlib import Path

class AwarenessSystem:
    def __init__(self):
        self.drive_root = "/root/.ouroboros"
        self.log_path = os.path.join(self.drive_root, "logs", "awareness.jsonl")
        self.scratchpad_path = os.path.join(self.drive_root, "memory", "scratchpad.md")
        self.repo_root = "/root/jo-project"
        self.data = None

    def scan(self):
        """Scan system state and return structured awareness data."""
        try:
            with open(self.scratchpad_path, "r", encoding="utf-8") as f:
                scratchpad_content = f.read()
            
            repo_files = []
            for root, dirs, files in os.walk(self.repo_root):
                for file in files:
                    if file.endswith(('.py', '.md', '.json', '.env')):
                        rel_path = os.path.relpath(os.path.join(root, file), self.repo_root)
                        repo_files.append(rel_path)
            
            git_head = os.popen("cd /root/jo-project && git rev-parse HEAD").read().strip()
            git_branch = os.popen("cd /root/jo-project && git symbolic-ref --short HEAD").read().strip()
            
            awareness_data = {
                "timestamp": datetime.now().isoformat(),
                "sys": {
                    "branch": git_branch,
                    "sha": git_head,
                    "files": repo_files,
                    "scratchpad_length": len(scratchpad_content)
                },
                "last_scan": None
            }
            
            # Write log entry
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(awareness_data) + "\n")
            
            return awareness_data
        except Exception as e:
            return {"error": str(e), "timestamp": datetime.now().isoformat()}

# Make ready
if __name__ == "__main__":
    a = AwarenessSystem()
    result = a.scan()
    print(json.dumps(result, indent=2))