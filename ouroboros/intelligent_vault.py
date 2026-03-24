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


# ============================================================================
# PHASE 2: Self-Healing & Quality Guardrails
# ============================================================================


@dataclass
class LinkSuggestion:
    """A suggested link between notes."""

    source_path: str  # Note that needs the link
    target_path: str  # Note to link to
    similarity: float  # Content similarity score
    reason: str  # Why this link is suggested
    confidence: float  # How confident we are

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source_path,
            "target": self.target_path,
            "similarity": round(self.similarity, 3),
            "reason": self.reason,
            "confidence": round(self.confidence, 3),
        }


@dataclass
class QualityViolation:
    """A quality violation found in a note."""

    note_path: str
    violation_type: str  # "missing_frontmatter", "no_tags", "stale", "orphan"
    severity: str  # "error", "warning", "info"
    message: str
    suggested_fix: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_path": self.note_path,
            "type": self.violation_type,
            "severity": self.severity,
            "message": self.message,
            "suggested_fix": self.suggested_fix,
        }


@dataclass
class VaultHealthReport:
    """Complete vault health report."""

    timestamp: str
    total_notes: int
    orphan_count: int
    stale_count: int
    missing_frontmatter: int
    missing_tags: int
    quality_score: float  # 0-100
    violations: List[QualityViolation] = field(default_factory=list)
    link_suggestions: List[LinkSuggestion] = field(default_factory=list)
    improvement_actions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_notes": self.total_notes,
            "orphan_count": self.orphan_count,
            "stale_count": self.stale_count,
            "missing_frontmatter": self.missing_frontmatter,
            "missing_tags": self.missing_tags,
            "quality_score": round(self.quality_score, 1),
            "violations": [v.to_dict() for v in self.violations],
            "link_suggestions": [s.to_dict() for s in self.link_suggestions],
            "improvement_actions": self.improvement_actions,
        }


class VaultGuardrails:
    """Quality guardrails for vault maintenance.

    Prevents quality drift and maintains vault integrity.
    """

    # Quality thresholds
    MAX_ORPHAN_PERCENTAGE = 0.3  # Max 30% orphans
    MAX_STALE_PERCENTAGE = 0.2  # Max 20% stale notes
    MIN_WORD_COUNT = 50  # Minimum words per note
    REQUIRE_FRONTMATTER = True  # Require YAML frontmatter
    REQUIRE_TAGS = False  # Tags are optional

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def check_note(self, note: VaultNote) -> List[QualityViolation]:
        """Check a single note for quality violations."""
        violations = []

        # Check frontmatter
        if self.REQUIRE_FRONTMATTER and not note.frontmatter:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="missing_frontmatter",
                    severity="warning",
                    message="Note has no YAML frontmatter",
                    suggested_fix="Add frontmatter with description, tags, and created date",
                )
            )

        # Check tags
        if self.REQUIRE_TAGS and not note.tags:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="missing_tags",
                    severity="info",
                    message="Note has no tags",
                    suggested_fix="Add tags to categorize the note",
                )
            )

        # Check word count
        if note.word_count < self.MIN_WORD_COUNT:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="low_word_count",
                    severity="warning",
                    message=f"Note has only {note.word_count} words (minimum: {self.MIN_WORD_COUNT})",
                    suggested_fix="Expand the note with more detail",
                )
            )

        # Check if orphan
        if note.is_orphan:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="orphan",
                    severity="error",
                    message="Note has no incoming or outgoing links",
                    suggested_fix="Link to related notes using [[wikilinks]]",
                )
            )

        # Check if stale
        if note.is_stale:
            violations.append(
                QualityViolation(
                    note_path=note.path,
                    violation_type="stale",
                    severity="info",
                    message="Note hasn't been modified in over 30 days",
                    suggested_fix="Review and update if needed",
                )
            )

        return violations

    def check_all_notes(self) -> List[QualityViolation]:
        """Check all notes for quality violations."""
        if not self._engine._graph:
            self._engine.build_graph()

        all_violations = []
        for note in self._engine._graph.notes.values():
            violations = self.check_note(note)
            all_violations.extend(violations)

        return all_violations

    def calculate_quality_score(self, violations: List[QualityViolation], total_notes: int = 0) -> float:
        """Calculate overall vault quality score (0-100).

        More realistic scoring based on:
        - Percentage of notes with issues
        - Severity weighting
        - Diminishing returns for many violations
        """
        if not violations:
            return 100.0

        if total_notes == 0:
            total_notes = len(set(v.note_path for v in violations))

        # Count violations by type
        orphan_count = sum(1 for v in violations if v.violation_type == "orphan")
        frontmatter_count = sum(1 for v in violations if v.violation_type == "missing_frontmatter")
        low_word_count = sum(1 for v in violations if v.violation_type == "low_word_count")
        other_count = len(violations) - orphan_count - frontmatter_count - low_word_count

        # Calculate penalties (lower = better score)
        # Orphan penalty: 3 points per orphan (most impactful)
        orphan_penalty = orphan_count * 3

        # Frontmatter penalty: 2 points per missing frontmatter
        frontmatter_penalty = frontmatter_count * 2

        # Low word count penalty: 1 point per low word count
        low_word_penalty = low_word_count * 1

        # Other penalties: 1 point each
        other_penalty = other_count * 1

        total_penalty = orphan_penalty + frontmatter_penalty + low_word_penalty + other_penalty

        # Normalize based on total notes (more realistic)
        # Max penalty would be if ALL notes had all issues
        max_possible_penalty = total_notes * 6  # orphan + frontmatter + low_word per note

        # Calculate score
        if max_possible_penalty > 0:
            score = max(0, 100 - (total_penalty / max_possible_penalty * 100))
        else:
            score = 100.0

        return score


