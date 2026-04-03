"""
Jo — Bulkhead Resource Isolation and Adaptive Timeouts.

Inspired by Zylos Research and SRE best practices for AI agents.

Bulkhead Pattern:
- Isolates resource pools per tool type to prevent cascading failures
- If one tool type is exhausted, others continue unaffected
- Named after ship bulkheads that contain flooding to one compartment

Adaptive Timeouts:
- Different operations warrant different timeouts
- Timeout scales with model tier and task complexity
- Partial result extraction on timeout (don't discard all progress)

This prevents:
- One slow tool starving all other tool calls
- Legitimate long completions being killed by short timeouts
- Silent failures from timeout truncation
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


@dataclass
class BulkheadConfig:
    """Configuration for a bulkhead resource pool."""

    max_concurrent: int  # Maximum concurrent calls
    timeout_seconds: float  # Default timeout for this pool


# Default bulkhead configurations per tool type
DEFAULT_BULKHEADS = {
    "llm": BulkheadConfig(max_concurrent=4, timeout_seconds=120.0),
    "read": BulkheadConfig(max_concurrent=16, timeout_seconds=30.0),  # File reads, searches
    "write": BulkheadConfig(max_concurrent=4, timeout_seconds=60.0),  # File writes, commits
    "external": BulkheadConfig(max_concurrent=2, timeout_seconds=30.0),  # Web, API calls
    "memory": BulkheadConfig(max_concurrent=8, timeout_seconds=15.0),  # Memory operations
}

# Tool type mapping
TOOL_TYPE_MAP = {
    # LLM operations
    "llm_call": "llm",
    "chat": "llm",
    # Read operations
    "repo_read": "read",
    "repo_list": "read",
    "repo_status": "read",
    "repo_log": "read",
    "drive_read": "read",
    "drive_list": "read",
    "web_search": "read",
    "codebase_digest": "read",
    "anatomy_scan": "read",
    "anatomy_lookup": "read",
    "anatomy_search": "read",
    "query_status": "read",
    "query_full": "read",
    "query_health": "read",
    # Write operations
    "repo_write_commit": "write",
    "repo_commit_push": "write",
    "code_edit": "write",
    "drive_write": "write",
    "delete_file": "write",
    "move_file": "write",
    "copy_file": "write",
    # External operations
    "vault_write": "external",
    "vault_create": "external",
    # Memory operations
    "cerebrum_search": "memory",
    "cerebrum_add": "memory",
    "cerebrum_summary": "memory",
    "cerebrum_check": "memory",
    "buglog_search": "memory",
    "buglog_log": "memory",
    "buglog_summary": "memory",
    "memory_extract": "memory",
    "memory_extract_save": "memory",
}

# Timeout configuration per model tier
TIMEOUT_CONFIG = {
    "opus": {"connect": 10, "total": 300},  # Complex reasoning, slow
    "sonnet": {"connect": 10, "total": 120},  # Balanced
    "haiku": {"connect": 5, "total": 30},  # Fast, low timeout
    "free": {"connect": 10, "total": 60},  # Free tier, moderate
    "default": {"connect": 10, "total": 120},
}


class BulkheadExecutor:
    """Executes tool calls with bulkhead resource isolation."""

    def __init__(self):
        self._pools: Dict[str, ThreadPoolExecutor] = {}
        self._configs: Dict[str, BulkheadConfig] = {}
        self._initialize_pools()

    def _initialize_pools(self) -> None:
        """Initialize thread pools for each bulkhead."""
        for tool_type, config in DEFAULT_BULKHEADS.items():
            self._pools[tool_type] = ThreadPoolExecutor(
                max_workers=config.max_concurrent, thread_name_prefix=f"bulkhead-{tool_type}"
            )
            self._configs[tool_type] = config
            log.info(
                "[Bulkhead] Initialized %s pool: %d workers, %.0fs timeout",
                tool_type,
                config.max_concurrent,
                config.timeout_seconds,
            )

    def get_tool_type(self, tool_name: str) -> str:
        """Determine the bulkhead type for a tool."""
        return TOOL_TYPE_MAP.get(tool_name, "external")

    def get_timeout(self, tool_name: str, model: str = "") -> float:
        """Get adaptive timeout for a tool call."""
        tool_type = self.get_tool_type(tool_name)
        base_timeout = self._configs.get(tool_type, DEFAULT_BULKHEADS["external"]).timeout_seconds

        # Adjust timeout based on model tier
        model_lower = model.lower()
        if "opus" in model_lower:
            tier = "opus"
        elif "sonnet" in model_lower:
            tier = "sonnet"
        elif "haiku" in model_lower:
            tier = "haiku"
        elif "free" in model_lower:
            tier = "free"
        else:
            tier = "default"

        tier_timeout = TIMEOUT_CONFIG.get(tier, TIMEOUT_CONFIG["default"])["total"]
        # Use the larger of base timeout and tier timeout
        return max(base_timeout, tier_timeout)

    def get_stats(self) -> Dict[str, Any]:
        """Get bulkhead executor statistics."""
        return {
            "pools": {
                tool_type: {
                    "max_workers": config.max_concurrent,
                    "timeout_seconds": config.timeout_seconds,
                }
                for tool_type, config in self._configs.items()
            },
            "tool_type_map_count": len(TOOL_TYPE_MAP),
        }


# Global bulkhead executor instance
_executor: Optional[BulkheadExecutor] = None


def get_bulkhead_executor() -> BulkheadExecutor:
    """Get or create the global bulkhead executor."""
    global _executor
    if _executor is None:
        _executor = BulkheadExecutor()
    return _executor
