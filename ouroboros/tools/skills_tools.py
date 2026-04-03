"""
Jo — Skills Tools.

Tool wrappers for the advanced skill system.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolEntry
from ouroboros.tools.context import ToolContext

log = logging.getLogger(__name__)


def _get_detector():
    from ouroboros.skills.keyword_detector import get_detector

    return get_detector()


def _get_skill_manager(repo_dir: pathlib.Path):
    from ouroboros.skills.skill_manager import get_skill_manager

    return get_skill_manager(repo_dir)


def _get_agent_router():
    from ouroboros.skills.agent_system import get_agent_router

    return get_agent_router()


def _get_state_manager(repo_dir: pathlib.Path):
    from ouroboros.skills.state_manager import get_state_manager

    return get_state_manager(repo_dir)


def _detect_keywords(ctx: ToolContext, prompt: str) -> str:
    """Detect magic keywords in a prompt."""
    detector = _get_detector()
    triggered = detector.detect(prompt)

    if not triggered:
        return "No magic keywords detected."

    parts = ["## Detected Magic Keywords\n"]
    for t in triggered:
        parts.append(f"- **{t['name']}** ({t['mode']}): {t['description']}")
        parts.append(f"  Matched: '{t['matched_keyword']}'")
        parts.append(f"  Priority: {t['priority']}")
        parts.append("")

    return "\n".join(parts)


def _list_skills(ctx: ToolContext) -> str:
    """List all available skills."""
    skill_mgr = _get_skill_manager(ctx.repo_dir)
    skills = skill_mgr.list_skills()

    if not skills:
        return "No skills registered."

    parts = ["## Available Skills\n"]
    for skill in skills:
        status = "✅" if skill["enabled"] else "❌"
        parts.append(f"{status} **{skill['name']}** ({skill['source']}/{skill['layer']})")
        parts.append(f"   {skill['description']}")
        parts.append(f"   Triggers: {', '.join(skill['triggers'])}")
        parts.append("")

    return "\n".join(parts)


def _list_agents(ctx: ToolContext) -> str:
    """List all available specialized agents."""
    router = _get_agent_router()
    agents = router.list_agents()

    parts = ["## Available Agents\n"]

    # Group by lane
    by_lane = {}
    for agent in agents:
        lane = agent["lane"]
        by_lane.setdefault(lane, []).append(agent)

    for lane, lane_agents in by_lane.items():
        parts.append(f"### {lane.replace('_', ' ').title()} Lane")
        for agent in lane_agents:
            parts.append(f"- **{agent['name']}** ({agent['model_tier']}): {agent['role']}")
            parts.append(f"  {agent['description']}")
        parts.append("")

    parts.append("## Typical Workflow\n")
    for step in router.get_typical_workflow():
        parts.append(f"→ {step}")

    return "\n".join(parts)


def _route_task(ctx: ToolContext, task: str) -> str:
    """Route a task to appropriate agents."""
    router = _get_agent_router()
    agents = router.route(task)

    parts = [f"## Task Routing for: {task[:100]}\n"]
    parts.append("### Recommended Agents\n")

    for agent in agents:
        parts.append(f"- **{agent.name}** ({agent.model_tier.value})")
        parts.append(f"  Role: {agent.role}")
        parts.append(f"  Capabilities: {', '.join(agent.capabilities)}")
        parts.append("")

    return "\n".join(parts)


def _notepad_write(ctx: ToolContext, content: str, priority: bool = False, source: str = "") -> str:
    """Write to the compaction-resistant notepad."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    state_mgr.notepad.write(content, source=source, priority=priority)

    priority_str = " [PRIORITY]" if priority else ""
    return f"✅ Notepad entry written{priority_str}\nContent: {content[:100]}..."


def _notepad_read(ctx: ToolContext) -> str:
    """Read the notepad contents."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    content = state_mgr.notepad.read()

    if not content:
        return "Notepad is empty."

    return content


def _notepad_stats(ctx: ToolContext) -> str:
    """Get notepad statistics."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    stats = state_mgr.notepad.stats()

    return (
        f"## Notepad Statistics\n"
        f"- Total entries: {stats['total_entries']}\n"
        f"- Priority entries: {stats['priority_entries']}\n"
        f"- Working entries: {stats['working_entries']}"
    )


