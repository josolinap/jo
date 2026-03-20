"""Vault tools: vault_create, vault_read, vault_write, vault_list, vault_search, vault_link, vault_backlinks, vault_graph."""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.vault_manager import VaultManager

log = logging.getLogger(__name__)


def _vault_path(ctx: ToolContext) -> pathlib.Path:
    return ctx.repo_path("vault")


def _get_vault(ctx: ToolContext) -> VaultManager:
    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else None
    return VaultManager(_vault_path(ctx), repo_dir=repo_dir)


def _sync_vault_to_repo(ctx: ToolContext, vault: VaultManager, action: str) -> str:
    """Sync vault changes to repo and commit."""
    if vault.repo_vault_path is None:
        return ""

    try:
        from ouroboros.tools.git import _repo_commit_push

        # Sync vault files to repo
        vault.sync_to_repo()

        # Commit vault changes
        commit_msg = f"vault: {action}"
        result = _repo_commit_push(ctx, commit_message=commit_msg, paths=["vault"])

        if "OK:" in result:
            return f" [{result}]"
        elif "⚠️" in result:
            return f" [Sync: {result}]"
        return ""
    except Exception as e:
        log.warning(f"Failed to sync vault to repo: {e}")
        return f" [Sync: {e}]"


def _vault_create(
    ctx: ToolContext,
    title: str,
    folder: str = "concepts",
    content: str = "",
    tags: str = "",
    type: str = "reference",
    status: str = "active",
) -> str:
    """Create a new vault note with frontmatter."""
    vault = _get_vault(ctx)
    tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    path = vault.create_note(title=title, folder=folder, content=content, tags=tag_list, type=type, status=status)
    sync_msg = _sync_vault_to_repo(ctx, vault, f"create {title}")
    return f"OK: Created {path}{sync_msg}"


def _vault_read(ctx: ToolContext, note: str, include_backlinks: bool = False) -> str:
    """Read a vault note by name."""
    vault = _get_vault(ctx)
    parsed = vault.get_note(note)
    if not parsed:
        return f"⚠️ Note not found: {note}"
    result = [
        f"# {parsed.title}",
        f"Tags: {', '.join(parsed.tags)}",
        f"Type: {parsed.frontmatter.get('type', 'reference')}",
        f"Status: {parsed.frontmatter.get('status', 'active')}",
        "",
        parsed.content,
    ]
    if include_backlinks:
        backlinks_section = vault.render_backlinks_section(parsed.title)
        if backlinks_section:
            result.append(backlinks_section)
    return "\n".join(result)


def _vault_write(ctx: ToolContext, note: str, content: str, mode: str = "append") -> str:
    """Write content to a vault note."""
    vault = _get_vault(ctx)
    if mode == "overwrite":
        result = vault.write_note(note, content, mode="overwrite")
        sync_msg = _sync_vault_to_repo(ctx, vault, f"update {note}")
        return f"{result}{sync_msg}"
    path = vault.resolve_path(note)
    if not path:
        return f"⚠️ Note not found: {note}"
    try:
        existing = path.read_text(encoding="utf-8")
        full_content = existing.rstrip() + "\n\n" + content
        path.write_text(full_content, encoding="utf-8")
        vault.invalidate_cache()
        sync_msg = _sync_vault_to_repo(ctx, vault, f"update {note}")
        return f"OK: Appended to {path.name}{sync_msg}"
    except Exception as e:
        return f"⚠️ Error writing note: {e}"


def _vault_list(ctx: ToolContext, folder: str = "", tags: str = "", status: str = "") -> str:
    """List vault notes, optionally filtered by folder or tags."""
    vault = _get_vault(ctx)
    notes = vault.get_all_notes()
    if folder:
        notes = [n for n in notes if folder in n["path"]]
    if tags:
        tag_list = [t.strip() for t in tags.split(",")]
        notes = [n for n in notes if any(t in n["tags"] for t in tag_list)]
    if status:
        notes = [n for n in notes if n["status"] == status]
    if not notes:
        return "(no notes found)"
    lines = [f"Found {len(notes)} notes:\n"]
    for note in notes:
        lines.append(f"- [[{note['title']}]] ({note['type']}, {note['status']})")
        if note["tags"]:
            lines.append(f"  Tags: {', '.join(note['tags'])}")
        if note["backlink_count"] > 0:
            lines.append(f"  Backlinks: {note['backlink_count']}")
    return "\n".join(lines)