class VaultAutoLinker:
    """Automatically suggest and create links for orphan notes.

    Reduces orphan count by suggesting related notes to link.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def suggest_links_for_note(self, note: VaultNote, max_suggestions: int = 5) -> List[LinkSuggestion]:
        """Suggest links for a single note."""
        if not self._engine._graph:
            self._engine.build_graph()

        suggestions = []
        note_words = set(note.content.lower().split())

        for other_path, other_note in self._engine._graph.notes.items():
            if other_path == note.path:
                continue
            if other_path in note.links:
                continue  # Already linked

            # Calculate similarity
            other_words = set(other_note.content.lower().split())
            overlap = len(note_words & other_words)
            total_words = len(note_words | other_words)
            similarity = overlap / max(total_words, 1)

            # Skip low similarity
            if similarity < 0.05:
                continue

            # Determine reason
            reason = ""
            if note.title.lower() in other_note.content.lower():
                reason = "Note title mentioned in content"
                similarity += 0.2
            elif other_note.title.lower() in note.content.lower():
                reason = "Related note title mentioned"
                similarity += 0.2
            elif any(tag in other_note.tags for tag in note.tags):
                reason = "Shared tags"
                similarity += 0.1
            else:
                reason = "Content similarity"

            confidence = min(1.0, similarity)

            suggestions.append(
                LinkSuggestion(
                    source_path=note.path,
                    target_path=other_path,
                    similarity=similarity,
                    reason=reason,
                    confidence=confidence,
                )
            )

        # Sort by similarity
        suggestions.sort(key=lambda s: s.similarity, reverse=True)
        return suggestions[:max_suggestions]

    def suggest_links_for_orphans(self, max_per_note: int = 3) -> List[LinkSuggestion]:
        """Suggest links for all orphan notes."""
        if not self._engine._graph:
            self._engine.build_graph()

        all_suggestions = []
        orphans = self._engine.detect_orphans()

        for orphan in orphans:
            suggestions = self.suggest_links_for_note(orphan, max_suggestions=max_per_note)
            all_suggestions.extend(suggestions)

        # Sort by confidence
        all_suggestions.sort(key=lambda s: s.confidence, reverse=True)
        return all_suggestions

    def create_link(self, source_path: str, target_path: str) -> bool:
        """Create a wikilink in the source note pointing to the target note."""
        if not self._engine._graph:
            self._engine.build_graph()

        source_note = self._engine._graph.get_note(source_path)
        target_note = self._engine._graph.get_note(target_path)

        if not source_note or not target_note:
            return False

        # Read source file
        source_file = self._engine._vault_dir / source_path
        if not source_file.exists():
            return False

        try:
            content = source_file.read_text(encoding="utf-8")

            # Check if link already exists
            link_text = f"[[{target_note.title}]]"
            if link_text in content:
                return False

            # Add link at the end of the note
            # Find the end of the content (before any trailing whitespace)
            content = content.rstrip()
            content += f"\n\n---\n## Related\n\n- {link_text}\n"

            source_file.write_text(content, encoding="utf-8")
            log.info(f"Created link: {source_path} -> {target_path}")
            return True

        except Exception as e:
            log.error(f"Failed to create link: {e}")
            return False


def get_vault_health_report(vault_dir: Optional[Path] = None) -> VaultHealthReport:
    """Generate a complete vault health report."""
    engine = get_vault_engine(vault_dir)
    guardrails = VaultGuardrails(engine)
    linker = VaultAutoLinker(engine)

    # Build graph
    graph = engine.build_graph()

    # Get metrics
    metrics = engine.get_quality_metrics()

    # Check violations
    violations = guardrails.check_all_notes()

    # Get link suggestions for orphans
    link_suggestions = linker.suggest_links_for_orphans(max_per_note=2)

    # Calculate quality score
    quality_score = guardrails.calculate_quality_score(violations, total_notes=metrics.total_notes)

    # Generate improvement actions
    actions = []
    if metrics.orphan_count > 0:
        actions.append(f"Link {metrics.orphan_count} orphan notes")
    if metrics.frontmatter_coverage < 0.5:
        actions.append(f"Add frontmatter to {int((1 - metrics.frontmatter_coverage) * metrics.total_notes)} notes")
    if metrics.tag_coverage < 0.5:
        actions.append(f"Add tags to {int((1 - metrics.tag_coverage) * metrics.total_notes)} notes")
    if metrics.stale_count > 0:
        actions.append(f"Review {metrics.stale_count} stale notes")

    return VaultHealthReport(
        timestamp=datetime.now().isoformat(),
        total_notes=metrics.total_notes,
        orphan_count=metrics.orphan_count,
        stale_count=metrics.stale_count,
        missing_frontmatter=metrics.total_notes - int(metrics.frontmatter_coverage * metrics.total_notes),
        missing_tags=metrics.total_notes - int(metrics.tag_coverage * metrics.total_notes),
        quality_score=quality_score,
        violations=violations,
        link_suggestions=link_suggestions,
        improvement_actions=actions,
    )


# ============================================================================
# PHASE 3A: Execute Improvements (Auto-Fix)
# ============================================================================


@dataclass
class ImprovementResult:
    """Result of executing an improvement."""

    note_path: str
    improvement_type: str  # "link_added", "frontmatter_added", "tag_added"
    success: bool
    message: str
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "note_path": self.note_path,
            "type": self.improvement_type,
            "success": self.success,
            "message": self.message,
            "details": self.details,
        }


class VaultAutoFixer:
    """Execute improvements to fix vault issues.

    Phase 3A: Actually applies fixes, not just suggestions.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def fix_orphan_notes(self, max_fixes: int = 50) -> List[ImprovementResult]:
        """Auto-link orphan notes based on content similarity.

        Args:
            max_fixes: Maximum number of fixes to apply

        Returns:
            List of improvement results
        """
        if not self._engine._graph:
            self._engine.build_graph()

        linker = VaultAutoLinker(self._engine)
        suggestions = linker.suggest_links_for_orphans(max_per_note=1)

        results = []
        fixed_notes = set()

        for suggestion in suggestions[:max_fixes]:
            if suggestion.source_path in fixed_notes:
                continue

            # Only fix high-confidence suggestions
            if suggestion.confidence < 0.5:
                continue

            success = linker.create_link(
                suggestion.source_path,
                suggestion.target_path,
            )

            results.append(
                ImprovementResult(
                    note_path=suggestion.source_path,
                    improvement_type="link_added",
                    success=success,
                    message=f"Linked to {suggestion.target_path}" if success else "Failed to add link",
                    details={
                        "target": suggestion.target_path,
                        "similarity": suggestion.similarity,
                        "reason": suggestion.reason,
                    },
                )
            )

            if success:
                fixed_notes.add(suggestion.source_path)

        return results

    def add_frontmatter(self, note_path: str) -> ImprovementResult:
        """Add YAML frontmatter to a note that's missing it."""
        note_file = self._engine._vault_dir / note_path
        if not note_file.exists():
            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=False,
                message="Note file not found",
            )

        try:
            content = note_file.read_text(encoding="utf-8")

            # Check if already has frontmatter
            if content.startswith("---"):
                return ImprovementResult(
                    note_path=note_path,
                    improvement_type="frontmatter_added",
                    success=False,
                    message="Note already has frontmatter",
                )

            # Generate frontmatter
            title = Path(note_path).stem
            # Try to get title from first heading
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("# "):
                    title = line[2:].strip()
                    break

            # Extract any existing tags from content
            tags = re.findall(r"#([a-zA-Z0-9_-]+)", content)
            tags_str = f"\n  - {chr(10) + '  - '.join(tags)}" if tags else " []"

            # Get folder for category
            folder = str(Path(note_path).parent)
            category = folder.split("/")[-1] if "/" in folder else folder.split("\\")[-1]

            # Create frontmatter
            frontmatter = f"""---
title: {title}
created: {datetime.now().strftime("%Y-%m-%d")}
category: {category}
tags: {tags_str}

---

"""
            new_content = frontmatter + content
            note_file.write_text(new_content, encoding="utf-8")

            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=True,
                message=f"Added frontmatter with title '{title}'",
                details={"title": title, "category": category, "tags": tags},
            )

        except Exception as e:
            return ImprovementResult(
                note_path=note_path,
                improvement_type="frontmatter_added",
                success=False,
                message=f"Error: {e}",
            )

    def fix_missing_frontmatter(self, max_fixes: int = 20) -> List[ImprovementResult]:
        """Add frontmatter to notes missing it.

        Args:
            max_fixes: Maximum number of fixes to apply

        Returns:
            List of improvement results
        """
        if not self._engine._graph:
            self._engine.build_graph()

        results = []
        fixed_count = 0

        for path, note in self._engine._graph.notes.items():
            if fixed_count >= max_fixes:
                break

            if not note.frontmatter:
                result = self.add_frontmatter(path)
                results.append(result)
                if result.success:
                    fixed_count += 1

        return results

    def auto_fix_violations(self, max_fixes: int = 30) -> Dict[str, Any]:
        """Auto-fix vault quality violations.

        Applies fixes in priority order:
        1. Add frontmatter to notes missing it
        2. Link orphan notes (high confidence only)

        Args:
            max_fixes: Maximum total fixes to apply

        Returns:
            Summary of fixes applied
        """
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_fixes": 0,
            "successful_fixes": 0,
            "failed_fixes": 0,
            "fixes_by_type": {},
            "details": [],
        }

        # Priority 1: Add frontmatter (most impactful)
        frontmatter_results = self.fix_missing_frontmatter(max_fixes // 2)
        for r in frontmatter_results:
            results["details"].append(r.to_dict())
            results["total_fixes"] += 1
            if r.success:
                results["successful_fixes"] += 1
                results["fixes_by_type"]["frontmatter_added"] = results["fixes_by_type"].get("frontmatter_added", 0) + 1
            else:
                results["failed_fixes"] += 1

        # Priority 2: Link orphan notes
        remaining = max_fixes - results["total_fixes"]
        if remaining > 0:
            link_results = self.fix_orphan_notes(remaining)
            for r in link_results:
                results["details"].append(r.to_dict())
                results["total_fixes"] += 1
                if r.success:
                    results["successful_fixes"] += 1
                    results["fixes_by_type"]["link_added"] = results["fixes_by_type"].get("link_added", 0) + 1
                else:
                    results["failed_fixes"] += 1

        return results


def execute_vault_improvements(
    vault_dir: Optional[Path] = None,
    max_fixes: int = 30,
) -> Dict[str, Any]:
    """Execute vault improvements (Phase 3A).

    This is the main entry point for auto-fixing vault issues.

    Args:
        vault_dir: Vault directory path
        max_fixes: Maximum number of fixes to apply

    Returns:
        Summary of improvements made
    """
    engine = get_vault_engine(vault_dir)
    fixer = VaultAutoFixer(engine)

    # Get initial state
    initial_report = get_vault_health_report(vault_dir)
    initial_score = initial_report.quality_score

    # Execute fixes
    results = fixer.auto_fix_violations(max_fixes)

    # Rebuild graph to reflect changes
    engine._graph = None  # Invalidate cache
    final_report = get_vault_health_report(vault_dir)
    final_score = final_report.quality_score

    # Add comparison to results
    results["quality_score_before"] = initial_score
    results["quality_score_after"] = final_score
    results["quality_improvement"] = final_score - initial_score

    return results
