"""Internal token compression for Jo (Ouroboros).

Provides utilities to filter and truncate tool outputs to save tokens
without losing critical information.
"""

from __future__ import annotations

import re
import logging
from typing import List, Optional

log = logging.getLogger(__name__)

# Regex for ANSI escape codes
ANSI_ESCAPE = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')

def strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    return ANSI_ESCAPE.sub('', text)

def collapse_repetitive_lines(text: str, max_repeat: int = 3) -> str:
    """Collapse consecutive identical lines."""
    lines = text.splitlines()
    if not lines:
        return text
    
    compacted = []
    current_line = None
    count = 0
    
    for line in lines:
        stripped = line.strip()
        if stripped == current_line:
            count += 1
        else:
            if count > max_repeat:
                compacted.append(f"... [{count - max_repeat} identical lines omitted] ...")
            elif current_line is not None:
                compacted.extend([current_line] * max_repeat if count >= max_repeat else [current_line] * count)
            
            current_line = stripped
            count = 1
            compacted.append(line)
            
    if count > max_repeat:
        compacted.append(f"... [{count - max_repeat} identical lines omitted] ...")
        
    return "\n".join(compacted)

def smart_truncate(text: str, max_chars: int = 4000) -> str:
    """Heuristic truncation that preserves headers and footers."""
    if len(text) <= max_chars:
        return text
    
    # Preserve first 1500 and last 1000 characters
    head_len = int(max_chars * 0.4)
    tail_len = int(max_chars * 0.3)
    
    head = text[:head_len]
    tail = text[-tail_len:]
    
    return f"{head}\n\n... [TRUNCATED {len(text) - max_chars} characters] ...\n\n{tail}"

def compress_shell_output(text: str, command: Optional[str] = None) -> str:
    """Main entry point for compressing shell/command output."""
    clean_text = strip_ansi(text)
    
    # Specific logic per command if needed
    if command:
        cmd_lower = command.lower()
        if "git status" in cmd_lower:
            # Git status is usually short, but if long, we want the changed files
            pass
        elif "pytest" in cmd_lower or "test" in cmd_lower:
            # For tests, we want to keep failures
            if "FAILURES" in clean_text or "ERRORS" in clean_text:
                # Keep the failure summary
                pass
    
    compacted = collapse_repetitive_lines(clean_text)
    return smart_truncate(compacted)

def get_compression_stats(original: str, compressed: str) -> dict:
    """Compute reduction statistics."""
    orig_len = len(original)
    comp_len = len(compressed)
    reduction = (1 - comp_len / orig_len) * 100 if orig_len > 0 else 0
    return {
        "original_chars": orig_len,
        "compressed_chars": comp_len,
        "reduction_pct": round(reduction, 2)
    }
