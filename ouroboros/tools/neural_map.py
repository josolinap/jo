"""Neural Mapping System - Jo's knowledge graph and connection finder.

A neuron finding all connections, making all connections.

This system maps relationships between:
- Code files (imports, function calls, class relationships)
- Concepts (wikilinks, tags, themes)
- Tools (what uses what, dependencies)
- Knowledge (topics, ideas, patterns)

The goal: Jo can understand the full picture and find/create connections.
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


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

    def find_path(self, source: str, target: str) -> Optional[List[str]]:
        """Find shortest path between two concepts."""
        if source not in self.concepts or target not in self.concepts:
            return None

        if source == target:
            return [source]

        visited = {source}
        queue = [(source, [source])]

        while queue:
            node, path = queue.pop(0)
            for neighbor in self._adjacency[node]:
                if neighbor == target:
                    return path + [target]
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [neighbor]))

        return None

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


# Re-export scan functions from neural_map_scan for backward compatibility
from ouroboros.tools.neural_map_scan import (  # noqa: E402
    _scan_codebase,
    _scan_vault,
    _scan_tools,
    _build_unified_map,
)


def _neural_map(ctx: ToolContext, depth: int = 2) -> str:
    """Build and return neural map of Jo's knowledge."""
    log.info("Building neural map...")

    neural_map = _build_unified_map(ctx)

    lines = [
        "## Neural Map of Jo's Knowledge",
        "",
        f"**Concepts:** {len(neural_map.concepts)}",
        f"**Connections:** {len(neural_map.connections)}",
        "",
    ]

    # Check which clustering method is used
    try:
        import community as _c  # noqa: F401
        import networkx as _n  # noqa: F401

        lines.append("**Clustering:** Louvain community detection (weighted)")
    except Exception:
        lines.append("**Clustering:** DFS connected components (install python-louvain + networkx for Louvain)")
    lines.append("")

    lines.append("### Clusters (Related Groups)")
    lines.append("")

    clusters = neural_map.get_clusters()
    for i, cluster in enumerate(clusters[:10], 1):
        if len(cluster) > 1:
            # Calculate cohesion: average confidence of internal edges
            internal_edges = [
                conn for conn in neural_map.connections if conn.source in cluster and conn.target in cluster
            ]
            avg_conf = sum(c.confidence for c in internal_edges) / max(len(internal_edges), 1)

            lines.append(f"**Cluster {i}:** {len(cluster)} concepts (cohesion: {avg_conf:.0%})")
            for concept_id in cluster[:5]:
                if concept_id in neural_map.concepts:
                    c = neural_map.concepts[concept_id]
                    lines.append(f"  - {c.name} ({c.type})")
            if len(cluster) > 5:
                lines.append(f"  ... and {len(cluster) - 5} more")
            lines.append("")

    lines.extend(["### Concept Types", ""])
    types = defaultdict(int)
    for c in neural_map.concepts.values():
        types[c.type] += 1
    for t, count in sorted(types.items(), key=lambda x: -x[1]):
        lines.append(f"- **{t}:** {count}")

    return "\n".join(lines)


def _find_connections(ctx: ToolContext, concept_a: str, concept_b: str) -> str:
    """Find connections between two concepts."""
    neural_map = _build_unified_map(ctx)

    if concept_a not in neural_map.concepts:
        return f"⚠️ Concept not found: {concept_a}"
    if concept_b not in neural_map.concepts:
        return f"⚠️ Concept not found: {concept_b}"

    path = neural_map.find_path(concept_a, concept_b)
    related_a = neural_map.find_related(concept_a, depth=1)
    related_b = neural_map.find_related(concept_b, depth=1)

    lines = [
        f"## Connection Analysis: {concept_a} ↔ {concept_b}",
        "",
    ]

    if path:
        lines.append("### Path Found")
        for i, node in enumerate(path):
            if node in neural_map.concepts:
                c = neural_map.concepts[node]
                prefix = " → ".join([""] * i) if i > 0 else ""
                lines.append(f"{'  ' * i}→ **{c.name}** ({c.type})")
    else:
        lines.append("### No Direct Path")
        lines.append("These concepts are not currently connected.")

    lines.extend(["", "### Directly Related to Each", ""])
    lines.append(f"**{concept_a} connects to:**")
    for c in related_a[:5]:
        lines.append(f"  - {c.name} ({c.type})")

    lines.append(f"\n**{concept_b} connects to:**")
    for c in related_b[:5]:
        lines.append(f"  - {c.name} ({c.type})")

    return "\n".join(lines)


