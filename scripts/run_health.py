import sys
import pathlib
from pathlib import Path

repo_dir = Path(r"c:\Users\JO\OneDrive\Desktop\jo")
ouroboros_dir = repo_dir / "ouroboros"
sys.path.insert(0, str(ouroboros_dir))

from tools.registry import ToolContext
from tools.health import _codebase_health

ctx = ToolContext(
    repo_dir=repo_dir,
    drive_root=repo_dir / "vault"
)

print(_codebase_health(ctx))
