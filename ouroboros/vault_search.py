"""Vault Search — semantic search, topic clustering, knowledge gaps."""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.vault_engine import VaultGraphEngine, VaultNote, get_vault_engine

log = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A search result from vault."""

    note_path: str
    title: str
    relevance: float  # 0.0-1.0
    matched_content: str  # Snippet of matched content
    match_type: str  # "title", "content", "tag", "frontmatter"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.note_path,
            "title": self.title,
            "relevance": round(self.relevance, 3),
            "snippet": self.matched_content[:200],
            "match_type": self.match_type,
        }


@dataclass
class TopicCluster:
    """A cluster of related notes."""

    topic: str  # Topic name (derived from common tags/content)
    notes: List[str]  # Note paths in this cluster
    common_tags: List[str]  # Tags shared by notes in cluster
    central_note: str  # Most connected note in cluster
    coherence: float  # How related the notes are (0-1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "note_count": len(self.notes),
            "notes": self.notes[:10],
            "common_tags": self.common_tags,
            "central_note": self.central_note,
            "coherence": round(self.coherence, 3),
        }


@dataclass
class KnowledgeGap:
    """An identified gap in vault knowledge."""

    topic: str  # What topic is missing
    related_notes: List[str]  # Notes that reference this topic
    severity: str  # "high", "medium", "low"
    suggestion: str  # What to create

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "related_notes": self.related_notes[:5],
            "severity": self.severity,
            "suggestion": self.suggestion,
        }


class VaultSemanticSearch:
    """Semantic search for vault notes.

    Phase 3B: Find notes by meaning, not just keywords.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def search(self, query: str, max_results: int = 10) -> List[SearchResult]:
        """Search vault notes by query.

        Uses multiple matching strategies:
        1. Title match (highest relevance)
        2. Content keyword match
        3. Tag match
        4. Frontmatter match

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of search results sorted by relevance
        """
        if not self._engine._graph:
            self._engine.build_graph()

        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for path, note in self._engine._graph.notes.items():
            relevance = 0.0
            matched_content = ""
            match_type = ""

            # Title match (highest weight)
            title_lower = note.title.lower()
            if query_lower in title_lower:
                relevance += 0.5
                matched_content = note.title
                match_type = "title"
            elif any(word in title_lower for word in query_words):
                relevance += 0.3
                matched_content = note.title
                match_type = "title"

            # Content keyword match
            content_lower = note.content.lower()
            if query_lower in content_lower:
                relevance += 0.3
                # Find snippet around match
                idx = content_lower.find(query_lower)
                start = max(0, idx - 50)
                end = min(len(content_lower), idx + len(query_lower) + 50)
                matched_content = note.content[start:end].replace("\n", " ")
                match_type = "content"
            elif query_words:
                # Word overlap
                note_words = set(content_lower.split())
                overlap = len(query_words & note_words)
                relevance += (overlap / len(query_words)) * 0.2
                if overlap > 0 and not matched_content:
                    matched_content = note.content[:100].replace("\n", " ")
                    match_type = "content"

            # Tag match
            if note.tags:
                for tag in note.tags:
                    if query_lower in tag.lower():
                        relevance += 0.1
                        if not matched_content:
                            matched_content = f"Tag: {tag}"
                            match_type = "tag"

            # Frontmatter match
            if note.frontmatter:
                for key, value in note.frontmatter.items():
                    value_str = str(value).lower()
                    if query_lower in value_str:
                        relevance += 0.1
                        if not matched_content:
                            matched_content = f"{key}: {value}"
                            match_type = "frontmatter"

            # Add result if relevant
            if relevance > 0:
                results.append(
                    SearchResult(
                        note_path=path,
                        title=note.title,
                        relevance=min(1.0, relevance),
                        matched_content=matched_content,
                        match_type=match_type,
                    )
                )

        # Sort by relevance
        results.sort(key=lambda r: r.relevance, reverse=True)
        return results[:max_results]

    def find_related(self, note_path: str, max_results: int = 5) -> List[SearchResult]:
        """Find notes related to a specific note."""
        if not self._engine._graph:
            self._engine.build_graph()

        note = self._engine._graph.get_note(note_path)
        if not note:
            return []

        # Use note title and tags as search query
        search_terms = [note.title]
        if note.tags:
            search_terms.extend(note.tags)

        query = " ".join(search_terms)

        # Search but exclude the original note
        results = self.search(query, max_results=max_results + 1)
        return [r for r in results if r.note_path != note_path][:max_results]