def _explore_concept(ctx: ToolContext, concept: str, depth: int = 2) -> str:
    """Explore a concept and its connections."""
    neural_map = _build_unified_map(ctx)

    search_id = None
    for cid, c in neural_map.concepts.items():
        if concept.lower() in cid.lower() or concept.lower() in c.name.lower():
            search_id = cid
            break

    if not search_id:
        return f"⚠️ Concept not found: {concept}"

    concept_obj = neural_map.concepts[search_id]
    related = neural_map.find_related(search_id, depth=depth)

    lines = [
        f"## Concept: {concept_obj.name}",
        "",
        f"**Type:** {concept_obj.type}",
        f"**Path:** {concept_obj.path}",
        f"**Tags:** {', '.join(concept_obj.tags) if concept_obj.tags else 'none'}",
        "",
        f"**Related Concepts:** ({len(related)})",
        "",
    ]

    for c in related[:15]:
        conns = [conn for conn in neural_map.connections if conn.source == search_id and conn.target == c.id]
        conn_type = conns[0].type if conns else "related"
        lines.append(f"- **{c.name}** ({c.type}) - via {conn_type}")

    return "\n".join(lines)


def _create_connection(ctx: ToolContext, from_concept: str, to_concept: str, connection_type: str = "related") -> str:
    """Create a new connection between concepts by adding wikilinks to repo vault (git-tracked)."""
    vault_dir = pathlib.Path(ctx.repo_path("vault"))

    lines = [
        f"## Creating Connection",
        "",
        f"From: {from_concept}",
        f"To: {to_concept}",
        f"Type: {connection_type}",
        "",
    ]

    created = False
    wikilink = f"[[{to_concept}]]"

    if not vault_dir.exists():
        lines.append("❌ Vault directory does not exist")
        return "\n".join(lines)

    for md_file in vault_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        if from_concept.lower() in content.lower() and md_file.stem.lower() == from_concept.lower().replace(" ", "_"):
            if wikilink not in content:
                content = content.rstrip() + f"\n\nRelated: {wikilink}\n"
                md_file.write_text(content, encoding="utf-8")
                lines.append(f"✅ Added link to {md_file.name}")
                created = True
            else:
                lines.append(f"ℹ️ Link already exists in {md_file.name}")

    if not created:
        for md_file in vault_dir.rglob("*.md"):
            if to_concept.lower() in md_file.name.lower():
                try:
                    content = md_file.read_text(encoding="utf-8")
                    backlink = f"[[{from_concept}]]"
                    if backlink not in content:
                        content = content.rstrip() + f"\n\nRelated: {backlink}\n"
                        md_file.write_text(content, encoding="utf-8")
                        lines.append(f"✅ Added link to {md_file.name}")
                        created = True
                except Exception:
                    log.debug("Unexpected error", exc_info=True)

    if not created:
        repo_vault_dir = pathlib.Path(ctx.repo_path("vault/concepts"))
        if not repo_vault_dir.exists():
            repo_vault_dir.mkdir(parents=True, exist_ok=True)
        vault_create_path = repo_vault_dir / f"{from_concept.lower().replace(' ', '_')}.md"
        try:
            vault_create_path.write_text(
                f"# {from_concept}\n\nRelated: [[{to_concept}]]\n",
                encoding="utf-8",
            )
            lines.append(f"✅ Created new note: {vault_create_path.name} (in repo vault)")
            created = True
        except Exception as e:
            lines.append(f"❌ Failed to create: {e}")

    return "\n".join(lines)