def _project_memory_read(ctx: ToolContext) -> str:
    """Read project memory."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    content = state_mgr.project_memory.read()

    if not content:
        return "Project memory is empty."

    return content


def _project_memory_add_note(ctx: ToolContext, note: str) -> str:
    """Add a note to project memory."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    state_mgr.project_memory.add_note(note)
    return f"✅ Note added to project memory: {note[:100]}..."


def _project_memory_add_directive(ctx: ToolContext, directive: str) -> str:
    """Add a directive to project memory."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    state_mgr.project_memory.add_directive(directive)
    return f"✅ Directive added to project memory: {directive[:100]}..."


def _persistent_tag_add(ctx: ToolContext, content: str, permanent: bool = False) -> str:
    """Add a persistent tag."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    state_mgr.persistent_tags.add(content, permanent=permanent)

    retention = "permanent" if permanent else "7 days"
    return f"✅ Persistent tag added (retention: {retention}): {content[:100]}..."


def _persistent_tag_list(ctx: ToolContext) -> str:
    """List active persistent tags."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    tags = state_mgr.persistent_tags.get_active()

    if not tags:
        return "No active persistent tags."

    parts = ["## Active Persistent Tags\n"]
    for tag in tags:
        parts.append(f"- {tag}")

    return "\n".join(parts)


def _plan_notepad_create(ctx: ToolContext, plan_name: str) -> str:
    """Create a new plan notepad."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    state_mgr.create_plan_notepad(plan_name)
    return f"✅ Plan notepad created: {plan_name}"


def _plan_notepad_add(ctx: ToolContext, plan_name: str, category: str, content: str) -> str:
    """Add an entry to a plan notepad."""
    state_mgr = _get_state_manager(ctx.repo_dir)

    if category == "learning":
        state_mgr.add_plan_learning(plan_name, content)
    elif category == "decision":
        state_mgr.add_plan_decision(plan_name, content)
    elif category == "issue":
        state_mgr.add_plan_issue(plan_name, content)
    elif category == "problem":
        state_mgr.add_plan_problem(plan_name, content)
    else:
        return f"⚠️ Invalid category: {category}. Must be: learning, decision, issue, problem"

    return f"✅ Added {category} to plan '{plan_name}': {content[:100]}..."


