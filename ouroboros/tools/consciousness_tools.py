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


def _identity_verify(ctx: ToolContext) -> str:
    """Verify identity integrity (tamper detection)."""
    from ouroboros.persistent_identity import get_persistent_identity

    identity = get_persistent_identity(ctx.repo_dir)
    verification = identity.verify_identity()
    status = "✅ VERIFIED" if verification["valid"] else "❌ TAMPERED"
    return f"## Identity Verification\n\n**Status**: {status}\n**Version**: {verification['version']}\n**Message**: {verification['message']}"


def _identity_history(ctx: ToolContext) -> str:
    """Get identity version history."""
    from ouroboros.persistent_identity import get_persistent_identity

    identity = get_persistent_identity(ctx.repo_dir)
    history = identity.get_history()
    return f"## Identity History\n\n" + "\n".join(
        f"- v{h['version']}: {h['timestamp']} - {h['reason']}" for h in history
    )


def _identity_stats(ctx: ToolContext) -> str:
    """Get persistent identity statistics."""
    from ouroboros.persistent_identity import get_persistent_identity

    identity = get_persistent_identity(ctx.repo_dir)
    stats = identity.get_stats()
    return f"## Identity Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _self_healing_detect(ctx: ToolContext) -> str:
    """Run self-healing detection."""
    from ouroboros.self_healing import get_self_healing

    healing = get_self_healing(ctx.repo_dir)
    issues = healing.auto_heal()
    if issues:
        return f"## Self-Healing Detection\n\nFound {len(issues)} issue(s):\n" + "\n".join(
            f"- {i.id}: {i.type.value} at {i.file_path}:{i.line_number}" for i in issues
        )
    return "✅ No issues detected"


def _self_healing_diagnose(ctx: ToolContext, issue_id: str) -> str:
    """Diagnose a specific issue."""
    from ouroboros.self_healing import get_self_healing

    healing = get_self_healing(ctx.repo_dir)
    issue = healing.diagnose_issue(issue_id)
    return f"## Issue Diagnosis\n\n**ID**: {issue.id}\n**Type**: {issue.type.value}\n**Status**: {issue.status.value}\n**File**: {issue.file_path}\n**Diagnosis**: {issue.diagnosis}\n**Fix**: {issue.fix_applied}"


def _self_healing_stats(ctx: ToolContext) -> str:
    """Get self-healing statistics."""
    from ouroboros.self_healing import get_self_healing

    healing = get_self_healing(ctx.repo_dir)
    stats = healing.get_stats()
    return f"## Self-Healing Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _compaction_status(ctx: ToolContext) -> str:
    """Get context compaction status."""
    from ouroboros.context_compaction import get_compaction

    compaction = get_compaction(ctx.repo_dir)
    stats = compaction.get_stats()
    return f"## Context Compaction Status\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _compaction_reset_circuit(ctx: ToolContext) -> str:
    """Reset the compaction circuit breaker."""
    from ouroboros.context_compaction import get_compaction

    compaction = get_compaction(ctx.repo_dir)
    compaction.reset_circuit_breaker()
    return "✅ Compaction circuit breaker reset"


def _tot_create_tree(ctx: ToolContext, root_content: str, max_depth: int = 3, max_branches: int = 3) -> str:
    """Create a new tree of thoughts for complex reasoning."""
    from ouroboros.tree_of_thought import get_tot_reasoner

    reasoner = get_tot_reasoner(ctx.repo_dir)
    tree = reasoner.create_tree(root_content, max_depth, max_branches)
    return f"## Tree of Thoughts Created\n\nID: {tree.root_id}\nRoot: {root_content[:100]}\nMax depth: {max_depth}\nMax branches: {max_branches}"


