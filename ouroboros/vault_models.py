"""Data models for the Intelligent Vault System."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


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


@dataclass
class TopicCluster:
    """A cluster of related notes."""

    topic: str
    notes: List[str]
    common_tags: List[str]
    central_note: str
    coherence: float  # 0.0 to 1.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "notes": self.notes,
            "common_tags": self.common_tags,
            "central_note": self.central_note,
            "coherence": round(self.coherence, 2),
            "size": len(self.notes),
        }


@dataclass
class KnowledgeGap:
    """A gap in vault knowledge."""

    topic: str
    related_notes: List[str]
    severity: str  # "low", "medium", "high"
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "related_notes": self.related_notes,
            "severity": self.severity,
            "suggestion": self.suggestion,
        }