from pathlib import Path
from typing import Dict
import json

# Define the Drive root directory
DRIVE_ROOT = Path.home() / ".ouroboros"

def load_state() -> Dict:
    state_path = DRIVE_ROOT / "state" / "state.json"
    try:
        with open(state_path, "r") as f:
            state = json.load(f)
    except FileNotFoundError:
        state = {}
    return state