class VaultTopicClustering:
    """Cluster notes by topic.

    Phase 3B: Group related notes automatically.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def get_clusters(self, min_cluster_size: int = 2) -> List[TopicCluster]:
        """Get topic clusters from vault notes.

        Groups notes by:
        1. Common tags
        2. Content similarity
        3. Link relationships
        """
        if not self._engine._graph:
            self._engine.build_graph()

        # Group by tags first
        tag_groups: Dict[str, List[str]] = {}
        for path, note in self._engine._graph.notes.items():
            for tag in note.tags:
                if tag not in tag_groups:
                    tag_groups[tag] = []
                tag_groups[tag].append(path)

        clusters = []
        used_notes = set()

        # Create clusters from tag groups
        for tag, note_paths in tag_groups.items():
            if len(note_paths) >= min_cluster_size:
                # Find central note (most connections)
                central_note = self._find_central_note(note_paths)

                # Calculate coherence (how related the notes are)
                coherence = self._calculate_coherence(note_paths)

                cluster = TopicCluster(
                    topic=tag.replace("-", " ").replace("_", " ").title(),
                    notes=note_paths,
                    common_tags=[tag],
                    central_note=central_note,
                    coherence=coherence,
                )
                clusters.append(cluster)
                used_notes.update(note_paths)

        # Add ungrouped notes as "General" cluster
        all_notes = set(self._engine._graph.notes.keys())
        ungrouped = all_notes - used_notes
        if ungrouped:
            central = self._find_central_note(list(ungrouped))
            clusters.append(
                TopicCluster(
                    topic="General/Uncategorized",
                    notes=list(ungrouped),
                    common_tags=[],
                    central_note=central,
                    coherence=0.0,
                )
            )

        # Sort by coherence (most coherent first)
        clusters.sort(key=lambda c: c.coherence, reverse=True)
        return clusters

    def _find_central_note(self, note_paths: List[str]) -> str:
        """Find the most connected note in a list."""
        if not self._engine._graph:
            return note_paths[0] if note_paths else ""

        best_note = note_paths[0]
        best_score = 0

        for path in note_paths:
            connections = len(self._engine._graph.links.get(path, set())) + len(
                self._engine._graph.backlinks.get(path, set())
            )
            if connections > best_score:
                best_score = connections
                best_note = path

        return best_note

    def _calculate_coherence(self, note_paths: List[str]) -> float:
        """Calculate how related notes in a cluster are."""
        if not note_paths or not self._engine._graph:
            return 0.0

        # Count internal links (links between notes in the cluster)
        internal_links = 0
        possible_links = len(note_paths) * (len(note_paths) - 1)

        for path in note_paths:
            linked = self._engine._graph.links.get(path, set())
            internal_links += len(linked & set(note_paths))

        if possible_links == 0:
            return 0.0

        return internal_links / possible_links


class VaultKnowledgeGaps:
    """Identify gaps in vault knowledge.

    Phase 3B: Find what's missing from the vault.
    """

    def __init__(self, engine: VaultGraphEngine):
        self._engine = engine

    def detect_gaps(self) -> List[KnowledgeGap]:
        """Detect knowledge gaps in the vault.

        Identifies:
        1. Topics mentioned but not documented
        2. Unlinked concepts
        3. Missing documentation for tools/concepts
        """
        if not self._engine._graph:
            self._engine.build_graph()

        gaps = []

        # Find concepts mentioned in content but not as notes
        mentioned_topics = self._find_mentioned_topics()
        existing_titles = {note.title.lower() for note in self._engine._graph.notes.values()}

        for topic, mention_count in mentioned_topics.items():
            if topic.lower() not in existing_titles and mention_count >= 2:
                gaps.append(
                    KnowledgeGap(
                        topic=topic,
                        related_notes=self._find_notes_mentioning(topic),
                        severity="high" if mention_count >= 5 else "medium",
                        suggestion=f"Create a note documenting '{topic}'",
                    )
                )

        # Find notes with no content (just frontmatter)
        for path, note in self._engine._graph.notes.items():
            if note.word_count < 20 and note.frontmatter:
                gaps.append(
                    KnowledgeGap(
                        topic=f"Stub note: {note.title}",
                        related_notes=[path],
                        severity="low",
                        suggestion=f"Expand '{note.title}' with more content",
                    )
                )

        return gaps

    def _find_mentioned_topics(self) -> Dict[str, int]:
        """Find topics mentioned across multiple notes."""
        topic_counts: Dict[str, int] = {}

        # Look for capitalized terms that might be concepts
        for note in self._engine._graph.notes.values():
            # Find potential topic names (capitalized words)
            words = note.content.split()
            for i, word in enumerate(words):
                if word[0:1].isupper() and len(word) > 3:
                    # Check if it's a multi-word topic
                    if i > 0 and words[i - 1][-1:] in ".!?":
                        topic = word.rstrip(".,;:!?")
                        topic_counts[topic] = topic_counts.get(topic, 0) + 1

        return topic_counts

    def _find_notes_mentioning(self, topic: str) -> List[str]:
        """Find notes that mention a specific topic."""
        mentioning = []
        topic_lower = topic.lower()

        for path, note in self._engine._graph.notes.items():
            if topic_lower in note.content.lower():
                mentioning.append(path)

        return mentioning[:10]


def vault_semantic_search(
    query: str,
    vault_dir: Optional[Path] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Search vault notes semantically.

    Main entry point for semantic search.

    Args:
        query: Search query
        vault_dir: Vault directory path
        max_results: Maximum results to return

    Returns:
        List of search results as dictionaries
    """
    engine = get_vault_engine(vault_dir)
    search = VaultSemanticSearch(engine)
    results = search.search(query, max_results)
    return [r.to_dict() for r in results]


def vault_topic_clusters(
    vault_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Get topic clusters from vault.

    Main entry point for topic clustering.

    Args:
        vault_dir: Vault directory path

    Returns:
        List of topic clusters as dictionaries
    """
    engine = get_vault_engine(vault_dir)
    clustering = VaultTopicClustering(engine)
    clusters = clustering.get_clusters()
    return [c.to_dict() for c in clusters]


def vault_knowledge_gaps(
    vault_dir: Optional[Path] = None,
) -> List[Dict[str, Any]]:
    """Detect knowledge gaps in vault.

    Main entry point for gap detection.

    Args:
        vault_dir: Vault directory path

    Returns:
        List of knowledge gaps as dictionaries
    """
    engine = get_vault_engine(vault_dir)
    gaps = VaultKnowledgeGaps(engine)
    detected = gaps.detect_gaps()
    return [g.to_dict() for g in detected]