def _vault_search(ctx: ToolContext, query: str, field: str = "content") -> str:
    """Search vault notes by content, title, or tags."""
    vault = _get_vault(ctx)
    results = vault.search(query, field)
    if not results:
        return f"(no results for '{query}' in {field})"
    lines = [f"Found {len(results)} result(s) for '{query}':\n"]
    for r in results:
        lines.append(f"- [[{r['note']}]] (match: {r['match']})")
    return "\n".join(lines)


def _vault_link(ctx: ToolContext, source: str, target: str, context: str = "") -> str:
    """Create a wikilink from source note to target note."""
    vault = _get_vault(ctx)
    return vault.link_notes(source, target, context)


def _vault_backlinks(ctx: ToolContext, note: str) -> str:
    """Show all notes that link to the specified note."""
    vault = _get_vault(ctx)
    backlinks = vault.get_backlinks(note)
    if not backlinks:
        return f"(no backlinks for '{note}')"
    lines = [f"Backlinks to [[{note}]] ({len(backlinks)}):\n"]
    for bl in backlinks:
        lines.append(f"- {bl['source']} (in [[{bl['note']}]])")
        if bl.get("context"):
            lines.append(f"  > {bl['context']}")
    return "\n".join(lines)


def _vault_outlinks(ctx: ToolContext, note: str) -> str:
    """Show all notes that this note links to."""
    vault = _get_vault(ctx)
    outlinks = vault.get_outlinks(note)
    if not outlinks:
        return f"(no outlinks from '{note}')"
    lines = [f"Outlinks from [[{note}]] ({len(outlinks)}):\n"]
    for target in outlinks:
        lines.append(f"- [[{target}]]")
    return "\n".join(lines)


def _vault_graph(ctx: ToolContext, format: str = "json") -> str:
    """Get vault graph data for visualization. Formats: json, mermaid, dot."""
    vault = _get_vault(ctx)
    if format == "mermaid":
        return vault.export_mermaid()
    elif format == "dot":
        return vault.export_dot()
    else:
        graph = vault.get_graph_data()
        return json.dumps(graph, indent=2, ensure_ascii=False)


def _vault_delete(ctx: ToolContext, note: str) -> str:
    """Delete a vault note."""
    vault = _get_vault(ctx)
    result = vault.delete_note(note)
    sync_msg = _sync_vault_to_repo(ctx, vault, f"delete {note}")
    return f"{result}{sync_msg}"


def _vault_ensure(ctx: ToolContext) -> str:
    """Ensure vault directory structure exists."""
    vault = _get_vault(ctx)
    vault.ensure_vault_structure()
    return "OK: Vault structure ready"


def _vault_verify(ctx: ToolContext) -> str:
    """Check vault integrity and detect duplicates."""
    vault = _get_vault(ctx)

    integrity = vault.check_integrity()
    duplicates = vault.detect_duplicates()

    lines = ["## Vault Integrity Report", ""]

    if integrity["healthy"]:
        lines.append("Status: **Healthy**")
    else:
        lines.append("Status: **Issues Found**")
        for issue in integrity["issues"]:
            lines.append(f"- {issue}")

    lines.append(f"")
    lines.append(f"Files checked: {integrity['files_checked']}")
    lines.append(f"Last check: {integrity['last_check']}")

    if duplicates:
        lines.append("")
        lines.append("### Potential Duplicates")
        for dup in duplicates:
            lines.append(f"- `{dup['base_name']}`: {dup['count']} files")
            for f in dup["files"]:
                lines.append(f"  - {f}")
    else:
        lines.append("")
        lines.append("No duplicates detected.")

    return "\n".join(lines)


def _vault_integrity_update(ctx: ToolContext) -> str:
    """Update vault integrity checksums."""
    vault = _get_vault(ctx)
    vault.update_integrity()
    return "OK: Integrity checksums updated"


