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


def _capability_detect_gaps(ctx: ToolContext, task_text: str) -> str:
    """Detect capability gaps in a task description."""
    from ouroboros.capability_gap import get_gap_detector

    detector = get_gap_detector(ctx.repo_dir)
    return detector.get_gap_report(task_text)


def _capability_stats(ctx: ToolContext) -> str:
    """Get capability gap detection statistics."""
    from ouroboros.capability_gap import get_gap_detector

    detector = get_gap_detector(ctx.repo_dir)
    stats = detector.get_stats()
    return f"## Capability Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _modification_start(ctx: ToolContext, target: str, trigger: str, description: str, justification: str) -> str:
    """Start a new self-modification pipeline."""
    from ouroboros.modification_pipeline import get_modification_pipeline

    pipeline = get_modification_pipeline(ctx.repo_dir)
    record = pipeline.start_modification(target, trigger, description, justification)
    return f"## Modification Started\n\nID: {record.id}\nTarget: {target}\nTrigger: {trigger}\nStage: {record.stage.value}\nRollback SHA: {record.rollback_sha}"


def _modification_validate(ctx: ToolContext) -> str:
    """Validate the current modification."""
    from ouroboros.modification_pipeline import get_modification_pipeline

    pipeline = get_modification_pipeline(ctx.repo_dir)
    passed = pipeline.validate_change()
    return f"## Validation {'PASSED' if passed else 'FAILED'}\n\nAll checks must pass before applying."


def _modification_apply(ctx: ToolContext, commit_message: str) -> str:
    """Apply the validated modification."""
    from ouroboros.modification_pipeline import get_modification_pipeline

    pipeline = get_modification_pipeline(ctx.repo_dir)
    passed = pipeline.apply_change(commit_message)
    return f"## Modification {'APPLIED' if passed else 'FAILED'}\n\n{commit_message}"


def _modification_verify(ctx: ToolContext) -> str:
    """Verify the applied modification."""
    from ouroboros.modification_pipeline import get_modification_pipeline

    pipeline = get_modification_pipeline(ctx.repo_dir)
    passed = pipeline.verify_change()
    return f"## Verification {'PASSED' if passed else 'FAILED - ROLLED BACK'}"


def _modification_history(ctx: ToolContext) -> str:
    """Get modification history."""
    from ouroboros.modification_pipeline import get_modification_pipeline

    pipeline = get_modification_pipeline(ctx.repo_dir)
    history = pipeline.get_history()
    stats = pipeline.get_stats()
    return f"## Modification History\n\n**Stats**: {json.dumps(stats, indent=2)}\n\n**Records**:\n" + "\n".join(
        f"- {r['id']}: {r['target']} ({r['status']})" for r in history[-10:]
    )


def _outreach_queue(ctx: ToolContext, type: str, content: str, priority: float = 0.5) -> str:
    """Queue a proactive outreach message."""
    from ouroboros.proactive_outreach import get_outreach, OutreachType

    outreach = get_outreach(ctx.repo_dir)
    type_enum = {
        "insight": OutreachType.INSIGHT,
        "alert": OutreachType.ALERT,
        "progress": OutreachType.PROGRESS,
        "question": OutreachType.QUESTION,
        "suggestion": OutreachType.SUGGESTION,
    }.get(type.lower(), OutreachType.INSIGHT)

    if type_enum == OutreachType.INSIGHT:
        outreach.queue_insight(content, priority)
    elif type_enum == OutreachType.ALERT:
        outreach.queue_alert(content, priority)
    elif type_enum == OutreachType.PROGRESS:
        outreach.queue_progress(content, priority)
    elif type_enum == OutreachType.QUESTION:
        outreach.queue_question(content, priority)
    elif type_enum == OutreachType.SUGGESTION:
        outreach.queue_suggestion(content, priority)

    return f"✅ {type.title()} message queued (priority {priority})"


def _outreach_pending(ctx: ToolContext) -> str:
    """Get pending outreach messages."""
    from ouroboros.proactive_outreach import get_outreach

    outreach = get_outreach(ctx.repo_dir)
    return outreach.format_outreach_summary() or "No pending outreach messages."


def _outreach_stats(ctx: ToolContext) -> str:
    """Get outreach statistics."""
    from ouroboros.proactive_outreach import get_outreach

    outreach = get_outreach(ctx.repo_dir)
    stats = outreach.get_stats()
    return f"## Outreach Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


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
        ToolEntry(
            "capability_detect_gaps",
            {
                "name": "capability_detect_gaps",
                "description": "Detect capability gaps in a task description before execution.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_text": {"type": "string", "description": "Task description to analyze"},
                    },
                    "required": ["task_text"],
                },
            },
            _capability_detect_gaps,
        ),
        ToolEntry(
            "capability_stats",
            {
                "name": "capability_stats",
                "description": "Get capability gap detection statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _capability_stats,
        ),
        ToolEntry(
            "modification_start",
            {
                "name": "modification_start",
                "description": "Start a new self-modification pipeline (Stage 1: DETECT).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {"type": "string", "description": "What is being modified"},
                        "trigger": {"type": "string", "description": "Why this modification was triggered"},
                        "description": {"type": "string", "description": "What the change does"},
                        "justification": {"type": "string", "description": "Why this change is needed"},
                    },
                    "required": ["target", "trigger", "description", "justification"],
                },
            },
            _modification_start,
        ),
        ToolEntry(
            "modification_validate",
            {
                "name": "modification_validate",
                "description": "Validate the current modification (Stage 3: VALIDATE).",
                "parameters": {"type": "object", "properties": {}},
            },
            _modification_validate,
        ),
        ToolEntry(
            "modification_apply",
            {
                "name": "modification_apply",
                "description": "Apply the validated modification (Stage 4: APPLY).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "commit_message": {"type": "string", "description": "Git commit message"},
                    },
                    "required": ["commit_message"],
                },
            },
            _modification_apply,
        ),
        ToolEntry(
            "modification_verify",
            {
                "name": "modification_verify",
                "description": "Verify the applied modification (Stage 5: VERIFY).",
                "parameters": {"type": "object", "properties": {}},
            },
            _modification_verify,
        ),
        ToolEntry(
            "modification_history",
            {
                "name": "modification_history",
                "description": "Get modification history and statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _modification_history,
        ),
        ToolEntry(
            "outreach_queue",
            {
                "name": "outreach_queue",
                "description": "Queue a proactive outreach message to creator.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "description": "Message type: insight, alert, progress, question, suggestion",
                        },
                        "content": {"type": "string", "description": "Message content"},
                        "priority": {"type": "number", "default": 0.5, "description": "Priority 0.0-1.0"},
                    },
                    "required": ["type", "content"],
                },
            },
            _outreach_queue,
        ),
        ToolEntry(
            "outreach_pending",
            {
                "name": "outreach_pending",
                "description": "Get pending outreach messages.",
                "parameters": {"type": "object", "properties": {}},
            },
            _outreach_pending,
        ),
        ToolEntry(
            "outreach_stats",
            {
                "name": "outreach_stats",
                "description": "Get outreach statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _outreach_stats,
        ),
    ]
