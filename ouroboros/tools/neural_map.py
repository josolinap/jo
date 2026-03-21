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


class NeuralMap:
    """Knowledge graph representing Jo's understanding."""

    def __init__(self):
        self.concepts: Dict[str, Concept] = {}
        self.connections: List[Connection] = []
        self._adjacency: Dict[str, Set[str]] = defaultdict(set)

    def add_concept(self, concept: Concept) -> None:
        self.concepts[concept.id] = concept

    def add_connection(self, source: str, target: str, conn_type: str, strength: float = 1.0) -> None:
        if source not in self.concepts or target not in self.concepts:
            return

        conn = Connection(source=source, target=target, type=conn_type, strength=strength)
        self.connections.append(conn)
        self._adjacency[source].add(target)

        if conn_type in ("import", "call", "link"):
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
        """Find connected components (concept clusters)."""
        visited = set()
        clusters = []

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


def _scan_codebase(ctx: ToolContext) -> NeuralMap:
    """Scan codebase and build neural map."""
    neural_map = NeuralMap()
    repo_dir = pathlib.Path(ctx.repo_dir)

    python_files = list(repo_dir.rglob("*.py"))
    for py_file in python_files:
        if "venv" in str(py_file) or ".git" in str(py_file) or "__pycache__" in str(py_file):
            continue

        rel_path = py_file.relative_to(repo_dir)
        concept_id = str(rel_path).replace("\\", "/")

        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        concept = Concept(
            id=concept_id,
            name=py_file.stem,
            type="file",
            path=str(rel_path),
            content=content[:500],
        )

        neural_map.add_concept(concept)

        imports = re.findall(r"^import (\w+)|^from (\w+)", content, re.MULTILINE)
        for imp in imports:
            module = imp[0] or imp[1]
            neural_map.add_connection(concept_id, module, "import", strength=0.5)

        classes = re.findall(r"^class (\w+)", content, re.MULTILINE)
        for cls in classes:
            cls_id = f"{concept_id}:{cls}"
            neural_map.add_concept(Concept(id=cls_id, name=cls, type="class", path=str(rel_path)))
            neural_map.add_connection(concept_id, cls_id, "contains", strength=1.0)

        functions = re.findall(r"^def (\w+)", content, re.MULTILINE)
        for fn in functions:
            fn_id = f"{concept_id}:{fn}"
            neural_map.add_concept(Concept(id=fn_id, name=fn, type="function", path=str(rel_path)))
            neural_map.add_connection(concept_id, fn_id, "contains", strength=0.8)

        calls = re.findall(r"(\w+)\(", content)
        for fn_call in set(calls):
            if len(fn_call) > 2 and fn_call[0].islower():
                neural_map.add_connection(concept_id, fn_call, "calls", strength=0.3)

    return neural_map


def _scan_vault(ctx: ToolContext) -> NeuralMap:
    """Scan vault notes and build neural map. Scans both drive vault and repo vault."""
    neural_map = NeuralMap()

    vault_dirs = [
        pathlib.Path(ctx.drive_path("vault")),
        pathlib.Path(ctx.repo_path("vault")),
    ]

    for vault_dir in vault_dirs:
        if not vault_dir.exists():
            continue

        for md_file in vault_dir.rglob("*.md"):
            if md_file.name.startswith("."):
                continue

            rel_path = md_file.relative_to(vault_dir)
            rel_path_str = str(rel_path).replace("\\", "/").replace(".md", "")
            concept_id = f"{vault_dir.name}/{rel_path_str}"

            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            tags = re.findall(r"tags?:\s*\[([^\]]+)\]", content) or []
            tags = [t.strip() for t in " ".join(tags).split(",")]

            concept = Concept(
                id=concept_id,
                name=md_file.stem,
                type="concept",
                path=str(rel_path),
                content=content[:500],
                tags=tags,
            )
            neural_map.add_concept(concept)

            wikilinks = re.findall(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]", content)
            for link in wikilinks:
                link_id = link.strip()
                if not neural_map.concepts.get(link_id):
                    neural_map.add_concept(Concept(id=link_id, name=link, type="concept"))
                neural_map.add_connection(concept_id, link_id, "link", strength=1.0)

            for tag in tags:
                tag_id = f"tag:{tag}"
                if not neural_map.concepts.get(tag_id):
                    neural_map.add_concept(Concept(id=tag_id, name=tag, type="tag"))
                neural_map.add_connection(concept_id, tag_id, "tagged", strength=0.5)

    return neural_map