def get_tools() -> List[ToolEntry]:
    return [
        ToolEntry(
            "vault_create",
            {
                "name": "vault_create",
                "description": "Create a new note in Jo's knowledge vault. Use to capture concepts, decisions, or ideas with proper structure.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string", "description": "Note title"},
                        "folder": {
                            "type": "string",
                            "description": "Folder: concepts, projects, tools, journal (default: concepts)",
                        },
                        "content": {"type": "string", "description": "Initial content (optional)"},
                        "tags": {"type": "string", "description": "Comma-separated tags (optional)"},
                        "type": {
                            "type": "string",
                            "description": "Note type: reference, project, concept, tool (default: reference)",
                        },
                        "status": {
                            "type": "string",
                            "description": "Status: active, draft, archived (default: active)",
                        },
                    },
                    "required": ["title"],
                },
            },
            _vault_create,
        ),
        ToolEntry(
            "vault_read",
            {
                "name": "vault_read",
                "description": "Read a vault note by name. Returns title, tags, and content.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note name (without .md)"},
                        "include_backlinks": {
                            "type": "boolean",
                            "description": "Include backlinks section (default: false)",
                        },
                    },
                    "required": ["note"],
                },
            },
            _vault_read,
        ),
        ToolEntry(
            "vault_write",
            {
                "name": "vault_write",
                "description": "Write or append content to a vault note.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note name"},
                        "content": {"type": "string", "description": "Content to write"},
                        "mode": {"type": "string", "enum": ["append", "overwrite"], "default": "append"},
                    },
                    "required": ["note", "content"],
                },
            },
            _vault_write,
        ),
        ToolEntry(
            "vault_list",
            {
                "name": "vault_list",
                "description": "List all vault notes, optionally filtered by folder or tags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "description": "Filter by folder name"},
                        "tags": {"type": "string", "description": "Filter by comma-separated tags"},
                        "status": {"type": "string", "description": "Filter by status: active, draft, archived"},
                    },
                    "required": [],
                },
            },
            _vault_list,
        ),
        ToolEntry(
            "vault_search",
            {
                "name": "vault_search",
                "description": "Search vault notes by content, title, or tags.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "field": {"type": "string", "enum": ["content", "title", "tags"], "default": "content"},
                    },
                    "required": ["query"],
                },
            },
            _vault_search,
        ),
        ToolEntry(
            "vault_link",
            {
                "name": "vault_link",
                "description": "Create a wikilink from source note to target note.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source note name"},
                        "target": {"type": "string", "description": "Target note name"},
                        "context": {"type": "string", "description": "Optional context text before the link"},
                    },
                    "required": ["source", "target"],
                },
            },
            _vault_link,
        ),
        ToolEntry(
            "vault_backlinks",
            {
                "name": "vault_backlinks",
                "description": "Show all notes that link to the specified note (bidirectional awareness).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note name to get backlinks for"},
                    },
                    "required": ["note"],
                },
            },
            _vault_backlinks,
        ),
        ToolEntry(
            "vault_outlinks",
            {
                "name": "vault_outlinks",
                "description": "Show all notes that this note links to.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note name to get outlinks for"},
                    },
                    "required": ["note"],
                },
            },
            _vault_outlinks,
        ),
        ToolEntry(
            "vault_graph",
            {
                "name": "vault_graph",
                "description": "Get vault knowledge graph for visualization. Export as JSON (D3), Mermaid, or DOT format.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {"type": "string", "enum": ["json", "mermaid", "dot"], "default": "json"},
                    },
                    "required": [],
                },
            },
            _vault_graph,
        ),
        ToolEntry(
            "vault_delete",
            {
                "name": "vault_delete",
                "description": "Delete a vault note.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "note": {"type": "string", "description": "Note name to delete"},
                    },
                    "required": ["note"],
                },
            },
            _vault_delete,
        ),
        ToolEntry(
            "vault_ensure",
            {
                "name": "vault_ensure",
                "description": "Ensure vault directory structure exists. Idempotent.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            _vault_ensure,
        ),
        ToolEntry(
            "vault_verify",
            {
                "name": "vault_verify",
                "description": "Check vault integrity (checksums) and detect duplicates.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            _vault_verify,
        ),
        ToolEntry(
            "vault_integrity_update",
            {
                "name": "vault_integrity_update",
                "description": "Update vault integrity checksums. Run after bulk changes.",
                "parameters": {"type": "object", "properties": {}, "required": []},
            },
            _vault_integrity_update,
        ),
    ]
