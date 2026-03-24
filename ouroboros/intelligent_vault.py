"""
Intelligent Vault System - Makes the vault active and self-maintaining.

Phase 1 Implementation:
1. Graph Engine - Build and query vault knowledge graph
2. Quality Metrics - Track note quality and staleness
3. Orphan Detection - Find disconnected notes
4. Caching - Cache graph for fast access

This makes the vault a living participant in Jo's evolution,
not just a passive repository.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


@dataclass
class VaultNote:
    """A single vault note with metadata."""

    path: str  # Relative path from vault root
    title: str  # Note title (from filename or first heading)
    content: str  # Full content
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    links: List[str] = field(default_factory=list)  # Outgoing wikilinks
    backlinks: List[str] = field(default_factory=list)  # Incoming links
    tags: List[str] = field(default_factory=list)
    last_modified: str = ""
    content_hash: str = ""
    word_count: int = 0
    line_count: int = 0

    @property
    def is_orphan(self) -> bool:
        """Note has no incoming or outgoing links."""
        return len(self.links) == 0 and len(self.backlinks) == 0

    @property
    def is_stale(self, days: int = 30) -> bool:
        """Note hasn't been modified in a long time."""
        if not self.last_modified:
            return True
        try:
            modified = datetime.fromisoformat(self.last_modified.replace("Z", "+00:00"))
            now = datetime.now(modified.tzinfo)
            return (now - modified).days > days
        except Exception:
            return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "title": self.title,
            "frontmatter": self.frontmatter,
            "links": self.links,
            "backlinks": self.backlinks,
            "tags": self.tags,
            "last_modified": self.last_modified,
            "content_hash": self.content_hash,
            "word_count": self.word_count,
            "line_count": self.line_count,
        }


