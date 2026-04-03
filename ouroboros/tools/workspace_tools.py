"""
Jo — Workspace Organizer Tools.

Tool wrappers for workspace organization system.
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolEntry
from ouroboros.tools.context import ToolContext

log = logging.getLogger(__name__)


def _get_organizer(repo_dir: pathlib.Path):
    from ouroboros.workspace_organizer import get_organizer

    return get_organizer(repo_dir)


def _workspace_analyze(ctx: ToolContext) -> str:
    """Analyze workspace organization health."""
    organizer = _get_organizer(ctx.repo_dir)
    report = organizer.analyze()
    return organizer.generate_workspace_summary()


def _workspace_cleanup_vault(ctx: ToolContext, dry_run: bool = True) -> str:
    """Clean up auto-generated tool documentation in vault."""
    organizer = _get_organizer(ctx.repo_dir)
    result = organizer.cleanup_vault_tools(dry_run=dry_run)
    return f"## Vault Cleanup Result\n\n```json\n{json.dumps(result, indent=2)}\n```"


def _workspace_consolidate_memory(ctx: ToolContext, dry_run: bool = True) -> str:
    """Consolidate memory files according to BIBLE.md principles."""
    organizer = _get_organizer(ctx.repo_dir)
    result = organizer.consolidate_memory(dry_run=dry_run)
    return f"## Memory Consolidation Result\n\n```json\n{json.dumps(result, indent=2)}\n```"


def _workspace_sync_tools(ctx: ToolContext, dry_run: bool = True) -> str:
    """Ensure all active tools have vault documentation."""
    organizer = _get_organizer(ctx.repo_dir)
    result = organizer.sync_tools_to_vault(dry_run=dry_run)
    return f"## Tool Vault Sync Result\n\n```json\n{json.dumps(result, indent=2)}\n```"


def _workspace_summary(ctx: ToolContext) -> str:
    """Generate a comprehensive workspace summary."""
    organizer = _get_organizer(ctx.repo_dir)
    return organizer.generate_workspace_summary()


def get_tools() -> List[ToolEntry]:
    """Get workspace organizer tools."""
    return [
        ToolEntry(
            "workspace_analyze",
            {
                "name": "workspace_analyze",
                "description": "Analyze workspace organization health and get recommendations.",
                "parameters": {"type": "object", "properties": {}},
            },
            _workspace_analyze,
        ),
        ToolEntry(
            "workspace_cleanup_vault",
            {
                "name": "workspace_cleanup_vault",
                "description": "Clean up auto-generated tool documentation in vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dry_run": {
                            "type": "boolean",
                            "default": True,
                            "description": "Preview changes without applying",
                        },
                    },
                },
            },
            _workspace_cleanup_vault,
        ),
        ToolEntry(
            "workspace_consolidate_memory",
            {
                "name": "workspace_consolidate_memory",
                "description": "Consolidate memory files according to BIBLE.md principles.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dry_run": {
                            "type": "boolean",
                            "default": True,
                            "description": "Preview changes without applying",
                        },
                    },
                },
            },
            _workspace_consolidate_memory,
        ),
        ToolEntry(
            "workspace_sync_tools",
            {
                "name": "workspace_sync_tools",
                "description": "Ensure all active tools have vault documentation.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "dry_run": {
                            "type": "boolean",
                            "default": True,
                            "description": "Preview changes without applying",
                        },
                    },
                },
            },
            _workspace_sync_tools,
        ),
        ToolEntry(
            "workspace_summary",
            {
                "name": "workspace_summary",
                "description": "Generate a comprehensive workspace summary.",
                "parameters": {"type": "object", "properties": {}},
            },
            _workspace_summary,
        ),
    ]
