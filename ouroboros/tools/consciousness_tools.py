"""
Jo — Consciousness, Growth, and Disclosure Tools.

Tool wrappers for the new high-value systems:
1. Background consciousness
2. Three-axis growth tracking
3. Progressive skill disclosure
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


def _get_consciousness(repo_dir: pathlib.Path):
    from ouroboros.background_consciousness import get_consciousness

    return get_consciousness(repo_dir)


def _get_tracker(repo_dir: pathlib.Path):
    from ouroboros.three_axis_tracker import get_tracker

    return get_tracker(repo_dir)


def _get_disclosure(repo_dir: pathlib.Path):
    from ouroboros.progressive_disclosure import get_disclosure

    return get_disclosure(repo_dir)


def _consciousness_status(ctx: ToolContext) -> str:
    """Get background consciousness status."""
    consciousness = _get_consciousness(ctx.repo_dir)
    stats = consciousness.get_stats()
    return f"## Background Consciousness Status\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _consciousness_wake_up(ctx: ToolContext) -> str:
    """Wake up background consciousness and get prompt."""
    consciousness = _get_consciousness(ctx.repo_dir)
    if consciousness.should_wake_up():
        prompt = consciousness.get_consciousness_prompt()
        return f"## Consciousness Activated\n\n{prompt}"
    return "⏭️ Consciousness not ready yet. Check status for timing."


def _consciousness_record_action(ctx: ToolContext, action: str, result: str = "") -> str:
    """Record a proactive action taken by consciousness."""
    consciousness = _get_consciousness(ctx.repo_dir)
    consciousness.record_action(action, result)
    return f"✅ Action recorded: {action}"


def _growth_record_technical(ctx: ToolContext, metric: str, value: float, context: str = "", notes: str = "") -> str:
    """Record technical growth metric."""
    tracker = _get_tracker(ctx.repo_dir)
    tracker.record_technical_growth(metric, value, context, notes)
    return f"✅ Technical growth recorded: {metric} = {value}"


def _growth_record_cognitive(ctx: ToolContext, metric: str, value: float, context: str = "", notes: str = "") -> str:
    """Record cognitive growth metric."""
    tracker = _get_tracker(ctx.repo_dir)
    tracker.record_cognitive_growth(metric, value, context, notes)
    return f"✅ Cognitive growth recorded: {metric} = {value}"


def _growth_record_existential(ctx: ToolContext, metric: str, value: float, context: str = "", notes: str = "") -> str:
    """Record existential growth metric."""
    tracker = _get_tracker(ctx.repo_dir)
    tracker.record_existential_growth(metric, value, context, notes)
    return f"✅ Existential growth recorded: {metric} = {value}"


def _growth_report(ctx: ToolContext) -> str:
    """Get comprehensive three-axis growth report."""
    tracker = _get_tracker(ctx.repo_dir)
    return tracker.get_growth_report()


def _growth_stats(ctx: ToolContext) -> str:
    """Get growth tracking statistics."""
    tracker = _get_tracker(ctx.repo_dir)
    stats = tracker.get_stats()
    return f"## Growth Tracking Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _disclosure_record_access(ctx: ToolContext, file_path: str) -> str:
    """Record file access and reveal matching skills."""
    disclosure = _get_disclosure(ctx.repo_dir)
    newly_revealed = disclosure.record_file_access(file_path)
    if newly_revealed:
        return f"✅ File access recorded: {file_path}\nNewly revealed skills: {', '.join(newly_revealed)}"
    return f"✅ File access recorded: {file_path} (no new skills revealed)"


def _disclosure_visible_skills(ctx: ToolContext) -> str:
    """Get currently visible skills."""
    disclosure = _get_disclosure(ctx.repo_dir)
    return disclosure.get_skill_context()


def _disclosure_stats(ctx: ToolContext) -> str:
    """Get progressive disclosure statistics."""
    disclosure = _get_disclosure(ctx.repo_dir)
    stats = disclosure.get_stats()
    return f"## Progressive Disclosure Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def get_tools() -> List[ToolEntry]:
    """Get consciousness, growth, and disclosure tools."""
    return [
        ToolEntry(
            "consciousness_status",
            {
                "name": "consciousness_status",
                "description": "Get background consciousness status and timing.",
                "parameters": {"type": "object", "properties": {}},
            },
            _consciousness_status,
        ),
        ToolEntry(
            "consciousness_wake_up",
            {
                "name": "consciousness_wake_up",
                "description": "Wake up background consciousness and get reflection prompt.",
                "parameters": {"type": "object", "properties": {}},
            },
            _consciousness_wake_up,
        ),
        ToolEntry(
            "consciousness_record_action",
            {
                "name": "consciousness_record_action",
                "description": "Record a proactive action taken by consciousness.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string", "description": "Action taken"},
                        "result": {"type": "string", "default": "", "description": "Result of action"},
                    },
                    "required": ["action"],
                },
            },
            _consciousness_record_action,
        ),
        ToolEntry(
            "growth_record_technical",
            {
                "name": "growth_record_technical",
                "description": "Record technical growth metric.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "Metric name"},
                        "value": {"type": "number", "description": "Metric value"},
                        "context": {"type": "string", "default": "", "description": "Context"},
                        "notes": {"type": "string", "default": "", "description": "Notes"},
                    },
                    "required": ["metric", "value"],
                },
            },
            _growth_record_technical,
        ),
        ToolEntry(
            "growth_record_cognitive",
            {
                "name": "growth_record_cognitive",
                "description": "Record cognitive growth metric.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "Metric name"},
                        "value": {"type": "number", "description": "Metric value"},
                        "context": {"type": "string", "default": "", "description": "Context"},
                        "notes": {"type": "string", "default": "", "description": "Notes"},
                    },
                    "required": ["metric", "value"],
                },
            },
            _growth_record_cognitive,
        ),
        ToolEntry(
            "growth_record_existential",
            {
                "name": "growth_record_existential",
                "description": "Record existential growth metric.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "metric": {"type": "string", "description": "Metric name"},
                        "value": {"type": "number", "description": "Metric value"},
                        "context": {"type": "string", "default": "", "description": "Context"},
                        "notes": {"type": "string", "default": "", "description": "Notes"},
                    },
                    "required": ["metric", "value"],
                },
            },
            _growth_record_existential,
        ),
        ToolEntry(
            "growth_report",
            {
                "name": "growth_report",
                "description": "Get comprehensive three-axis growth report.",
                "parameters": {"type": "object", "properties": {}},
            },
            _growth_report,
        ),
        ToolEntry(
            "growth_stats",
            {
                "name": "growth_stats",
                "description": "Get growth tracking statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _growth_stats,
        ),
        ToolEntry(
            "disclosure_record_access",
            {
                "name": "disclosure_record_access",
                "description": "Record file access and reveal matching skills.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "File path accessed"},
                    },
                    "required": ["file_path"],
                },
            },
            _disclosure_record_access,
        ),
        ToolEntry(
            "disclosure_visible_skills",
            {
                "name": "disclosure_visible_skills",
                "description": "Get currently visible skills.",
                "parameters": {"type": "object", "properties": {}},
            },
            _disclosure_visible_skills,
        ),
        ToolEntry(
            "disclosure_stats",
            {
                "name": "disclosure_stats",
                "description": "Get progressive disclosure statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _disclosure_stats,
        ),
    ]