def _tot_expand(ctx: ToolContext, tree_id: str, node_id: str, children: str, scores: str) -> str:
    """Expand a node with child thoughts."""
    from ouroboros.tree_of_thought import get_tot_reasoner
    import json

    reasoner = get_tot_reasoner(ctx.repo_dir)
    children_list = json.loads(children) if isinstance(children, str) else children
    scores_list = json.loads(scores) if isinstance(scores, str) else scores
    success = reasoner.expand_node(tree_id, node_id, children_list, scores_list)
    return f"✅ Node expanded: {success}"


def _tot_prune(ctx: ToolContext, tree_id: str, threshold: float = 0.3) -> str:
    """Prune weak branches from a tree."""
    from ouroboros.tree_of_thought import get_tot_reasoner

    reasoner = get_tot_reasoner(ctx.repo_dir)
    pruned = reasoner.prune_weak_branches(tree_id, threshold)
    return f"✅ Pruned {pruned} weak branches"


def _tot_select_best(ctx: ToolContext, tree_id: str) -> str:
    """Select the best path through a tree."""
    from ouroboros.tree_of_thought import get_tot_reasoner

    reasoner = get_tot_reasoner(ctx.repo_dir)
    path = reasoner.select_best_path(tree_id)
    return f"## Best Path Selected\n\nPath: {' -> '.join(path)}"


def _tot_stats(ctx: ToolContext) -> str:
    """Get tree-of-thought statistics."""
    from ouroboros.tree_of_thought import get_tot_reasoner

    reasoner = get_tot_reasoner(ctx.repo_dir)
    stats = reasoner.get_stats()
    return f"## Tree-of-Thought Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


def _memory_create_todo(ctx: ToolContext, content: str, parent_id: str = "") -> str:
    """Create a new todo in working memory."""
    from ouroboros.working_memory import get_working_memory

    memory = get_working_memory(ctx.repo_dir)
    todo_id = memory.create_todo(content, parent_id if parent_id else None)
    return f"✅ Todo created: {todo_id}"


def _memory_update_todo(ctx: ToolContext, todo_id: str, status: str = "", notes: str = "", content: str = "") -> str:
    """Update a todo in working memory."""
    from ouroboros.working_memory import get_working_memory, TodoStatus

    memory = get_working_memory(ctx.repo_dir)
    status_enum = {
        "pending": TodoStatus.PENDING,
        "in_progress": TodoStatus.IN_PROGRESS,
        "completed": TodoStatus.COMPLETED,
        "failed": TodoStatus.FAILED,
        "cancelled": TodoStatus.CANCELLED,
    }.get(status.lower(), None)
    success = memory.update_todo(
        todo_id,
        status=status_enum,
        notes=notes if notes else None,
        content=content if content else None,
    )
    return f"✅ Todo updated: {success}"


def _memory_view(ctx: ToolContext) -> str:
    """View the current working memory (todo tree)."""
    from ouroboros.working_memory import get_working_memory

    memory = get_working_memory(ctx.repo_dir)
    return memory.format_todos()


def _memory_progress(ctx: ToolContext) -> str:
    """Get working memory progress."""
    from ouroboros.working_memory import get_working_memory

    memory = get_working_memory(ctx.repo_dir)
    progress = memory.get_progress()
    return f"## Working Memory Progress\n\n```json\n{json.dumps(progress, indent=2)}\n```"


def _memory_clear_completed(ctx: ToolContext) -> str:
    """Clear completed todos from working memory."""
    from ouroboros.working_memory import get_working_memory

    memory = get_working_memory(ctx.repo_dir)
    cleared = memory.clear_completed()
    return f"✅ Cleared {cleared} completed todos"


def _critique_evaluate(ctx: ToolContext, task_description: str, work_summary: str, threshold: float = 0.7) -> str:
    """Start a self-critique evaluation."""
    from ouroboros.self_critique import get_self_critique_evaluator

    evaluator = get_self_critique_evaluator(ctx.repo_dir)
    critique = evaluator.evaluate(task_description, work_summary, [], threshold)
    prompt = evaluator.get_critique_prompt(critique.id)
    return f"## Self-Critique Started\n\nID: {critique.id}\nThreshold: {threshold}\n\nUse this prompt to evaluate:\n\n{prompt}"


