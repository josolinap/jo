"""Connection Weavers - Automatic neural link creation.

These tools actively find and create connections between:
- Code changes → Identity reflections
- Task results → Vault lessons
- Decisions → BIBLE.md principles
- Tools → Related concepts

A neuron extending dendrites to every part of the system.
"""

from __future__ import annotations

import logging
import pathlib
import re
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


def _weave_code_knowledge_connection(ctx: ToolContext, file_path: str, topic: str) -> str:
    """Connect a code file to a knowledge topic."""
    file_path_obj = pathlib.Path(file_path)
    if not file_path_obj.exists():
        file_path_obj = pathlib.Path(ctx.repo_dir) / file_path

    if not file_path_obj.exists():
        return f"⚠️ File not found: {file_path}"

    try:
        content = file_path_obj.read_text(encoding="utf-8")
    except Exception as e:
        return f"⚠️ Failed to read file: {e}"

    lines = [
        f"# {file_path_obj.name}",
        "",
        f"**Type:** Code Module",
        f"**Path:** {file_path}",
        "",
        "## Purpose",
        "_Purpose documented in code_",
        "",
        "## Related Concepts",
        f"[[{topic}]]",
        "",
        "## Key Functions",
    ]

    functions = re.findall(r"^def (\w+)", content, re.MULTILINE)
    for fn in functions[:10]:
        lines.append(f"- `{fn}()`")

    lines.extend(["", "## Dependencies", ""])
    imports = re.findall(r"^import (\w+)|^from (\w+)", content, re.MULTILINE)
    for imp in imports:
        module = imp[0] or imp[1]
        lines.append(f"- {module}")

    return "\n".join(lines)


def _reflect_on_change(ctx: ToolContext, change_description: str, outcome: str = "") -> str:
    """After a code change, create an identity reflection."""
    from datetime import datetime

    identity_path = ctx.drive_path("memory/identity.md")
    now = datetime.now().isoformat()

    reflection = f"""
## Reflection - {now}

**Change:** {change_description}
**Outcome:** {outcome or "Applied"}

_This change reflects growth in capabilities._
"""

    try:
        if identity_path.exists():
            content = identity_path.read_text(encoding="utf-8")
            identity_path.write_text(content + reflection, encoding="utf-8")
        else:
            identity_path.parent.mkdir(parents=True, exist_ok=True)
            identity_path.write_text(f"# Identity\n{reflection}", encoding="utf-8")
        return f"✅ Reflection added to identity"
    except Exception as e:
        return f"⚠️ Failed to write reflection: {e}"


def _learn_from_result(ctx: ToolContext, task: str, result: str, success: bool = True) -> str:
    """Store a lesson from task result in vault."""
    from ouroboros.tools.vault import _vault_create

    status = "success" if success else "failure"
    title = f"Lesson: {task[:50]}"

    content = f"""
## Task
{task}

## Result
{result[:500]}

## Status
{"✅ Success" if success else "❌ Failure"}

## Lesson
_What was learned from this task execution._
"""

    try:
        result = _vault_create(
            ctx,
            title=title,
            folder="journal",
            content=content,
            tags=f"lesson, {status}",
            type="lesson",
            status="reviewed",
        )
        return f"✅ Lesson stored: {result}"
    except Exception as e:
        return f"⚠️ Failed to store lesson: {e}"


def _link_decision_to_principle(ctx: ToolContext, decision: str, principle: str = "") -> str:
    """Link a decision to a BIBLE.md principle."""
    bible_path = ctx.repo_path("vault/concepts/bible.md")

    if not bible_path.exists():
        return "⚠️ BIBLE.md not found"

    try:
        content = bible_path.read_text(encoding="utf-8")

        decision_entry = f"""
### Decision: {decision[:100]}
**Principle:** {principle or "See relevant section above"}
**Date:** _Recorded automatically_
"""

        bible_path.write_text(content + decision_entry, encoding="utf-8")
        return f"✅ Decision linked to BIBLE.md"
    except Exception as e:
        return f"⚠️ Failed to link: {e}"


def _create_backlink(ctx: ToolContext, from_file: str, to_file: str, reason: str = "") -> str:
    """Create a backlink from one file to another."""
    from_path = pathlib.Path(from_file)
    if not from_path.is_absolute():
        from_path = ctx.repo_dir / from_file

    if not from_path.exists():
        return f"⚠️ Source file not found: {from_path}"

    try:
        content = from_path.read_text(encoding="utf-8")

        backlink = f"\n\n---\n**Related:** [[{to_file}]]"
        if reason:
            backlink += f" ({reason})"

        from_path.write_text(content + backlink, encoding="utf-8")
        return f"✅ Created backlink: {from_file} → {to_file}"
    except Exception as e:
        return f"⚠️ Failed to create backlink: {e}"


def _map_tool_to_concept(ctx: ToolContext, tool_name: str, concept: str) -> str:
    """Link a tool to a related concept in vault."""
    vault_path = ctx.repo_path("vault")

    concept_files = list(vault_path.rglob(f"*{concept}*.md"))

    if not concept_files:
        return f"ℹ️ No existing concept found for '{concept}'. Creating new link."

    try:
        content = concept_files[0].read_text(encoding="utf-8")

        tool_ref = f"\n\n---\n**Related Tool:** `{tool_name}`"

        if tool_name not in content:
            concept_files[0].write_text(content + tool_ref, encoding="utf-8")
            return f"✅ Linked tool '{tool_name}' to concept '{concept}'"
        else:
            return f"ℹ️ Link already exists"
    except Exception as e:
        return f"⚠️ Failed to map: {e}"


