import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from ouroboros.tools.core import get_tools
from ouroboros.utils import log


def store_task_result(task: Dict[str, Any], result_data: Dict[str, Any]) -> None:
    """Store task result to disk atomically."""
    results_dir = Path("logs") / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    result_file = results_dir / f"{task.get('id')}.json"
    tmp_file = results_dir / f"{task.get('id')}.json.tmp"
    
    # Fix Windows encoding issue: add explicit UTF-8 encoding
    tmp_file.write_text(json.dumps(result_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    os.rename(tmp_file, result_file)
    
    try:
        log.info("Stored task result for %s", task.get('id'))
    except Exception as e:
        log.warning("Failed to log task storage: %s", e)