def _query_knowledge(ctx: ToolContext, query: str, max_results: int = 10) -> str:
    """Query across all knowledge structures. Searches repo code and repo vault."""
    repo_dir = pathlib.Path(ctx.repo_dir)
    repo_vault_dir = pathlib.Path(ctx.repo_path("vault"))
    knowledge_dir = ctx.drive_path("memory/knowledge")

    results = []

    search_terms = [t.strip().lower() for t in query.split() if len(t) > 2]

    for search_dir, pattern in [
        (repo_dir, "*.py"),
        (repo_vault_dir, "*.md"),
        (knowledge_dir, "*.md"),
    ]:
        if not search_dir.exists():
            continue

        for md_file in search_dir.rglob(pattern):
            if "__pycache__" in str(md_file) or ".git" in str(md_file):
                continue

            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            score = 0
            for term in search_terms:
                if term in content.lower():
                    score += content.lower().count(term)

            if score > 0:
                rel_path = md_file.relative_to(repo_dir) if md_file.is_relative_to(repo_dir) else md_file
                results.append((score, str(rel_path), content[:200]))

    results.sort(reverse=True, key=lambda x: x[0])

    lines = [f"## Knowledge Query: {query}", "", f"**Found:** {len(results)} matches", ""]

    for score, path, preview in results[:max_results]:
        lines.append(f"- **{path}** (relevance: {score})")
        clean_preview = re.sub(r"[^\S\n]+", " ", preview).strip()[:150]
        lines.append(f"  _{clean_preview}..._")
        lines.append("")

    return "\n".join(lines)


def _validate_connection(ctx: ToolContext, source: str, target: str) -> str:
    """Verify a connection exists between two concepts."""
    neural_map = _build_unified_map(ctx)

    source_lower = source.lower().replace(" ", "_")
    target_lower = target.lower().replace(" ", "_")

    source_id = _find_concept_id(neural_map, source_lower)
    target_id = _find_concept_id(neural_map, target_lower)

    if not source_id:
        return f"❌ Source '{source}' not found in knowledge graph"
    if not target_id:
        return f"❌ Target '{target}' not found in knowledge graph"

    connection = None
    for conn in neural_map.connections:
        if (conn.source == source_id and conn.target == target_id) or (
            conn.source == target_id and conn.target == source_id
        ):
            connection = conn
            break

    if connection:
        return f"✅ Connection verified: {source} → {target}\n**Type:** {connection.type}\n**Strength:** {connection.strength:.2f}"
    else:
        return f"❌ No connection found between '{source}' and '{target}'"


def _find_concept_id(neural_map: NeuralMap, name: str) -> Optional[str]:
    """Find concept ID by name."""
    name_lower = name.lower()
    for concept_id, concept in neural_map.concepts.items():
        if name_lower in concept_id.lower() or name_lower in concept.name.lower():
            return concept_id
    return None


def _find_gaps(ctx: ToolContext) -> str:
    """Find gaps in the knowledge graph."""
    from collections import defaultdict

    neural_map = _build_unified_map(ctx)
    lines = ["## Knowledge Graph Gaps", ""]

    orphan_concepts = []
    for concept_id, concept in neural_map.concepts.items():
        if not neural_map._adjacency.get(concept_id):
            orphan_concepts.append(concept)

    if orphan_concepts:
        lines.append(f"### Orphaned Concepts ({len(orphan_concepts)})")
        lines.append("These have no connections:")
        for c in orphan_concepts[:10]:
            lines.append(f"- {c.name}")
        lines.append("")

    orphan_tools = []
    for concept_id, concept in neural_map.concepts.items():
        if concept.type == "tool" and not neural_map._adjacency.get(concept_id):
            orphan_tools.append(concept)

    if orphan_tools:
        lines.append(f"### Orphaned Tools ({len(orphan_tools)})")
        lines.append("Tools without documentation links:")
        for t in orphan_tools[:10]:
            lines.append(f"- {t.name}")
        lines.append("")

    principles_without_impl = []
    principle_ids = [c for c in neural_map.concepts.keys() if "principle" in c.lower()]
    for p_id in principle_ids:
        if p_id not in neural_map._adjacency or not neural_map._adjacency.get(p_id):
            principles_without_impl.append(neural_map.concepts[p_id])

    if principles_without_impl:
        lines.append(f"### Principles Without Implementation Links ({len(principles_without_impl)})")
        for p in principles_without_impl:
            lines.append(f"- {p.name}")

    orphaned_concepts = [
        c for c in neural_map.concepts.values() if c.type == "concept" and not neural_map._adjacency.get(c.id)
    ]
    if orphaned_concepts:
        lines.append(f"### Unlinked Concepts ({len(orphaned_concepts)})")
        for c in orphaned_concepts[:5]:
            lines.append(f"- {c.name}")

    if not orphan_concepts and not orphan_tools and not principles_without_impl and not orphaned_concepts:
        lines.append("✅ No significant gaps found - knowledge graph is well-connected!")

    return "\n".join(lines)