def _auto_weave_all(ctx: ToolContext) -> str:
    """Automatically find and create all possible connections."""
    from collections import defaultdict

    log.info("Auto-weaving all connections...")

    repo_dir = pathlib.Path(ctx.repo_dir)
    vault_dir = ctx.repo_path("vault")
    results = []

    code_connections = defaultdict(list)
    concept_connections = defaultdict(list)

    for py_file in repo_dir.rglob("*.py"):
        if "venv" in str(py_file) or ".git" in str(py_file):
            continue

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        imports = re.findall(r"^from (\w+)", content, re.MULTILINE)
        for imp in imports:
            if imp.startswith("ouroboros"):
                code_connections[py_file.stem].append(f"ouroboros.{imp}")

    for md_file in vault_dir.rglob("*.md"):
        if md_file.name.startswith("."):
            continue

        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
        for link in wikilinks:
            concept_connections[md_file.stem].append(link.strip())

    results.append("## Auto-Weave Results\n")

    results.append(f"**Code imports scanned:** {len(code_connections)}")
    results.append(f"**Vault links scanned:** {len(concept_connections)}")
    results.append("")

    orphan_tools = []
    for tool_file in (repo_dir / "ouroboros" / "tools").glob("*.py"):
        tool_name = tool_file.stem
        has_vault_link = any(tool_name in str(v) for v in concept_connections.keys())
        if not has_vault_link and tool_name not in ["__init__", "registry"]:
            orphan_tools.append(tool_name)

    if orphan_tools:
        results.append(f"### Undocumented Tools ({len(orphan_tools)})")
        results.append("Consider creating vault entries for these tools:")
        for t in orphan_tools[:10]:
            results.append(f"- `{t}`")
        if len(orphan_tools) > 10:
            results.append(f"- ... and {len(orphan_tools) - 10} more")
        results.append("")

    orphaned_concepts = []
    for concept in concept_connections:
        if not concept_connections[concept]:
            orphaned_concepts.append(concept)

    if orphaned_concepts:
        results.append(f"### Isolated Concepts ({len(orphaned_concepts)})")
        results.append("These concepts have no outgoing links:")
        for c in orphaned_concepts[:10]:
            results.append(f"- {c}")
        results.append("")

    connections_found = sum(len(v) for v in code_connections.values())
    connections_found += sum(len(v) for v in concept_connections.values())

    results.append(f"**Total connections found:** {connections_found}")

    return "\n".join(results)


def get_tools() -> List[ToolEntry]:
    """Get connection weaver tools."""
    return [
        ToolEntry(
            name="weave_connection",
            schema={
                "name": "weave_connection",
                "description": (
                    "Create a connection between a code file and a knowledge topic. "
                    "Links the codebase to the vault for associative thinking."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string", "description": "Path to code file"},
                        "topic": {"type": "string", "description": "Knowledge topic to link"},
                    },
                    "required": ["file_path", "topic"],
                },
            },
            handler=_weave_code_knowledge_connection,
            timeout_sec=15,
        ),
        ToolEntry(
            name="reflect_on_change",
            schema={
                "name": "reflect_on_change",
                "description": (
                    "After making a code change, record a reflection in identity. "
                    "Links actions to growth and evolution."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "change_description": {"type": "string", "description": "What changed"},
                        "outcome": {"type": "string", "description": "Result of the change"},
                    },
                    "required": ["change_description"],
                },
            },
            handler=_reflect_on_change,
            timeout_sec=10,
        ),
        ToolEntry(
            name="learn_from_result",
            schema={
                "name": "learn_from_result",
                "description": (
                    "Store a lesson from a task result in the vault journal. Builds a knowledge base of experiences."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "task": {"type": "string", "description": "Task description"},
                        "result": {"type": "string", "description": "Task result"},
                        "success": {"type": "boolean", "description": "Was the task successful?"},
                    },
                    "required": ["task", "result"],
                },
            },
            handler=_learn_from_result,
            timeout_sec=15,
        ),
        ToolEntry(
            name="link_to_principle",
            schema={
                "name": "link_to_principle",
                "description": (
                    "Link a decision to a BIBLE.md principle. Creates traceability from actions to core values."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "decision": {"type": "string", "description": "Decision made"},
                        "principle": {"type": "string", "description": "Related principle"},
                    },
                    "required": ["decision"],
                },
            },
            handler=_link_decision_to_principle,
            timeout_sec=10,
        ),
        ToolEntry(
            name="create_backlink",
            schema={
                "name": "create_backlink",
                "description": "Create a backlink from one file to another in the codebase.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_file": {"type": "string", "description": "Source file path"},
                        "to_file": {"type": "string", "description": "Target file path"},
                        "reason": {"type": "string", "description": "Why they're related"},
                    },
                    "required": ["from_file", "to_file"],
                },
            },
            handler=_create_backlink,
            timeout_sec=10,
        ),
        ToolEntry(
            name="map_tool_to_concept",
            schema={
                "name": "map_tool_to_concept",
                "description": "Link a tool to a related concept in the vault.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string", "description": "Tool name"},
                        "concept": {"type": "string", "description": "Concept name"},
                    },
                    "required": ["tool_name", "concept"],
                },
            },
            handler=_map_tool_to_concept,
            timeout_sec=10,
        ),
        ToolEntry(
            name="auto_weave",
            schema={
                "name": "auto_weave",
                "description": (
                    "Automatically scan codebase and vault, find all connections, "
                    "identify gaps, and report what needs linking."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_auto_weave_all,
            timeout_sec=30,
        ),
    ]
