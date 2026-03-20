"""
Ouroboros — Vault Manager.

Manages Jo's Obsidian-style vault: notes, links, backlinks, and metadata.
"""

from __future__ import annotations

import json
import logging
import pathlib
from datetime import datetime
from typing import Any, Dict, List, Optional

from ouroboros.utils import utc_now_iso

from .vault_parser import WikilinkParser, ParsedNote, Wikilink

log = logging.getLogger(__name__)


class VaultManager:
    """Manages Jo's Obsidian-style vault with wikilinks and backlinks."""

    def __init__(self, vault_root: pathlib.Path):
        self.vault_root = vault_root
        self.parser = WikilinkParser()
        self._graph_cache: Optional[Dict[str, Any]] = None
        self._index: Dict[str, ParsedNote] = {}

    @property
    def graph_cache_path(self) -> pathlib.Path:
        return self.vault_root / ".vault" / "graph.json"

    @property
    def backlinks_cache_path(self) -> pathlib.Path:
        return self.vault_root / ".vault" / "backlinks.json"

    def ensure_vault_structure(self) -> None:
        """Create vault directory structure if it doesn't exist."""
        (self.vault_root / ".vault").mkdir(parents=True, exist_ok=True)
        for folder in ["concepts", "projects", "tools", "journal"]:
            (self.vault_root / folder).mkdir(parents=True, exist_ok=True)

    def resolve_path(self, note_name_or_path: str) -> Optional[pathlib.Path]:
        """Resolve a note name or path to an absolute path."""
        if pathlib.Path(note_name_or_path).exists():
            return pathlib.Path(note_name_or_path)
        name = note_name_or_path.rstrip(".md")
        name_lower = name.lower()
        for md_file in self.vault_root.rglob("*.md"):
            if ".vault" in md_file.parts:
                continue
            if md_file.stem.lower() == name_lower or str(md_file) == note_name_or_path:
                return md_file
        return None

    def note_name(self, path: pathlib.Path) -> str:
        """Get the note name (filename without extension) from a path."""
        return path.stem

    def get_note(self, note_name: str) -> Optional[ParsedNote]:
        """Get a parsed note by name."""
        if note_name in self._index:
            return self._index[note_name]
        path = self.resolve_path(note_name)
        if not path:
            return None
        try:
            content = path.read_text(encoding="utf-8")
            note = self.parser.parse_file(str(path), content)
            self._index[note_name] = note
            return note
        except Exception as e:
            log.warning(f"Failed to parse note {note_name}: {e}")
            return None

    def create_note(
        self,
        title: str,
        folder: str = "concepts",
        content: str = "",
        tags: Optional[List[str]] = None,
        type: str = "reference",
        status: str = "active",
        aliases: Optional[List[str]] = None,
    ) -> str:
        """Create a new note with frontmatter."""
        self.ensure_vault_structure()
        safe_title = self._sanitize_filename(title)
        path = self.vault_root / folder / f"{safe_title}.md"
        counter = 1
        while path.exists():
            path = self.vault_root / folder / f"{safe_title}_{counter}.md"
            counter += 1
        now = utc_now_iso()
        frontmatter = [
            "---",
            f"title: {title}",
            f"created: {now}",
            f"modified: {now}",
            f"type: {type}",
            f"status: {status}",
        ]
        if tags:
            frontmatter.append(f"tags: [{', '.join(tags)}]")
        if aliases:
            frontmatter.append(f"aliases: [{', '.join(aliases)}]")
        frontmatter.append("---")
        full_content = "\n".join(frontmatter) + f"\n\n# {title}\n\n{content}"
        path.write_text(full_content, encoding="utf-8")
        self.invalidate_cache()
        return str(path)

    def write_note(
        self,
        note_name: str,
        content: str,
        mode: str = "overwrite",
    ) -> str:
        """Write content to an existing note.

        Args:
            note_name: Name of the note
            content: Content to write
            mode: 'overwrite' (replace all) or 'append' (add to end)
        """
        path = self.resolve_path(note_name)
        if not path:
            return f"⚠️ Note not found: {note_name}"
        try:
            existing = ""
            if path.exists():
                existing = path.read_text(encoding="utf-8")
            if mode == "append":
                new_content = existing.rstrip() + "\n\n" + content
            else:
                if existing.startswith("---"):
                    fm_end = existing.find("\n---\n") + 6
                    fm = existing[:fm_end]
                    new_content = fm + "\n" + content
                else:
                    new_content = content
            path.write_text(new_content, encoding="utf-8")
            self.invalidate_cache()
            return f"OK: Updated {path.name}"
        except Exception as e:
            return f"⚠️ Error writing note: {e}"

    def delete_note(self, note_name: str) -> str:
        """Delete a note."""
        path = self.resolve_path(note_name)
        if not path:
            return f"⚠️ Note not found: {note_name}"
        try:
            path.unlink()
            self.invalidate_cache()
            self._index.pop(note_name, None)
            return f"OK: Deleted {path.name}"
        except Exception as e:
            return f"⚠️ Error deleting note: {e}"

    def link_notes(self, source: str, target: str, context: str = "") -> str:
        """Add a wikilink from source to target note."""
        source_path = self.resolve_path(source)
        if not source_path:
            return f"⚠️ Source note not found: {source}"
        try:
            content = source_path.read_text(encoding="utf-8")
            target_name = target.rstrip(".md").rsplit("/", 1)[-1]
            link_text = f" [[{target_name}]]"
            if context:
                content = content.rstrip() + f"\n{context}{link_text}\n"
            else:
                content = content.rstrip() + f"{link_text}\n"
            source_path.write_text(content, encoding="utf-8")
            self.invalidate_cache()
            return f"OK: Linked {source} → {target}"
        except Exception as e:
            return f"⚠️ Error linking notes: {e}"

    def get_outlinks(self, note_name: str) -> List[str]:
        """Get list of notes that this note links to."""
        note = self.get_note(note_name)
        if not note:
            return []
        return list(set(w.note_name for w in note.wikilinks))

    def get_backlinks(self, note_name: str) -> List[Dict[str, Any]]:
        """Get all notes that link to this note."""
        self.build_index()
        backlinks = []
        note = self.get_note(note_name)
        if not note:
            return []
        note_title = note.title.lower()
        note_stem = note_name.rstrip(".md").rsplit("/", 1)[-1].lower()
        for path_str, parsed in self._index.items():
            for wikilink in parsed.wikilinks:
                target_lower = wikilink.note_name.lower()
                if target_lower == note_title or target_lower == note_stem:
                    context = self._get_link_context(str(parsed.path), wikilink)
                    backlinks.append(
                        {
                            "source": wikilink.raw,
                            "note": parsed.title or parsed.path,
                            "path": parsed.path,
                            "context": context,
                        }
                    )
        return backlinks

    def _get_link_context(self, path: str, wikilink: Wikilink) -> str:
        """Get surrounding context for a wikilink."""
        try:
            content = pathlib.Path(path).read_text(encoding="utf-8")
            idx = content.find(wikilink.raw)
            if idx == -1:
                return ""
            start = max(0, idx - 50)
            end = min(len(content), idx + len(wikilink.raw) + 50)
            context = content[start:end].replace("\n", " ").strip()
            return f"...{context}..."
        except Exception:
            return ""

    def build_index(self) -> None:
        """Build or refresh the note index."""
        self._index.clear()
        if not self.vault_root.exists():
            return
        for md_file in self.vault_root.rglob("*.md"):
            if ".vault" in md_file.parts:
                continue
            try:
                content = md_file.read_text(encoding="utf-8")
                note = self.parser.parse_file(str(md_file), content)
                self._index[str(md_file)] = note
            except Exception as e:
                log.debug(f"Failed to index {md_file}: {e}")

    def invalidate_cache(self) -> None:
        """Invalidate cached graph and backlinks."""
        self._graph_cache = None
        self._index.clear()

    def get_all_notes(self) -> List[Dict[str, Any]]:
        """Get all notes with their metadata."""
        self.build_index()
        notes = []
        for path_str, parsed in self._index.items():
            notes.append(
                {
                    "title": parsed.title or parsed.path,
                    "path": parsed.path,
                    "aliases": parsed.aliases,
                    "tags": parsed.tags,
                    "type": parsed.frontmatter.get("type", "reference"),
                    "status": parsed.frontmatter.get("status", "active"),
                    "created": parsed.frontmatter.get("created", ""),
                    "modified": parsed.frontmatter.get("modified", ""),
                    "outlinks": [w.note_name for w in parsed.wikilinks],
                    "backlink_count": len(self.get_backlinks(parsed.title)),
                }
            )
        return notes

    def search(self, query: str, field: str = "content") -> List[Dict[str, Any]]:
        """Search notes by content or tags."""
        self.build_index()
        query_lower = query.lower()
        results = []
        for path_str, parsed in self._index.items():
            if field == "content" and query_lower in parsed.content.lower():
                results.append({"note": parsed.title, "path": parsed.path, "match": "content"})
            elif field == "title" and query_lower in parsed.title.lower():
                results.append({"note": parsed.title, "path": parsed.path, "match": "title"})
            elif field == "tags":
                if query_lower in [t.lower() for t in parsed.tags]:
                    results.append({"note": parsed.title, "path": parsed.path, "match": "tag"})
        return results

    def render_backlinks_section(self, note_name: str) -> str:
        """Render a backlinks section for embedding in a note."""
        backlinks = self.get_backlinks(note_name)
        if not backlinks:
            return ""
        lines = ["\n---\n## Backlinks\n"]
        for bl in backlinks:
            lines.append(f"- {bl['source']} (in [[{bl['note']}]])")
            if bl.get("context"):
                lines.append(f"  > {bl['context']}")
        return "\n".join(lines)

    def _sanitize_filename(self, title: str) -> str:
        """Sanitize a title for use as a filename."""
        safe = title.lower()
        safe = "".join(c if c.isalnum() or c in " -_" else "_" for c in safe)
        safe = "_".join(safe.split())
        return safe[:50] or "untitled"

    def get_graph_data(self) -> Dict[str, Any]:
        """Get graph data structure for visualization."""
        if self._graph_cache:
            return self._graph_cache
        self.build_index()
        nodes = []
        links = []
        seen_links = set()
        for path_str, parsed in self._index.items():
            nodes.append(
                {
                    "id": parsed.title or parsed.path,
                    "path": parsed.path,
                    "tags": parsed.tags,
                    "type": parsed.frontmatter.get("type", "reference"),
                }
            )
            for wikilink in parsed.wikilinks:
                target = self.resolve_path(wikilink.note_name)
                if target:
                    target_title = target.stem
                    source_title = parsed.title or parsed.path
                    link_key = tuple(sorted([source_title, target_title]))
                    if link_key not in seen_links:
                        seen_links.add(link_key)
                        links.append(
                            {
                                "source": source_title,
                                "target": target_title,
                                "type": "wikilink",
                            }
                        )
        self._graph_cache = {"nodes": nodes, "links": links}
        return self._graph_cache

    def export_mermaid(self) -> str:
        """Export graph as Mermaid markdown."""
        graph = self.get_graph_data()
        lines = ["```mermaid", "graph TD"]
        for node in graph["nodes"]:
            node_id = node["id"].replace(" ", "_").replace("-", "_")
            lines.append(f'    {node_id}["{node["id"]}"]')
        for link in graph["links"]:
            source = link["source"].replace(" ", "_").replace("-", "_")
            target = link["target"].replace(" ", "_").replace("-", "_")
            lines.append(f"    {source} --> {target}")
        lines.append("```")
        return "\n".join(lines)

    def export_dot(self) -> str:
        """Export graph as GraphViz DOT format."""
        graph = self.get_graph_data()
        lines = ["digraph vault {"]
        for node in graph["nodes"]:
            node_id = node["id"].replace('"', '\\"')
            lines.append(f'    "{node_id}" [label="{node_id}"];')
        for link in graph["links"]:
            source = link["source"].replace('"', '\\"')
            target = link["target"].replace('"', '\\"')
            lines.append(f'    "{source}" -> "{target}";')
        lines.append("}")
        return "\n".join(lines)
