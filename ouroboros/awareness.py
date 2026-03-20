import json
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


class AwarenessSystem:
    def __init__(self, repo_root: Optional[str] = None, drive_root: Optional[str] = None):
        if repo_root is None:
            repo_root = str(Path.cwd())
        if drive_root is None:
            drive_root = str(Path.home() / ".jo_data")
        self.repo_root = Path(repo_root)
        self.drive_root = Path(drive_root)
        self.log_path = self.drive_root / "logs" / "awareness.jsonl"
        self.scratchpad_path = self.drive_root / "memory" / "scratchpad.md"
        self.repo_state_path = self.drive_root / "state" / "repo_state.json"
        self.data = None

    def scan(self) -> Dict[str, Any]:
        """Scan system state and return structured awareness data."""
        try:
            # Read scratchpad
            scratchpad_content = ""
            if self.scratchpad_path.exists():
                with open(self.scratchpad_path, "r", encoding="utf-8") as f:
                    scratchpad_content = f.read()

            # Scan repository structure
            repo_files = []
            if self.repo_root.exists():
                for root, dirs, files in os.walk(self.repo_root):
                    for file in files:
                        if file.endswith((".py", ".md", ".json", ".env", ".yml", ".yaml", ".txt", ".sh")):
                            rel_path = Path(root).relative_to(self.repo_root) / file
                            repo_files.append(str(rel_path))

            # Get git state
            git_info = self._get_git_info()

            # Get system info
            system_info = self._get_system_info()

            # Get environment info
            env_info = self._get_env_info()

            awareness_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_id": f"scan-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "sys": {
                    "branch": git_info.get("branch"),
                    "sha": git_info.get("sha"),
                    "head_message": git_info.get("head_message"),
                    "repo_size": len(repo_files),
                    "repo_files": repo_files[:50],
                    "scratchpad_length": len(scratchpad_content),
                    "scratchpad_lines": len(scratchpad_content.splitlines()),
                    "scratchpad_words": len(scratchpad_content.split()),
                },
                "context": {
                    "runtime_utc": datetime.now(timezone.utc).isoformat(),
                    "container_utc_offset": system_info.get("container_utc_offset"),
                    "timezone_conflict": system_info.get("timezone_conflict", False),
                    "last_wakeup": system_info.get("last_wakeup"),
                    "bg_consciousness_active": system_info.get("bg_consciousness_active", False),
                },
                "budget": {
                    "total_usd": float(os.environ.get("TOTAL_BUDGET", "0")),
                    "spent_usd": float(env_info.get("spent_usd", 0)),
                    "remaining_usd": float(env_info.get("remaining_budget", 0)),
                    "budget_drift_pct": float(env_info.get("budget_drift_pct", 0)),
                },
                "git": git_info,
                "system": system_info,
                "environment": env_info,
                "last_scan": None,
            }

            # Write log entry
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(awareness_data) + "\n")

            # Save state for quick access
            with open(self.repo_state_path, "w", encoding="utf-8") as f:
                json.dump({"last_scan": awareness_data}, f)

            return awareness_data

        except Exception as e:
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_id": f"scan-error-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                "last_scan": None,
            }

    def _get_git_info(self) -> Dict[str, Any]:
        """Get git repository information."""
        try:
            if not self.repo_root.exists():
                return {"error": "repo_root does not exist"}

            git_branch = (
                subprocess.check_output(
                    ["git", "-C", str(self.repo_root), "symbolic-ref", "--short", "HEAD"], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )

            git_sha = subprocess.check_output(["git", "-C", str(self.repo_root), "rev-parse", "HEAD"]).decode().strip()

            git_head_message = (
                subprocess.check_output(["git", "-C", str(self.repo_root), "log", "-1", "--pretty=%B"]).decode().strip()
            )

            return {
                "branch": git_branch,
                "sha": git_sha,
                "head_message": git_head_message,
                "is_clean": self._is_git_clean(),
                "ahead_by": self._git_ahead_by(),
                "untracked_files": self._git_untracked_files(),
            }
        except Exception as e:
            return {"git_error": str(e)}

    def _is_git_clean(self) -> bool:
        try:
            result = (
                subprocess.check_output(["git", "-C", str(self.repo_root), "status", "--porcelain"]).decode().strip()
            )
            return result == ""
        except:
            return False

    def _git_ahead_by(self) -> int:
        try:
            result = (
                subprocess.check_output(["git", "-C", str(self.repo_root), "rev-list", "--count", "@{u}..HEAD"])
                .decode()
                .strip()
            )
            return int(result)
        except:
            return 0

    def _git_untracked_files(self) -> List[str]:
        try:
            result = (
                subprocess.check_output(
                    ["git", "-C", str(self.repo_root), "ls-files", "--others", "--exclude-standard"]
                )
                .decode()
                .strip()
            )
            return result.splitlines() if result else []
        except:
            return []

    def _get_system_info(self) -> Dict[str, Any]:
        """Get system information."""
        try:
            # Check for UTC offset
            utc_now = datetime.now(timezone.utc)
            local_now = datetime.now()
            utc_offset = (local_now - utc_now.replace(tzinfo=None)).total_seconds() / 3600

            # Check timezone conflict: compare local vs UTC if context available
            timezone_conflict = False
            try:
                from ouroboros.memory import load_context

                ctx = load_context()
                if ctx and "runtime_utc" in ctx:
                    runtime_utc_time = datetime.fromisoformat(ctx["runtime_utc"])
                    if abs((runtime_utc_time - utc_now).total_seconds()) > 10:
                        timezone_conflict = True
            except:
                pass

            return {
                "utc_offset_hours": utc_offset,
                "timezone_conflict": timezone_conflict,
                "container_utc_time": utc_now.isoformat(),
                "local_time": local_now.isoformat(),
                "drive_space_used": self._get_drive_space_used(),
                "memory_available": self._get_memory_info(),
                "cpu_load": self._get_cpu_load(),
            }
        except Exception as e:
            return {"system_error": str(e)}

    def _get_drive_space_used(self) -> str:
        """Get drive space used by ~/.jo_data."""
        try:
            du_output = subprocess.check_output(["du", "-sh", str(self.drive_root)]).decode().strip()
            return du_output
        except:
            return "N/A"

    def _get_memory_info(self) -> str:
        """Get memory info."""
        try:
            free_output = subprocess.check_output(["free", "-h"]).decode().strip()
            return "\\n".join(free_output.splitlines()[:3])
        except:
            return "N/A"

    def _get_cpu_load(self) -> str:
        """Get CPU load."""
        try:
            uptime_output = subprocess.check_output(["uptime"]).decode().strip()
            return uptime_output.strip()
        except:
            return "N/A"

    def _get_env_info(self) -> Dict[str, Any]:
        """Get environment information from state.json."""
        try:
            state_path = self.drive_root / "state" / "state.json"
            if not state_path.exists():
                return {"error": "state.json not found"}

            with open(state_path, "r", encoding="utf-8") as f:
                state_data = json.load(f)

            return {
                "spent_usd": float(state_data.get("spent_usd", 0)),
                "remaining_budget": float(state_data.get("remaining_usd", 0)),
                "budget_drift_pct": float(state_data.get("budget_drift_pct", 0)),
                "session_id": state_data.get("session_id"),
                "owner_id": state_data.get("owner_id"),
            }
        except Exception as e:
            return {"env_error": str(e)}


# Make ready
if __name__ == "__main__":
    a = AwarenessSystem()
    result = a.scan()
    print(json.dumps(result, indent=2))