def _critique_update_dimension(
    ctx: ToolContext, critique_id: str, dimension: str, score: float, issues: str = "", recommendations: str = ""
) -> str:
    """Update a critique dimension score."""
    from ouroboros.self_critique import get_self_critique_evaluator

    evaluator = get_self_critique_evaluator(ctx.repo_dir)
    issues_list = [i.strip() for i in issues.split("|") if i.strip()] if issues else []
    recs_list = [r.strip() for r in recommendations.split("|") if r.strip()] if recommendations else []
    success = evaluator.update_dimension(critique_id, dimension, score, issues_list, recs_list)
    return f"✅ Dimension updated: {success}"


def _critique_stats(ctx: ToolContext) -> str:
    """Get self-critique statistics."""
    from ouroboros.self_critique import get_self_critique_evaluator

    evaluator = get_self_critique_evaluator(ctx.repo_dir)
    stats = evaluator.get_stats()
    return f"## Self-Critique Statistics\n\n```json\n{json.dumps(stats, indent=2)}\n```"


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
        ToolEntry(
            "identity_verify",
            {
                "name": "identity_verify",
                "description": "Verify identity integrity (tamper detection).",
                "parameters": {"type": "object", "properties": {}},
            },
            _identity_verify,
        ),
        ToolEntry(
            "identity_history",
            {
                "name": "identity_history",
                "description": "Get identity version history.",
                "parameters": {"type": "object", "properties": {}},
            },
            _identity_history,
        ),
        ToolEntry(
            "identity_stats",
            {
                "name": "identity_stats",
                "description": "Get persistent identity statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _identity_stats,
        ),
        ToolEntry(
            "self_healing_detect",
            {
                "name": "self_healing_detect",
                "description": "Run self-healing detection (syntax, imports, tests).",
                "parameters": {"type": "object", "properties": {}},
            },
            _self_healing_detect,
        ),
        ToolEntry(
            "self_healing_diagnose",
            {
                "name": "self_healing_diagnose",
                "description": "Diagnose a specific issue.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "issue_id": {"type": "string", "description": "Issue ID to diagnose"},
                    },
                    "required": ["issue_id"],
                },
            },
            _self_healing_diagnose,
        ),
        ToolEntry(
            "self_healing_stats",
            {
                "name": "self_healing_stats",
                "description": "Get self-healing statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _self_healing_stats,
        ),
        ToolEntry(
            "compaction_status",
            {
                "name": "compaction_status",
                "description": "Get context compaction status and statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _compaction_status,
        ),
        ToolEntry(
            "compaction_reset_circuit",
            {
                "name": "compaction_reset_circuit",
                "description": "Reset the compaction circuit breaker after failures.",
                "parameters": {"type": "object", "properties": {}},
            },
            _compaction_reset_circuit,
        ),
        # Tree-of-Thought tools
        ToolEntry(
            "tot_create_tree",
            {
                "name": "tot_create_tree",
                "description": "Create a new tree of thoughts for complex reasoning (Yao et al. 2023).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "root_content": {"type": "string", "description": "Root problem/thought"},
                        "max_depth": {"type": "integer", "default": 3, "description": "Max tree depth"},
                        "max_branches": {"type": "integer", "default": 3, "description": "Max branches per node"},
                    },
                    "required": ["root_content"],
                },
            },
            _tot_create_tree,
        ),
        ToolEntry(
            "tot_expand",
            {
                "name": "tot_expand",
                "description": "Expand a node with child thoughts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tree_id": {"type": "string", "description": "Tree ID"},
                        "node_id": {"type": "string", "description": "Node ID to expand"},
                        "children": {"type": "string", "description": "JSON array of child thoughts"},
                        "scores": {"type": "string", "description": "JSON array of scores (0.0-1.0)"},
                    },
                    "required": ["tree_id", "node_id", "children", "scores"],
                },
            },
            _tot_expand,
        ),
        ToolEntry(
            "tot_prune",
            {
                "name": "tot_prune",
                "description": "Prune weak branches from a tree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tree_id": {"type": "string", "description": "Tree ID"},
                        "threshold": {"type": "number", "default": 0.3, "description": "Score threshold"},
                    },
                    "required": ["tree_id"],
                },
            },
            _tot_prune,
        ),
        ToolEntry(
            "tot_select_best",
            {
                "name": "tot_select_best",
                "description": "Select the best path through a tree.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tree_id": {"type": "string", "description": "Tree ID"},
                    },
                    "required": ["tree_id"],
                },
            },
            _tot_select_best,
        ),
        ToolEntry(
            "tot_stats",
            {
                "name": "tot_stats",
                "description": "Get tree-of-thought statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _tot_stats,
        ),
        # Working Memory tools
        ToolEntry(
            "memory_create_todo",
            {
                "name": "memory_create_todo",
                "description": "Create a new todo in working memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Todo content"},
                        "parent_id": {"type": "string", "default": "", "description": "Parent todo ID"},
                    },
                    "required": ["content"],
                },
            },
            _memory_create_todo,
        ),
        ToolEntry(
            "memory_update_todo",
            {
                "name": "memory_update_todo",
                "description": "Update a todo in working memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "todo_id": {"type": "string", "description": "Todo ID"},
                        "status": {
                            "type": "string",
                            "default": "",
                            "description": "Status: pending, in_progress, completed, failed, cancelled",
                        },
                        "notes": {"type": "string", "default": "", "description": "Notes"},
                        "content": {"type": "string", "default": "", "description": "Updated content"},
                    },
                    "required": ["todo_id"],
                },
            },
            _memory_update_todo,
        ),
        ToolEntry(
            "memory_view",
            {
                "name": "memory_view",
                "description": "View the current working memory (todo tree).",
                "parameters": {"type": "object", "properties": {}},
            },
            _memory_view,
        ),
        ToolEntry(
            "memory_progress",
            {
                "name": "memory_progress",
                "description": "Get working memory progress.",
                "parameters": {"type": "object", "properties": {}},
            },
            _memory_progress,
        ),
        ToolEntry(
            "memory_clear_completed",
            {
                "name": "memory_clear_completed",
                "description": "Clear completed todos from working memory.",
                "parameters": {"type": "object", "properties": {}},
            },
            _memory_clear_completed,
        ),
        # Self-Critique tools
        ToolEntry(
            "critique_evaluate",
            {
                "name": "critique_evaluate",
                "description": "Start a self-critique evaluation (CriticGPT-inspired).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task_description": {"type": "string", "description": "Task being evaluated"},
                        "work_summary": {"type": "string", "description": "Summary of work done"},
                        "threshold": {"type": "number", "default": 0.7, "description": "Pass threshold (0.0-1.0)"},
                    },
                    "required": ["task_description", "work_summary"],
                },
            },
            _critique_evaluate,
        ),
        ToolEntry(
            "critique_update_dimension",
            {
                "name": "critique_update_dimension",
                "description": "Update a critique dimension score.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "critique_id": {"type": "string", "description": "Critique ID"},
                        "dimension": {
                            "type": "string",
                            "description": "Dimension: correctness, completeness, safety, quality, efficiency",
                        },
                        "score": {"type": "number", "description": "Score (0.0-1.0)"},
                        "issues": {"type": "string", "default": "", "description": "Issues (pipe-separated)"},
                        "recommendations": {
                            "type": "string",
                            "default": "",
                            "description": "Recommendations (pipe-separated)",
                        },
                    },
                    "required": ["critique_id", "dimension", "score"],
                },
            },
            _critique_update_dimension,
        ),
        ToolEntry(
            "critique_stats",
            {
                "name": "critique_stats",
                "description": "Get self-critique statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _critique_stats,
        ),
    ]