@dataclass
class VaultGraph:
    """Knowledge graph of the vault."""

    notes: Dict[str, VaultNote] = field(default_factory=dict)  # path -> note
    links: Dict[str, Set[str]] = field(default_factory=dict)  # note -> [linked notes]
    backlinks: Dict[str, Set[str]] = field(default_factory=dict)  # note -> [notes linking to it]
    orphans: List[str] = field(default_factory=list)
    built_at: str = ""
    cache_hash: str = ""

    def get_note(self, path: str) -> Optional[VaultNote]:
        """Get note by path."""
        return self.notes.get(path)

    def get_linked_notes(self, path: str) -> List[str]:
        """Get notes linked from a note."""
        return list(self.links.get(path, set()))

    def get_backlinked_notes(self, path: str) -> List[str]:
        """Get notes that link to a note."""
        return list(self.backlinks.get(path, set()))

    def get_orphans(self) -> List[VaultNote]:
        """Get all orphan notes."""
        return [self.notes[path] for path in self.orphans if path in self.notes]

    def get_central_notes(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most connected notes (highest link count)."""
        connection_count = {}
        for note_path, linked in self.links.items():
            connection_count[note_path] = len(linked)
        for note_path, linking in self.backlinks.items():
            connection_count[note_path] = connection_count.get(note_path, 0) + len(linking)

        sorted_notes = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)
        return sorted_notes[:limit]

    def find_path(self, start: str, end: str, max_depth: int = 5) -> Optional[List[str]]:
        """Find shortest path between two notes using BFS."""
        if start not in self.notes or end not in self.notes:
            return None

        if start == end:
            return [start]

        visited = {start}
        queue = [(start, [start])]

        while queue and max_depth > 0:
            current, path = queue.pop(0)
            if len(path) > max_depth:
                continue

            # Check outgoing links
            for neighbor in self.links.get(current, set()):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

            # Check backlinks (bidirectional)
            for neighbor in self.backlinks.get(current, set()):
                if neighbor == end:
                    return path + [neighbor]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_count": len(self.notes),
            "orphan_count": len(self.orphans),
            "link_count": sum(len(v) for v in self.links.values()),
            "built_at": self.built_at,
            "cache_hash": self.cache_hash,
        }


@dataclass
class QualityMetrics:
    """Quality metrics for vault notes."""

    total_notes: int = 0
    orphan_count: int = 0
    stale_count: int = 0
    average_word_count: float = 0.0
    average_links: float = 0.0
    most_connected: List[Tuple[str, int]] = field(default_factory=list)
    least_connected: List[Tuple[str, int]] = field(default_factory=list)
    frontmatter_coverage: float = 0.0  # % of notes with frontmatter
    tag_coverage: float = 0.0  # % of notes with tags

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_notes": self.total_notes,
            "orphan_count": self.orphan_count,
            "stale_count": self.stale_count,
            "orphan_percentage": round(self.orphan_count / max(self.total_notes, 1) * 100, 1),
            "average_word_count": round(self.average_word_count, 0),
            "average_links": round(self.average_links, 1),
            "frontmatter_coverage": round(self.frontmatter_coverage * 100, 1),
            "tag_coverage": round(self.tag_coverage * 100, 1),
            "most_connected": self.most_connected[:5],
        }


class VaultGraphEngine:
    """Builds and maintains the vault knowledge graph.

    This is the core of the Intelligent Vault System.
    It makes the vault active rather than passive.
    """

    def __init__(self, vault_dir: Path):
        self._vault_dir = Path(vault_dir)
        self._cache_dir = self._vault_dir / ".vault" / "cache"
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._graph: Optional[VaultGraph] = None

    def _extract_wikilinks(self, content: str) -> List[str]:
        """Extract [[wikilinks]] from content."""
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        matches = re.findall(pattern, content)
        return [m.strip() for m in matches]

    def _extract_frontmatter(self, content: str) -> Tuple[Dict[str, Any], str]:
        """Extract YAML frontmatter from content."""
        frontmatter = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter_text = parts[1]
                body = parts[2]

                # Simple YAML parsing
                for line in frontmatter_text.split("\n"):
                    line = line.strip()
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip()
                        value = value.strip()
                        if value.startswith("[") and value.endswith("]"):
                            # List
                            value = [v.strip().strip("'\"") for v in value[1:-1].split(",")]
                        frontmatter[key] = value

        return frontmatter, body

    def _extract_tags(self, content: str, frontmatter: Dict[str, Any]) -> List[str]:
        """Extract tags from content and frontmatter."""
        tags = []

        # From frontmatter
        if "tags" in frontmatter:
            fm_tags = frontmatter["tags"]
            if isinstance(fm_tags, list):
                tags.extend(fm_tags)
            elif isinstance(fm_tags, str):
                tags.extend([t.strip() for t in fm_tags.split(",")])

        # From content (#tag)
        inline_tags = re.findall(r"#([a-zA-Z0-9_-]+)", content)
        tags.extend(inline_tags)

        return list(set(tags))

    def _get_note_title(self, path: Path, content: str) -> str:
        """Get note title from first heading or filename."""
        # Try first heading
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()

        # Fallback to filename
        return path.stem

    def build_graph(self, use_cache: bool = True) -> VaultGraph:
        """Build the vault knowledge graph."""
        # Check cache
        if use_cache:
            cached = self._load_cache()
            if cached:
                log.info("Vault graph loaded from cache")
                return cached

        log.info(f"Building vault graph from {self._vault_dir}")
        start_time = datetime.now()

        graph = VaultGraph()
        all_notes = {}

        # Scan all markdown files
        for md_file in self._vault_dir.rglob("*.md"):
            if ".vault" in str(md_file):
                continue  # Skip internal vault files

            try:
                content = md_file.read_text(encoding="utf-8")
                relative_path = str(md_file.relative_to(self._vault_dir))

                # Extract metadata
                frontmatter, body = self._extract_frontmatter(content)
                links = self._extract_wikilinks(body)
                tags = self._extract_tags(body, frontmatter)
                title = self._get_note_title(md_file, content)

                # Calculate hash
                content_hash = hashlib.md5(content.encode()).hexdigest()[:16]

                # Get modification time
                last_modified = datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()

                # Create note
                note = VaultNote(
                    path=relative_path,
                    title=title,
                    content=content,
                    frontmatter=frontmatter,
                    links=links,
                    tags=tags,
                    last_modified=last_modified,
                    content_hash=content_hash,
                    word_count=len(body.split()),
                    line_count=len(content.split("\n")),
                )

                all_notes[relative_path] = note

            except Exception as e:
                log.warning(f"Failed to process {md_file}: {e}")

        # Build link graph
        links = {}
        backlinks = {}

        for path, note in all_notes.items():
            # Resolve links to actual paths
            resolved_links = set()
            for link in note.links:
                # Try to find matching note
                for other_path in all_notes:
                    if link.lower() in other_path.lower() or link.lower() in all_notes[other_path].title.lower():
                        resolved_links.add(other_path)
                        break

            links[path] = resolved_links

            # Build backlinks
            for linked_path in resolved_links:
                if linked_path not in backlinks:
                    backlinks[linked_path] = set()
                backlinks[linked_path].add(path)

        # Add backlinks to notes
        for path, linking_notes in backlinks.items():
            if path in all_notes:
                all_notes[path].backlinks = list(linking_notes)

        # Find orphans
        orphans = [path for path, note in all_notes.items() if note.is_orphan]

        # Build final graph
        graph.notes = all_notes
        graph.links = links
        graph.backlinks = backlinks
        graph.orphans = orphans
        graph.built_at = datetime.now().isoformat()
        graph.cache_hash = hashlib.md5(json.dumps(sorted(all_notes.keys())).encode()).hexdigest()[:16]

        elapsed = (datetime.now() - start_time).total_seconds()
        log.info(f"Vault graph built: {len(all_notes)} notes, {len(orphans)} orphans ({elapsed:.2f}s)")

        # Cache the graph
        self._save_cache(graph)
        self._graph = graph

        return graph

    def get_affected_notes(self, changed_path: str) -> List[str]:
        """Find notes affected by a change to a specific note."""
        if not self._graph:
            self.build_graph()

        affected = set()

        # Notes that link to the changed note (backlinks)
        for backlink in self._graph.backlinks.get(changed_path, set()):
            affected.add(backlink)

        # Notes that the changed note links to
        for link in self._graph.links.get(changed_path, set()):
            affected.add(link)

        return list(affected)

    def get_quality_metrics(self) -> QualityMetrics:
        """Calculate vault quality metrics."""
        if not self._graph:
            self.build_graph()

        notes = list(self._graph.notes.values())
        if not notes:
            return QualityMetrics()

        total = len(notes)
        orphan_count = len(self._graph.orphans)

        # Stale notes (>30 days)
        stale_count = sum(1 for n in notes if n.is_stale)

        # Word count
        total_words = sum(n.word_count for n in notes)
        avg_words = total_words / total

        # Link count
        total_links = sum(len(n.links) for n in notes)
        avg_links = total_links / total

        # Frontmatter coverage
        with_frontmatter = sum(1 for n in notes if n.frontmatter)
        frontmatter_coverage = with_frontmatter / total

        # Tag coverage
        with_tags = sum(1 for n in notes if n.tags)
        tag_coverage = with_tags / total

        # Most/least connected
        connection_count = {}
        for note in notes:
            connection_count[note.path] = len(note.links) + len(note.backlinks)

        sorted_by_connections = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)

        return QualityMetrics(
            total_notes=total,
            orphan_count=orphan_count,
            stale_count=stale_count,
            average_word_count=avg_words,
            average_links=avg_links,
            most_connected=sorted_by_connections[:10],
            least_connected=sorted_by_connections[-10:],
            frontmatter_coverage=frontmatter_coverage,
            tag_coverage=tag_coverage,
        )

    def detect_orphans(self) -> List[VaultNote]:
        """Detect orphan notes (no incoming or outgoing links)."""
        if not self._graph:
            self.build_graph()

        return self._graph.get_orphans()

    def suggest_links(self, note_path: str, max_suggestions: int = 5) -> List[Tuple[str, float]]:
        """Suggest links for a note based on content similarity."""
        if not self._graph:
            self.build_graph()

        note = self._graph.get_note(note_path)
        if not note:
            return []

        suggestions = []
        note_words = set(note.content.lower().split())

        for other_path, other_note in self._graph.notes.items():
            if other_path == note_path:
                continue
            if other_path in note.links:
                continue  # Already linked

            # Simple word overlap similarity
            other_words = set(other_note.content.lower().split())
            overlap = len(note_words & other_words)
            similarity = overlap / max(len(note_words | other_words), 1)

            if similarity > 0.1:  # Threshold
                suggestions.append((other_path, similarity))

        suggestions.sort(key=lambda x: x[1], reverse=True)
        return suggestions[:max_suggestions]

    def _load_cache(self) -> Optional[VaultGraph]:
        """Load cached graph."""
        cache_file = self._cache_dir / "vault_graph.json"
        if not cache_file.exists():
            return None

        try:
            data = json.loads(cache_file.read_text(encoding="utf-8"))

            # Check if cache is stale
            vault_hash = self._get_vault_hash()
            if data.get("cache_hash") != vault_hash:
                log.info("Vault cache is stale, rebuilding")
                return None

            # Rebuild graph from cache
            graph = VaultGraph()
            graph.notes = {k: VaultNote(**v) for k, v in data.get("notes", {}).items()}
            graph.links = {k: set(v) for k, v in data.get("links", {}).items()}
            graph.backlinks = {k: set(v) for k, v in data.get("backlinks", {}).items()}
            graph.orphans = data.get("orphans", [])
            graph.built_at = data.get("built_at", "")
            graph.cache_hash = data.get("cache_hash", "")

            return graph
        except Exception as e:
            log.warning(f"Failed to load vault cache: {e}")
            return None

    def _save_cache(self, graph: VaultGraph) -> None:
        """Save graph to cache."""
        cache_file = self._cache_dir / "vault_graph.json"
        try:
            data = {
                "notes": {k: v.to_dict() for k, v in graph.notes.items()},
                "links": {k: list(v) for k, v in graph.links.items()},
                "backlinks": {k: list(v) for k, v in graph.backlinks.items()},
                "orphans": graph.orphans,
                "built_at": graph.built_at,
                "cache_hash": graph.cache_hash,
            }
            cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            log.debug(f"Vault graph cached to {cache_file}")
        except Exception as e:
            log.warning(f"Failed to cache vault graph: {e}")

    def _get_vault_hash(self) -> str:
        """Get hash of all vault files for cache invalidation."""
        all_paths = sorted(str(p) for p in self._vault_dir.rglob("*.md") if ".vault" not in str(p))
        combined = "".join(all_paths)
        return hashlib.md5(combined.encode()).hexdigest()[:16]


# Singleton instance
_vault_engine: Optional[VaultGraphEngine] = None


def get_vault_engine(vault_dir: Optional[Path] = None) -> VaultGraphEngine:
    """Get singleton vault graph engine."""
    global _vault_engine
    if _vault_engine is None:
        if vault_dir is None:
            vault_dir = Path(os.environ.get("REPO_DIR", ".")) / "vault"
        _vault_engine = VaultGraphEngine(vault_dir)
    return _vault_engine
