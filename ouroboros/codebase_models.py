"""Shared data models for codebase analysis.

This module contains data classes used by both codebase_graph.py and codebase_analysis.py
to avoid circular imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GraphNode:
    """A node in the codebase graph."""

    id: str  # e.g., "file:ouroboros/loop.py" or "func:run_llm_loop"
    type: str  # "file", "class", "function", "import"
    name: str
    file_path: str
    line_number: int = 0
    summary: str = ""
    layer: str = ""  # "core", "tools", "utils", "test"
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    """An edge in the codebase graph."""

    source: str  # Node ID
    target: str  # Node ID
    relation: str  # "imports", "calls", "contains", "inherits"
    confidence: float = 1.0  # 0.0-1.0: AST-resolved=0.9, structural=1.0, heuristic=0.3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodebaseGraph:
    """Knowledge graph of a codebase."""

    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    scanned_at: str = ""
    repo_dir: str = ""

    def add_node(self, node: GraphNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: GraphEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_file_nodes(self, file_path: str) -> List[GraphNode]:
        """Get all nodes in a file."""
        return [n for n in self.nodes.values() if n.file_path == file_path]

    def get_edges_from(self, node_id: str) -> List[GraphEdge]:
        """Get all edges from a node."""
        return [e for e in self.edges if e.source == node_id]

    def get_edges_to(self, node_id: str) -> List[GraphEdge]:
        """Get all edges to a node."""
        return [e for e in self.edges if e.target == node_id]

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes that this node depends on."""
        return [e.target for e in self.edges if e.source == node_id and e.relation == "imports"]

    def get_dependents(self, node_id: str) -> List[str]:
        """Get all nodes that depend on this node."""
        return [e.source for e in self.edges if e.target == node_id and e.relation == "imports"]

    def search(self, query: str) -> List[GraphNode]:
        """Search nodes by name or summary."""
        query_lower = query.lower()
        results = []
        for node in self.nodes.values():
            if (
                query_lower in node.name.lower()
                or query_lower in node.summary.lower()
                or query_lower in node.file_path.lower()
            ):
                results.append(node)
        return results

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "scanned_at": self.scanned_at,
            "repo_dir": self.repo_dir,
            "node_count": len(self.nodes),
            "edge_count": len(self.edges),
            "nodes": [
                {
                    "id": n.id,
                    "type": n.type,
                    "name": n.name,
                    "file_path": n.file_path,
                    "line_number": n.line_number,
                    "summary": n.summary,
                    "layer": n.layer,
                    "metadata": n.metadata,
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "relation": e.relation,
                    "confidence": e.confidence,
                    "metadata": e.metadata,
                }
                for e in self.edges
            ],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> CodebaseGraph:
        """Create from dictionary."""
        graph = cls(
            scanned_at=data.get("scanned_at", ""),
            repo_dir=data.get("repo_dir", ""),
        )
        for node_data in data.get("nodes", []):
            node = GraphNode(
                id=node_data["id"],
                type=node_data["type"],
                name=node_data["name"],
                file_path=node_data["file_path"],
                line_number=node_data.get("line_number", 0),
                summary=node_data.get("summary", ""),
                layer=node_data.get("layer", ""),
                metadata=node_data.get("metadata", {}),
            )
            graph.nodes[node.id] = node

        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                relation=edge_data["relation"],
                confidence=edge_data.get("confidence", 1.0),
                metadata=edge_data.get("metadata", {}),
            )
            graph.edges.append(edge)

        return graph