def _state_full_context(ctx: ToolContext) -> str:
    """Get full state context."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    content = state_mgr.get_full_context()

    if not content:
        return "No state information available."

    return content


def _state_cleanup(ctx: ToolContext) -> str:
    """Clean up expired and old state."""
    state_mgr = _get_state_manager(ctx.repo_dir)
    results = state_mgr.cleanup()

    parts = ["## State Cleanup Results\n"]
    for key, value in results.items():
        parts.append(f"- {key}: {value}")

    return "\n".join(parts)


def _verify_all(ctx: ToolContext) -> str:
    """Run full verification protocol."""
    from ouroboros.skills.verification import get_verifier

    verifier = get_verifier(ctx.repo_dir)
    report = verifier.verify_all()
    return report.summary()


def _verify_build(ctx: ToolContext) -> str:
    """Run build verification only."""
    from ouroboros.skills.verification import get_verifier

    verifier = get_verifier(ctx.repo_dir)
    verifier._verify_build()
    return verifier._results[-1].evidence if verifier._results else "No result"


def _verify_tests(ctx: ToolContext) -> str:
    """Run test verification only."""
    from ouroboros.skills.verification import get_verifier

    verifier = get_verifier(ctx.repo_dir)
    verifier._verify_tests()
    return verifier._results[-1].evidence if verifier._results else "No result"


def get_tools() -> List[ToolEntry]:
    """Get skills tools."""
    return [
        ToolEntry(
            "detect_keywords",
            {
                "name": "detect_keywords",
                "description": "Detect magic keywords in a prompt and return triggered modes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {"type": "string", "description": "Text to analyze for magic keywords"},
                    },
                    "required": ["prompt"],
                },
            },
            _detect_keywords,
        ),
        ToolEntry(
            "list_skills",
            {
                "name": "list_skills",
                "description": "List all available skills with their triggers and status.",
                "parameters": {"type": "object", "properties": {}},
            },
            _list_skills,
        ),
        ToolEntry(
            "list_agents",
            {
                "name": "list_agents",
                "description": "List all 19 specialized agents organized by lane.",
                "parameters": {"type": "object", "properties": {}},
            },
            _list_agents,
        ),
        ToolEntry(
            "route_task",
            {
                "name": "route_task",
                "description": "Route a task description to appropriate specialized agents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description to route"},
                    },
                    "required": ["task"],
                },
            },
            _route_task,
        ),
        ToolEntry(
            "notepad_write",
            {
                "name": "notepad_write",
                "description": "Write to the compaction-resistant notepad. Survives context resets.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Content to write"},
                        "priority": {
                            "type": "boolean",
                            "default": False,
                            "description": "Mark as priority (never pruned)",
                        },
                        "source": {"type": "string", "default": "", "description": "Source of this entry"},
                    },
                    "required": ["content"],
                },
            },
            _notepad_write,
        ),
        ToolEntry(
            "notepad_read",
            {
                "name": "notepad_read",
                "description": "Read the compaction-resistant notepad contents.",
                "parameters": {"type": "object", "properties": {}},
            },
            _notepad_read,
        ),
        ToolEntry(
            "notepad_stats",
            {
                "name": "notepad_stats",
                "description": "Get notepad statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            _notepad_stats,
        ),
        ToolEntry(
            "project_memory_read",
            {
                "name": "project_memory_read",
                "description": "Read persistent project memory.",
                "parameters": {"type": "object", "properties": {}},
            },
            _project_memory_read,
        ),
        ToolEntry(
            "project_memory_add_note",
            {
                "name": "project_memory_add_note",
                "description": "Add a note to project memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note content"},
                    },
                    "required": ["note"],
                },
            },
            _project_memory_add_note,
        ),
        ToolEntry(
            "project_memory_add_directive",
            {
                "name": "project_memory_add_directive",
                "description": "Add a directive to project memory.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "directive": {"type": "string", "description": "Directive content"},
                    },
                    "required": ["directive"],
                },
            },
            _project_memory_add_directive,
        ),
        ToolEntry(
            "persistent_tag_add",
            {
                "name": "persistent_tag_add",
                "description": "Add a persistent tag (7-day or permanent retention).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "content": {"type": "string", "description": "Tag content"},
                        "permanent": {"type": "boolean", "default": False, "description": "Permanent retention"},
                    },
                    "required": ["content"],
                },
            },
            _persistent_tag_add,
        ),
        ToolEntry(
            "persistent_tag_list",
            {
                "name": "persistent_tag_list",
                "description": "List active persistent tags.",
                "parameters": {"type": "object", "properties": {}},
            },
            _persistent_tag_list,
        ),
        ToolEntry(
            "plan_notepad_create",
            {
                "name": "plan_notepad_create",
                "description": "Create a new plan notepad for per-plan knowledge capture.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan_name": {"type": "string", "description": "Name of the plan"},
                    },
                    "required": ["plan_name"],
                },
            },
            _plan_notepad_create,
        ),
        ToolEntry(
            "plan_notepad_add",
            {
                "name": "plan_notepad_add",
                "description": "Add an entry to a plan notepad (learning/decision/issue/problem).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "plan_name": {"type": "string", "description": "Name of the plan"},
                        "category": {"type": "string", "description": "Category: learning, decision, issue, problem"},
                        "content": {"type": "string", "description": "Entry content"},
                    },
                    "required": ["plan_name", "category", "content"],
                },
            },
            _plan_notepad_add,
        ),
        ToolEntry(
            "state_full_context",
            {
                "name": "state_full_context",
                "description": "Get full state context (notepad, project memory, tags, plans).",
                "parameters": {"type": "object", "properties": {}},
            },
            _state_full_context,
        ),
        ToolEntry(
            "state_cleanup",
            {
                "name": "state_cleanup",
                "description": "Clean up expired and old state entries.",
                "parameters": {"type": "object", "properties": {}},
            },
            _state_cleanup,
        ),
        ToolEntry(
            "verify_all",
            {
                "name": "verify_all",
                "description": "Run full multi-stage verification protocol (BUILD, TEST, LINT, FUNCTIONALITY, ARCHITECT, TODO, ERROR_FREE).",
                "parameters": {"type": "object", "properties": {}},
            },
            _verify_all,
        ),
        ToolEntry(
            "verify_build",
            {
                "name": "verify_build",
                "description": "Run build verification only (compilation check).",
                "parameters": {"type": "object", "properties": {}},
            },
            _verify_build,
        ),
        ToolEntry(
            "verify_tests",
            {
                "name": "verify_tests",
                "description": "Run test verification only.",
                "parameters": {"type": "object", "properties": {}},
            },
            _verify_tests,
        ),
    ]
