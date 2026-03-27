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
    import pathlib
    # Create a mock ToolContext with correct parameters
    ctx = ToolContext(
        repo_dir=pathlib.Path("/home/runner/work/jo/jo"),
        drive_root=pathlib.Path("/home/runner/.jo_data")
    )
    
    # Run the health assessment
    result = _codebase_health(ctx)
    print(result)

if __name__ == "__main__":
    main()