def _generate_insight(ctx: ToolContext, focus_area: str = "all") -> str:
    """Analyze knowledge graph and generate insights."""
    neural_map = _build_unified_map(ctx)
    lines = ["## Knowledge Graph Insights", ""]

    total_concepts = len(neural_map.concepts)
    total_connections = len(neural_map.connections)
    lines.append(f"**Stats:** {total_concepts} concepts, {total_connections} connections")

    avg_connections = 0.0
    if total_connections > 0:
        avg_connections = sum(len(v) for v in neural_map._adjacency.values()) / total_concepts
        lines.append(f"**Avg connections per concept:** {avg_connections:.2f}")

    hubs = []
    for concept_id, connections in neural_map._adjacency.items():
        if len(connections) >= 3:
            concept = neural_map.concepts.get(concept_id)
            if concept:
                hubs.append((concept.name, len(connections)))

    if hubs:
        lines.append("")
        lines.append("### Hub Concepts (most connected)")
        for name, count in sorted(hubs, key=lambda x: -x[1])[:5]:
            lines.append(f"- {name}: {count} connections")

    if focus_area in ("all", "principles"):
        principles = [c for c in neural_map.concepts.values() if "principle" in c.id.lower()]
        if principles:
            lines.append("")
            lines.append("### Principles Analysis")
            for p in principles:
                conn_count = len(neural_map._adjacency.get(p.id, []))
                lines.append(f"- {p.name}: {conn_count} connections")

    if focus_area in ("all", "architecture"):
        arch_related = [
            c for c in neural_map.concepts.values() if "architecture" in c.id.lower() or "loop" in c.id.lower()
        ]
        if arch_related:
            lines.append("")
            lines.append("### Architecture Components")
            for a in arch_related:
                conn_count = len(neural_map._adjacency.get(a.id, []))
                lines.append(f"- {a.name}: {conn_count} connections")

    if focus_area in ("all", "self-reflection"):
        reflection_related = [
            c
            for c in neural_map.concepts.values()
            if any(x in c.id.lower() for x in ["audit", "deep_dive", "analysis", "neural"])
        ]
        if reflection_related:
            lines.append("")
            lines.append("### Self-Reflection Insights")
            for r in reflection_related:
                conn_count = len(neural_map._adjacency.get(r.id, []))
                lines.append(f"- {r.name}: {conn_count} connections")

    lines.append("")
    lines.append("### Recommendations")
    if avg_connections < 1:
        lines.append("- Consider running weave_connection to create more links")
    orphan_count = sum(1 for c in neural_map.concepts.values() if not neural_map._adjacency.get(c.id))
    if orphan_count > 5:
        lines.append(f"- {orphan_count} concepts are orphaned - add wikilinks to connect them")
    if not hubs:
        lines.append("- No hub concepts found - system may lack central architecture")

    return "\n".join(lines)


