#!/usr/bin/env python3
"""
Code Health Assessment Script
Uses the existing health infrastructure to analyze codebase violations.
"""

import os
import pathlib
import sys

# Add the ouroboros directory to the path
sys.path.insert(0, '/home/runner/work/jo/jo/ouroboros')

from tools.health import _codebase_health
from tools.registry import ToolContext

def main():
    """Run codebase health assessment."""
    # Create a mock ToolContext
    ctx = ToolContext(
        repo_dir="/home/runner/work/jo/jo",
        drive_root="/home/runner/.jo_data",
        tools_registry=None,
        logger=None
    )
    
    # Run the health assessment
    result = _codebase_health(ctx)
    print(result)

if __name__ == "__main__":
    main()