def _scan_tools(ctx: ToolContext) -> NeuralMap:
    """Scan tool definitions and map dependencies."""
    neural_map = NeuralMap()
    repo_dir = pathlib.Path(ctx.repo_dir)
    tools_dir = repo_dir / "ouroboros" / "tools"

    for py_file in tools_dir.glob("*.py"):
        if py_file.stem.startswith("_"):
            continue

        concept_id = f"tool:{py_file.stem}"
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        tool_name = re.search(r'name[=:]["\']([\w_]+)["\']', content)
        tool_name = tool_name.group(1) if tool_name else py_file.stem

        concept = Concept(
            id=concept_id,
            name=tool_name,
            type="tool",
            path=str(py_file.relative_to(repo_dir)),
            content=content[:300],
        )
        neural_map.add_concept(concept)

        registry_match = re.search(r'"(\w+)"', content)
        if registry_match:
            neural_map.add_connection(concept_id, "tool_registry", "registered", strength=0.5)

    neural_map.add_concept(Concept(id="tool_registry", name="ToolRegistry", type="component"))
    return neural_map


def _build_unified_map(ctx: ToolContext) -> NeuralMap:
    """Build unified neural map from all sources."""
    code_map = _scan_codebase(ctx)
    vault_map = _scan_vault(ctx)
    tool_map = _scan_tools(ctx)

    unified = NeuralMap()

    for concept in (
        list(code_map.concepts.values()) + list(vault_map.concepts.values()) + list(tool_map.concepts.values())
    ):
        unified.add_concept(concept)

    for conn in code_map.connections + vault_map.connections + tool_map.connections:
        unified.connections.append(conn)
        unified._adjacency[conn.source].add(conn.target)

    return unified


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
        "### Clusters (Related Groups)",
        "",
    ]

    clusters = neural_map.get_clusters()
    for i, cluster in enumerate(clusters[:10], 1):
        if len(cluster) > 1:
            lines.append(f"**Cluster {i}:** {len(cluster)} concepts")
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
    """Create a new connection between concepts by adding wikilinks. Searches both drive vault and repo vault."""
    vault_dirs = [
        pathlib.Path(ctx.drive_path("vault")),
        pathlib.Path(ctx.repo_path("vault")),
    ]

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

    for vault_dir in vault_dirs:
        if not vault_dir.exists():
            continue

        for md_file in vault_dir.rglob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8")
            except Exception:
                continue

            if from_concept.lower() in content.lower() and md_file.stem.lower() == from_concept.lower().replace(
                " ", "_"
            ):
                if wikilink not in content:
                    content = content.rstrip() + f"\n\nRelated: {wikilink}\n"
                    md_file.write_text(content, encoding="utf-8")
                    lines.append(f"✅ Added link to {md_file.name} ({vault_dir.name}/)")
                    created = True
                else:
                    lines.append(f"ℹ️ Link already exists in {md_file.name}")

    if not created:
        for vault_dir in vault_dirs:
            if not vault_dir.exists():
                continue
            for md_file in vault_dir.rglob("*.md"):
                if to_concept.lower() in md_file.name.lower():
                    try:
                        content = md_file.read_text(encoding="utf-8")
                        backlink = f"[[{from_concept}]]"
                        if backlink not in content:
                            content = content.rstrip() + f"\n\nRelated: {backlink}\n"
                            md_file.write_text(content, encoding="utf-8")
                            lines.append(f"✅ Added link to {md_file.name} ({vault_dir.name}/)")
                            created = True
                    except Exception:
                        pass

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
    """Query across all knowledge structures. Searches repo, drive vault, and repo vault."""
    repo_dir = pathlib.Path(ctx.repo_dir)
    vault_dir = pathlib.Path(ctx.drive_path("vault"))
    repo_vault_dir = pathlib.Path(ctx.repo_path("vault"))
    knowledge_dir = ctx.drive_path("memory/knowledge")

    results = []

    search_terms = [t.strip().lower() for t in query.split() if len(t) > 2]

    for search_dir, pattern in [
        (repo_dir, "*.py"),
        (vault_dir, "*.md"),
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
    ]