def _codebase_impact(ctx: ToolContext, target: str, direction: str = "upstream", max_depth: int = 3) -> str:
    """Blast radius analysis - depth-grouped impact with confidence scoring."""
    from ouroboros.codebase_graph import CodebaseGraph, scan_repo

    graph = scan_repo(repo_dir=ctx.repo_dir)

    # Find the target node
    target_id = None
    for node_id, node in graph.nodes.items():
        if target.lower() in node_id.lower() or target.lower() in node.name.lower():
            target_id = node_id
            break

    if not target_id:
        # Search by file path too
        for node_id, node in graph.nodes.items():
            if target.lower() in node.file_path.lower():
                target_id = node_id
                break

    if not target_id:
        return f"⚠️ Target not found in codebase graph: {target}"

    from ouroboros.codebase_graph import analyze_impact

    result = analyze_impact(graph, target_id, max_depth=max_depth, direction=direction)

    t = result["target"]
    lines = [
        f"## Impact Analysis: {t['name']} ({direction})",
        "",
        f"**Target:** `{t['name']}` ({t['type']})",
        f"**File:** {t['file']}:{t['line']}",
        f"**Risk Level:** {result['risk_level'].upper()}",
        f"**Total Affected:** {result['total_affected']} symbols",
        "",
    ]

    depth_labels = result["depth_labels"]
    for depth in sorted(result["depth_groups"].keys()):
        details = result["depth_groups"][depth]
        label = depth_labels.get(depth, f"Depth {depth}")
        lines.append(f"### Depth {depth}: {label} ({len(details)} symbols)")
        lines.append("")
        for d in details[:15]:
            conf_str = f" (confidence: {d['confidence']:.0%})" if d["confidence"] < 1 else ""
            loc = f" - {d['file']}:{d['line']}" if d["file"] else ""
            lines.append(f"- `{d['name']}` ({d['type']}){loc}{conf_str}")
        if len(details) > 15:
            lines.append(f"  ... and {len(details) - 15} more")
        lines.append("")

    if result["total_affected"] == 0:
        lines.append("✅ No dependents found - safe to modify.")

    return "\n".join(lines)


def _symbol_context(ctx: ToolContext, name: str) -> str:
    """360-degree view of a symbol: callers, callees, clusters, and connections."""
    from ouroboros.codebase_graph import scan_repo

    # Build graph once, pass to unified map to avoid double scan
    graph = scan_repo(repo_dir=ctx.repo_dir)
    neural_map = _build_unified_map(ctx, graph=graph)

    # Find the target symbol
    target_id = None
    for node_id, node in graph.nodes.items():
        if name.lower() in node_id.lower() or name.lower() in node.name.lower():
            target_id = node_id
            break

    if not target_id:
        # Fall back to neural map search
        for concept_id, concept in neural_map.concepts.items():
            if name.lower() in concept_id.lower() or name.lower() in concept.name.lower():
                return _explore_concept(ctx, name)

    if not target_id:
        return f"⚠️ Symbol not found: {name}"

    node = graph.get_node(target_id)

    # Incoming (who references this)
    incoming_calls = []
    incoming_imports = []
    incoming_inherits = []
    for edge in graph.edges:
        if edge.target == target_id:
            source_node = graph.get_node(edge.source)
            entry = {
                "name": source_node.name if source_node else edge.source,
                "file": source_node.file_path if source_node else "",
                "line": source_node.line_number if source_node else 0,
                "confidence": edge.confidence,
            }
            if edge.relation == "calls":
                incoming_calls.append(entry)
            elif edge.relation == "imports":
                incoming_imports.append(entry)
            elif edge.relation == "inherits":
                incoming_inherits.append(entry)

    # Outgoing (what this references)
    outgoing_calls = []
    outgoing_imports = []
    for edge in graph.edges:
        if edge.source == target_id:
            target_node = graph.get_node(edge.target)
            entry = {
                "name": target_node.name if target_node else edge.target,
                "file": target_node.file_path if target_node else "",
                "line": target_node.line_number if target_node else 0,
                "confidence": edge.confidence,
            }
            if edge.relation == "calls":
                outgoing_calls.append(entry)
            elif edge.relation == "imports":
                outgoing_imports.append(entry)

    # Cluster membership (from neural map)
    clusters = neural_map.get_clusters()
    membership = []
    for i, cluster in enumerate(clusters):
        if target_id in cluster or any(name.lower() in cid.lower() for cid in cluster):
            members = [neural_map.concepts[cid].name for cid in cluster[:5] if cid in neural_map.concepts]
            membership.append({"cluster_id": i, "size": len(cluster), "members": members})

    lines = [
        f"## Symbol Context: {node.name if node else name}",
        "",
    ]

    if node:
        lines.extend(
            [
                f"**Type:** {node.type}",
                f"**File:** {node.file_path}:{node.line_number}",
                f"**Layer:** {node.layer or 'unclassified'}",
                "",
            ]
        )

    if incoming_calls or incoming_imports or incoming_inherits:
        lines.append("### Incoming (who references this)")
        lines.append("")
        if incoming_calls:
            lines.append("**Called by:**")
            for c in sorted(incoming_calls, key=lambda x: -x["confidence"])[:10]:
                conf_str = f" {c['confidence']:.0%}" if c["confidence"] < 1 else ""
                lines.append(f"- `{c['name']}` ({c['file']}:{c['line']}){conf_str}")
        if incoming_imports:
            lines.append("**Imported by:**")
            for c in sorted(incoming_imports, key=lambda x: -x["confidence"])[:10]:
                lines.append(f"- `{c['name']}` ({c['file']})")
        if incoming_inherits:
            lines.append("**Inherited by:**")
            for c in incoming_inherits[:10]:
                lines.append(f"- `{c['name']}` ({c['file']})")
        lines.append("")

    if outgoing_calls or outgoing_imports:
        lines.append("### Outgoing (what this references)")
        lines.append("")
        if outgoing_calls:
            lines.append("**Calls:**")
            for c in sorted(outgoing_calls, key=lambda x: -x["confidence"])[:10]:
                conf_str = f" {c['confidence']:.0%}" if c["confidence"] < 1 else ""
                lines.append(f"- `{c['name']}` ({c['file']}:{c['line']}){conf_str}")
        if outgoing_imports:
            lines.append("**Imports:**")
            for c in outgoing_imports[:10]:
                lines.append(f"- `{c['name']}` ({c['file']})")
        lines.append("")

    if membership:
        lines.append("### Cluster Membership")
        lines.append("")
        for m in membership[:5]:
            lines.append(f"- **Cluster {m['cluster_id']}** ({m['size']} members): {', '.join(m['members'])}")
        lines.append("")

    if not incoming_calls and not incoming_imports and not outgoing_calls:
        lines.append(
            "ℹ️ No strong relationships detected in the AST graph. "
            "This symbol may be loosely connected or defined in a non-Python file."
        )

    return "\n".join(lines)


