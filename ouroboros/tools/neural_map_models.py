"""Shared data models for neural map.

This module contains data classes used by neural_map.py, neural_map_scan.py, and neural_map_tools.py
to avoid circular imports.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set


@dataclass
class Concept:
    """A concept in the knowledge graph."""

    id: str
    name: str
    type: str  # file, function, class, concept, tool, topic
    path: str = ""
    connections: List[str] = field(default_factory=list)
    content: str = ""
    tags: List[str] = field(default_factory=list)


@dataclass
class Connection:
    """A connection between concepts."""

    source: str
    target: str
    type: str  # import, call, link, reference, implements, extends
    strength: float = 1.0
    confidence: float = 1.0  # 0.0-1.0: AST-resolved=0.9, regex=0.3, link=0.7


class NeuralMap:
    """Knowledge graph representing Jo's understanding."""

    def __init__(self):
        self.concepts: Dict[str, Concept] = {}
        self.connections: List[Connection] = []
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)

    def add_concept(self, concept: Concept) -> None:
        self.concepts[concept.id] = concept

    def add_connection(
        self,
        source: str,
        target: str,
        conn_type: str,
        strength: float = 1.0,
        confidence: float = 1.0,
    ) -> None:
        if source not in self.concepts or target not in self.concepts:
            return

        conn = Connection(source=source, target=target, type=conn_type, strength=strength, confidence=confidence)
        self.connections.append(conn)
        self._adjacency[source].add(target)

        if conn_type in ("import", "imports", "call", "calls", "link"):
            self._adjacency[target].add(source)

        self.concepts[source].connections.append(target)
        if conn_type in ("import", "imports", "call", "calls", "link"):
            self.concepts[target].connections.append(source)

    def get_related(self, concept_id: str, max_depth: int = 2) -> List[str]:
        """Get related concepts up to max_depth."""
        if concept_id not in self.concepts:
            return []

        visited = set()
        queue = [(concept_id, 0)]
        result = []

        while queue:
            current, depth = queue.pop(0)
            if current in visited or depth > max_depth:
                continue

            visited.add(current)
            if current != concept_id:
                result.append(current)

            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append((neighbor, depth + 1))

        return result

    def find_path(self, source: str, target: str, max_depth: int = 5) -> Optional[List[str]]:
        """Find shortest path between concepts."""
        if source not in self.concepts or target not in self.concepts:
            return None

        visited = set()
        queue = [(source, [source])]

        while queue:
            current, path = queue.pop(0)

            if current == target:
                return path

            if len(path) > max_depth:
                continue

            if current in visited:
                continue
            visited.add(current)

            for neighbor in self._adjacency.get(current, set()):
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))

        return None

    def search(self, query: str, limit: int = 10) -> List[Concept]:
        """Search concepts by name or content."""
        query_lower = query.lower()
        results = []

        for concept in self.concepts.values():
            if (
                query_lower in concept.name.lower()
                or query_lower in concept.content.lower()
                or any(query_lower in tag.lower() for tag in concept.tags)
            ):
                results.append(concept)

        return results[:limit]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "concepts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "type": c.type,
                    "path": c.path,
                    "connections": c.connections,
                    "content": c.content[:200] if c.content else "",
                    "tags": c.tags,
                }
                for c in self.concepts.values()
            ],
            "connections": [
                {
                    "source": c.source,
                    "target": c.target,
                    "type": c.type,
                    "strength": c.strength,
                    "confidence": c.confidence,
                }
                for c in self.connections
            ],
            "stats": {
                "concept_count": len(self.concepts),
                "connection_count": len(self.connections),
            },
        }

    def find_related(self, concept_id: str, depth: int = 1) -> List[Concept]:
        """Find concepts related to a given concept."""
        if concept_id not in self.concepts:
            return []

        result = []
        visited = {concept_id}
        current_level = {concept_id}

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                for neighbor in self._adjacency[node]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        next_level.add(neighbor)
                        result.append(self.concepts[neighbor])
            current_level = next_level

        return result

    def get_clusters(self) -> List[List[str]]:
        """Find clusters using Louvain community detection if available, else DFS connected components."""
        try:
            import community as community_louvain
            import networkx as nx

            return self._get_clusters_louvain(community_louvain, nx)
        except Exception:
            return self._get_clusters_dfs()

    def _get_clusters_louvain(self, community_louvain: Any, nx: Any) -> List[List[str]]:
        """Louvain community detection for better functional grouping."""
        G = nx.Graph()
        for concept_id in self.concepts:
            G.add_node(concept_id)
        for conn in self.connections:
            w = conn.strength * conn.confidence
            if G.has_edge(conn.source, conn.target):
                G[conn.source][conn.target]["weight"] += w
            else:
                G.add_edge(conn.source, conn.target, weight=w)

        if len(G.nodes) <= 1 or len(G.edges) == 0:
            return [list(G.nodes)] if G.nodes else []

        partition = community_louvain.best_partition(G, weight="weight")

        groups: Dict[int, List[str]] = {}
        for node_id, comm_id in partition.items():
            groups.setdefault(comm_id, []).append(node_id)

        # Sort by cluster size descending
        return sorted(groups.values(), key=len, reverse=True)

    def _get_clusters_dfs(self) -> List[List[str]]:
        """Fallback: DFS connected components (no external deps)."""
        visited: Set[str] = set()
        clusters: List[List[str]] = []

        def dfs(node: str, cluster: List[str]) -> None:
            visited.add(node)
            cluster.append(node)
            for neighbor in self._adjacency[node]:
                if neighbor not in visited:
                    dfs(neighbor, cluster)

        for concept_id in self.concepts:
            if concept_id not in visited:
                cluster = []
                dfs(concept_id, cluster)
                if cluster:
                    clusters.append(cluster)

        return clusters