def get_tools() -> List[ToolEntry]:
    """Get neural mapping tools."""
    return [
        ToolEntry(
            name="neural_map",
            schema={
                "name": "neural_map",
                "description": (
                    "Build a neural map of Jo's knowledge graph. "
                    "Shows all concepts, connections, and clusters. "
                    "Use to understand how different parts of the system relate."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "depth": {
                            "type": "integer",
                            "description": "Depth of connections to explore (default: 2)",
                            "default": 2,
                        },
                    },
                },
            },
            handler=_neural_map,
            timeout_sec=30,
        ),
        ToolEntry(
            name="find_connections",
            schema={
                "name": "find_connections",
                "description": (
                    "Find connections between two concepts, files, or ideas. "
                    "Shows the path between them and what's related to each."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept_a": {
                            "type": "string",
                            "description": "First concept or file name",
                        },
                        "concept_b": {
                            "type": "string",
                            "description": "Second concept or file name",
                        },
                    },
                    "required": ["concept_a", "concept_b"],
                },
            },
            handler=_find_connections,
            timeout_sec=20,
        ),
        ToolEntry(
            name="explore_concept",
            schema={
                "name": "explore_concept",
                "description": ("Explore a concept and all its connections. Shows what it's related to and how."),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "concept": {
                            "type": "string",
                            "description": "Concept, file, or tool name to explore",
                        },
                        "depth": {
                            "type": "integer",
                            "description": "Connection depth (default: 2)",
                            "default": 2,
                        },
                    },
                    "required": ["concept"],
                },
            },
            handler=_explore_concept,
            timeout_sec=20,
        ),
        ToolEntry(
            name="create_connection",
            schema={
                "name": "create_connection",
                "description": (
                    "Create a new connection between concepts by adding wikilinks. Links two ideas/files in the vault."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_concept": {
                            "type": "string",
                            "description": "Source concept or note name",
                        },
                        "to_concept": {
                            "type": "string",
                            "description": "Target concept or note name",
                        },
                        "connection_type": {
                            "type": "string",
                            "description": "Type of connection (default: related)",
                            "default": "related",
                        },
                    },
                    "required": ["from_concept", "to_concept"],
                },
            },
            handler=_create_connection,
            timeout_sec=15,
        ),
        ToolEntry(
            name="validate_connection",
            schema={
                "name": "validate_connection",
                "description": (
                    "Verify a connection exists between two concepts. Returns evidence for the connection "
                    "and checks if it's still valid. Helps reduce hallucinations by confirming knowledge links."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string", "description": "Source concept or file"},
                        "target": {"type": "string", "description": "Target concept or file"},
                    },
                    "required": ["source", "target"],
                },
            },
            handler=_validate_connection,
            timeout_sec=15,
        ),
        ToolEntry(
            name="find_gaps",
            schema={
                "name": "find_gaps",
                "description": (
                    "Find gaps in the knowledge graph where connections should exist but don't. "
                    "Identifies orphaned concepts, missing links between related ideas, and unreferenced tools. "
                    "Use to discover what needs linking."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_find_gaps,
            timeout_sec=30,
        ),
        ToolEntry(
            name="generate_insight",
            schema={
                "name": "generate_insight",
                "description": (
                    "Analyze the knowledge graph to generate new insights. Reviews connections, identifies patterns, "
                    "and proposes new understandings. Can help identify gaps and suggest areas for exploration. "
                    "Reduces hallucinations by grounding insights in actual connections."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "focus_area": {
                            "type": "string",
                            "description": "Area to focus on: architecture, tools, principles, self-reflection (default: all)",
                            "default": "all",
                        },
                    },
                },
            },
            handler=_generate_insight,
            timeout_sec=60,
        ),
        ToolEntry(
            name="query_knowledge",
            schema={
                "name": "query_knowledge",
                "description": (
                    "Query across all knowledge structures: codebase, vault, memory. Finds relevant concepts and files."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Search terms or question",
                        },
                        "max_results": {
                            "type": "integer",
                            "description": "Maximum results (default: 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=_query_knowledge,
            timeout_sec=30,
        ),
        ToolEntry(
            name="codebase_impact",
            schema={
                "name": "codebase_impact",
                "description": (
                    "Blast radius analysis - depth-grouped impact with confidence scoring. "
                    "Shows what WILL BREAK (depth 1), LIKELY AFFECTED (depth 2), and "
                    "MAY NEED TESTING (depth 3) if you modify a symbol. "
                    "Run BEFORE editing any function, class, or method."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target": {
                            "type": "string",
                            "description": "Symbol, function, class, or file name to analyze",
                        },
                        "direction": {
                            "type": "string",
                            "description": "'upstream' (who depends on this) or 'downstream' (what this depends on)",
                            "default": "upstream",
                        },
                        "max_depth": {
                            "type": "integer",
                            "description": "Maximum traversal depth (default: 3)",
                            "default": 3,
                        },
                    },
                    "required": ["target"],
                },
            },
            handler=_codebase_impact,
            timeout_sec=30,
        ),
        ToolEntry(
            name="symbol_context",
            schema={
                "name": "symbol_context",
                "description": (
                    "360-degree view of a symbol: callers, callees, imports, cluster membership, "
                    "and confidence scores. Use to understand what a symbol connects to before editing it."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Symbol, function, class, or file name to view",
                        },
                    },
                    "required": ["name"],
                },
            },
            handler=_symbol_context,
            timeout_sec=30,
        ),
        ToolEntry(
            name="discover_knowledge_gaps",
            schema={
                "name": "discover_knowledge_gaps",
                "description": (
                    "Scan all knowledge structures (neural map, ontology, vault, codebase) for gaps. "
                    "Returns prioritized list of what Jo should know but doesn't. "
                    "Use during background consciousness to proactively fill understanding gaps. "
                    "Shows orphaned concepts, disconnected tools, missing ontology links, and unlinked vault notes."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
            handler=_discover_knowledge_gaps,
            timeout_sec=30,
        ),
    ]


def _discover_knowledge_gaps(ctx: ToolContext) -> str:
    """Scan all knowledge structures for gaps."""
    import pathlib
    from ouroboros.knowledge_discovery import KnowledgeDiscovery

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path(".")

    discovery = KnowledgeDiscovery(repo_dir=repo_dir, drive_root=drive_root)
    return discovery.get_discovery_report()
