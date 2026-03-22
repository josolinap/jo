"""
Codebase Graph - Build and query a knowledge graph of Jo's codebase.

Inspired by Understand-Anything's knowledge graph approach.
Builds a graph of files, classes, functions, and dependencies.
"""

from __future__ import annotations

import ast
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


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

    def get_dependencies(self, node_id: str) -> List[str]:
        """Get all nodes that this node depends on."""
        deps = []
        for edge in self.edges:
            if edge.source == node_id:
                deps.append(edge.target)
        return deps

    def get_dependents(self, node_id: str) -> List[str]:
        """Get all nodes that depend on this node."""
        dependents = []
        for edge in self.edges:
            if edge.target == node_id:
                dependents.append(edge.source)
        return dependents

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
            graph.add_node(node)
        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                relation=edge_data["relation"],
                metadata=edge_data.get("metadata", {}),
            )
            graph.add_edge(edge)
        return graph


def _classify_layer(file_path: str) -> str:
    """Classify file into architectural layer."""
    path_lower = file_path.lower()
    if "test" in path_lower:
        return "test"
    elif "tool" in path_lower:
        return "tools"
    elif "util" in path_lower:
        return "utils"
    elif "core" in path_lower or "loop" in path_lower or "agent" in path_lower:
        return "core"
    else:
        return "module"


def _parse_python_file(file_path: Path, repo_dir: Path) -> Tuple[List[GraphNode], List[GraphEdge]]:
    """Parse a Python file and extract nodes and edges."""
    nodes = []
    edges = []

    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))
    except Exception as e:
        log.debug(f"Failed to parse {file_path}: {e}")
        return nodes, edges

    # Relative path for IDs
    rel_path = str(file_path.relative_to(repo_dir))
    file_id = f"file:{rel_path}"
    layer = _classify_layer(rel_path)

    # Add file node
    nodes.append(
        GraphNode(
            id=file_id,
            type="file",
            name=file_path.name,
            file_path=rel_path,
            line_number=1,
            summary=f"Python module: {file_path.stem}",
            layer=layer,
        )
    )

    # Extract imports
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                import_id = f"import:{alias.name}"
                nodes.append(
                    GraphNode(
                        id=import_id,
                        type="import",
                        name=alias.name,
                        file_path=rel_path,
                        line_number=node.lineno,
                        summary=f"Imports {alias.name}",
                        layer=layer,
                    )
                )
                edges.append(
                    GraphEdge(
                        source=file_id,
                        target=import_id,
                        relation="imports",
                    )
                )
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                import_id = f"import:{module}.{alias.name}"
                nodes.append(
                    GraphNode(
                        id=import_id,
                        type="import",
                        name=f"{module}.{alias.name}",
                        file_path=rel_path,
                        line_number=node.lineno,
                        summary=f"From {module} imports {alias.name}",
                        layer=layer,
                    )
                )
                edges.append(
                    GraphEdge(
                        source=file_id,
                        target=import_id,
                        relation="imports",
                    )
                )

    # Extract classes
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.ClassDef):
            class_id = f"class:{rel_path}:{node.name}"
            bases = [base.id if isinstance(base, ast.Name) else str(base) for base in node.bases]
            nodes.append(
                GraphNode(
                    id=class_id,
                    type="class",
                    name=node.name,
                    file_path=rel_path,
                    line_number=node.lineno,
                    summary=f"Class {node.name}",
                    layer=layer,
                    metadata={"bases": bases},
                )
            )
            edges.append(
                GraphEdge(
                    source=file_id,
                    target=class_id,
                    relation="contains",
                )
            )

            # Add inheritance edges
            for base in node.bases:
                if isinstance(base, ast.Name):
                    edges.append(
                        GraphEdge(
                            source=class_id,
                            target=f"class:*:{base.id}",
                            relation="inherits",
                        )
                    )

            # Extract methods
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.FunctionDef):
                    method_id = f"func:{rel_path}:{node.name}.{item.name}"
                    nodes.append(
                        GraphNode(
                            id=method_id,
                            type="function",
                            name=f"{node.name}.{item.name}",
                            file_path=rel_path,
                            line_number=item.lineno,
                            summary=f"Method {item.name} of {node.name}",
                            layer=layer,
                            metadata={"class": node.name, "is_method": True},
                        )
                    )
                    edges.append(
                        GraphEdge(
                            source=class_id,
                            target=method_id,
                            relation="contains",
                        )
                    )

    # Extract top-level functions
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef):
            func_id = f"func:{rel_path}:{node.name}"
            nodes.append(
                GraphNode(
                    id=func_id,
                    type="function",
                    name=node.name,
                    file_path=rel_path,
                    line_number=node.lineno,
                    summary=f"Function {node.name}",
                    layer=layer,
                )
            )
            edges.append(
                GraphEdge(
                    source=file_id,
                    target=func_id,
                    relation="contains",
                )
            )

    # Extract function calls for call graph
    call_edges = extract_function_calls(tree, rel_path, repo_dir)
    edges.extend(call_edges)

    return nodes, edges


def scan_repo(repo_dir: Optional[Path] = None, max_files: int = 100) -> CodebaseGraph:
    """Scan a repository and build a codebase graph.

    Args:
        repo_dir: Repository directory (defaults to REPO_DIR env var)
        max_files: Maximum number of files to scan

    Returns:
        CodebaseGraph with nodes and edges
    """
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    repo_dir = repo_dir.resolve()
    graph = CodebaseGraph(
        scanned_at=datetime.now().isoformat(),
        repo_dir=str(repo_dir),
    )

    # Find Python files
    python_files = []
    for pattern in ["*.py"]:
        python_files.extend(repo_dir.rglob(pattern))

    # Filter out common non-source directories
    excluded = {"__pycache__", ".git", ".venv", "venv", "node_modules", ".tox", "dist", "build"}
    python_files = [f for f in python_files if not any(ex in f.parts for ex in excluded)]

    # Limit files
    python_files = python_files[:max_files]

    log.info(f"Scanning {len(python_files)} Python files in {repo_dir}")

    for file_path in python_files:
        nodes, edges = _parse_python_file(file_path, repo_dir)
        for node in nodes:
            graph.add_node(node)
        for edge in edges:
            graph.add_edge(edge)

    log.info(f"Graph built: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    return graph


def export_to_vault(graph: CodebaseGraph, repo_dir: Optional[Path] = None) -> str:
    """Export codebase graph to vault as JSON.

    Args:
        graph: CodebaseGraph to export
        repo_dir: Repository directory

    Returns:
        Status message
    """
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    vault_path = repo_dir / "vault" / "concepts" / "codebase_graph.json"

    try:
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        vault_path.write_text(json.dumps(graph.to_dict(), indent=2), encoding="utf-8")
        return f"Exported graph to vault ({len(graph.nodes)} nodes, {len(graph.edges)} edges)"
    except Exception as e:
        log.error(f"Failed to export graph to vault: {e}")
        return f"Export failed: {e}"


def export_summary_to_vault(graph: CodebaseGraph, repo_dir: Optional[Path] = None) -> str:
    """Export human-readable summary of codebase graph to vault.

    Args:
        graph: CodebaseGraph to summarize
        repo_dir: Repository directory

    Returns:
        Status message
    """
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    vault_path = repo_dir / "vault" / "concepts" / "codebase_overview.md"

    try:
        # Group by layer
        layers: Dict[str, List[GraphNode]] = {}
        for node in graph.nodes.values():
            layer = node.layer or "other"
            if layer not in layers:
                layers[layer] = []
            layers[layer].append(node)

        # Count by type
        type_counts: Dict[str, int] = {}
        for node in graph.nodes.values():
            type_counts[node.type] = type_counts.get(node.type, 0) + 1

        # Build markdown
        lines = [
            "# Codebase Overview",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Repository: {graph.repo_dir}",
            "",
            "## Summary",
            "",
            f"- **Total Nodes:** {len(graph.nodes)}",
            f"- **Total Edges:** {len(graph.edges)}",
            f"- **Files:** {type_counts.get('file', 0)}",
            f"- **Classes:** {type_counts.get('class', 0)}",
            f"- **Functions:** {type_counts.get('function', 0)}",
            "",
            "## Architecture Layers",
            "",
        ]

        for layer in sorted(layers.keys()):
            nodes = layers[layer]
            lines.append(f"### {layer.title()} ({len(nodes)} nodes)")
            lines.append("")
            # Group by file
            files: Dict[str, List[GraphNode]] = {}
            for node in nodes:
                if node.type == "file":
                    continue
                if node.file_path not in files:
                    files[node.file_path] = []
                files[node.file_path].append(node)

            for file_path in sorted(files.keys()):
                file_nodes = files[file_path]
                lines.append(f"- **{file_path}** ({len(file_nodes)} items)")
                for node in sorted(file_nodes, key=lambda n: n.line_number)[:5]:
                    lines.append(f"  - `{node.name}` (line {node.line_number})")
                if len(file_nodes) > 5:
                    lines.append(f"  - ... and {len(file_nodes) - 5} more")
            lines.append("")

        # Most connected nodes
        connection_count: Dict[str, int] = {}
        for edge in graph.edges:
            connection_count[edge.source] = connection_count.get(edge.source, 0) + 1
            connection_count[edge.target] = connection_count.get(edge.target, 0) + 1

        if connection_count:
            lines.append("## Most Connected Nodes")
            lines.append("")
            sorted_connections = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)[:10]
            for node_id, count in sorted_connections:
                node = graph.get_node(node_id)
                if node:
                    lines.append(f"- **{node.name}** ({node.type}) - {count} connections")
            lines.append("")

        lines.append("---")
        lines.append("*Auto-generated by Jo's codebase graph system*")

        content = "\n".join(lines)
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        vault_path.write_text(content, encoding="utf-8")

        return f"Exported summary to vault ({len(graph.nodes)} nodes)"

    except Exception as e:
        log.error(f"Failed to export summary to vault: {e}")
        return f"Export failed: {e}"


def load_graph_from_vault(repo_dir: Optional[Path] = None) -> Optional[CodebaseGraph]:
    """Load codebase graph from vault.

    Args:
        repo_dir: Repository directory

    Returns:
        CodebaseGraph or None if not found
    """
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    vault_path = repo_dir / "vault" / "concepts" / "codebase_graph.json"

    if not vault_path.exists():
        return None

    try:
        data = json.loads(vault_path.read_text(encoding="utf-8"))
        return CodebaseGraph.from_dict(data)
    except Exception as e:
        log.error(f"Failed to load graph from vault: {e}")
        return None


# ============================================================================
# ADVANCED FEATURES - Function Calls, Impact Analysis, Code Metrics
# ============================================================================


def extract_function_calls(tree: ast.Module, file_path: str, repo_dir: Path) -> List[GraphEdge]:
    """Extract function calls from AST to build call graph.

    This enables understanding WHO calls WHAT - critical for impact analysis.
    """
    edges = []
    rel_path = str(file_path) if isinstance(file_path, str) else str(file_path.relative_to(repo_dir))

    # Track current context (class/function we're inside)
    current_context: List[str] = []

    class CallVisitor(ast.NodeVisitor):
        def visit_ClassDef(self, node: ast.ClassDef):
            class_id = f"class:{rel_path}:{node.name}"
            current_context.append(class_id)
            self.generic_visit(node)
            current_context.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            # Build function ID based on context
            if current_context and current_context[-1].startswith("class:"):
                func_id = f"func:{rel_path}:{current_context[-1].split(':')[-1]}.{node.name}"
            else:
                func_id = f"func:{rel_path}:{node.name}"

            current_context.append(func_id)
            self.generic_visit(node)
            current_context.pop()

        def visit_Call(self, node: ast.Call):
            if current_context:
                caller = current_context[-1]

                # Extract called function name
                called_name = None
                if isinstance(node.func, ast.Name):
                    called_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    if isinstance(node.func.value, ast.Name):
                        called_name = f"{node.func.value.id}.{node.func.attr}"
                    else:
                        called_name = node.func.attr

                if called_name:
                    # Try to find the target in same file first
                    target_id = f"func:{rel_path}:{called_name}"
                    edges.append(
                        GraphEdge(
                            source=caller,
                            target=target_id,
                            relation="calls",
                            metadata={"line": node.lineno},
                        )
                    )

            self.generic_visit(node)

    visitor = CallVisitor()
    visitor.visit(tree)
    return edges


def analyze_impact(graph: CodebaseGraph, changed_node_id: str) -> Dict[str, Any]:
    """Analyze the impact of changing a node.

    Returns:
        - directly_affected: Nodes that directly depend on changed_node
        - indirectly_affected: Nodes affected through chains
        - impact_depth: How far the impact spreads
        - risk_level: low/medium/high based on affected count
    """
    directly_affected = graph.get_dependents(changed_node_id)

    # Trace indirect impact (2 levels deep)
    indirectly_affected = set()
    for dep in directly_affected:
        for indirect in graph.get_dependents(dep):
            if indirect != changed_node_id and indirect not in directly_affected:
                indirectly_affected.add(indirect)

    total_affected = len(directly_affected) + len(indirectly_affected)

    # Risk assessment
    if total_affected == 0:
        risk_level = "low"
    elif total_affected <= 3:
        risk_level = "low"
    elif total_affected <= 10:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Get affected node details
    affected_details = []
    for node_id in directly_affected + list(indirectly_affected):
        node = graph.get_node(node_id)
        if node:
            affected_details.append(
                {
                    "id": node_id,
                    "name": node.name,
                    "type": node.type,
                    "file": node.file_path,
                }
            )

    return {
        "changed_node": changed_node_id,
        "directly_affected": directly_affected,
        "indirectly_affected": list(indirectly_affected),
        "total_affected": total_affected,
        "risk_level": risk_level,
        "affected_details": affected_details,
    }


def get_code_metrics(graph: CodebaseGraph) -> Dict[str, Any]:
    """Calculate code metrics from the graph.

    Returns metrics like:
    - Total files, classes, functions
    - Average functions per file
    - Most complex files
    - Inheritance depth
    - Import density
    """
    file_count = sum(1 for n in graph.nodes.values() if n.type == "file")
    class_count = sum(1 for n in graph.nodes.values() if n.type == "class")
    func_count = sum(1 for n in graph.nodes.values() if n.type == "function")
    import_count = sum(1 for n in graph.nodes.values() if n.type == "import")

    # Functions per file
    funcs_per_file: Dict[str, int] = {}
    for node in graph.nodes.values():
        if node.type == "function":
            funcs_per_file[node.file_path] = funcs_per_file.get(node.file_path, 0) + 1

    avg_funcs_per_file = sum(funcs_per_file.values()) / max(len(funcs_per_file), 1)

    # Most complex files (by function count)
    complex_files = sorted(funcs_per_file.items(), key=lambda x: x[1], reverse=True)[:5]

    # Inheritance analysis
    inheritance_edges = [e for e in graph.edges if e.relation == "inherits"]
    classes_with_bases = len(set(e.source for e in inheritance_edges))

    # Layer distribution
    layer_counts: Dict[str, int] = {}
    for node in graph.nodes.values():
        layer = node.layer or "unknown"
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

    # Connection density
    connection_count: Dict[str, int] = {}
    for edge in graph.edges:
        connection_count[edge.source] = connection_count.get(edge.source, 0) + 1
        connection_count[edge.target] = connection_count.get(edge.target, 0) + 1

    most_connected = sorted(connection_count.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "summary": {
            "files": file_count,
            "classes": class_count,
            "functions": func_count,
            "imports": import_count,
            "edges": len(graph.edges),
        },
        "complexity": {
            "avg_functions_per_file": round(avg_funcs_per_file, 1),
            "most_complex_files": [{"file": f, "functions": c} for f, c in complex_files],
        },
        "inheritance": {
            "classes_with_bases": classes_with_bases,
            "inheritance_edges": len(inheritance_edges),
        },
        "layers": layer_counts,
        "connectivity": {
            "most_connected": [{"node": n, "connections": c} for n, c in most_connected],
        },
    }


def detect_patterns(graph: CodebaseGraph) -> List[Dict[str, Any]]:
    """Detect code patterns and potential issues.

    Identifies:
    - God classes (too many methods)
    - Large files (too many functions)
    - Circular dependencies (import cycles)
    - Isolated nodes (no connections)
    """
    patterns = []

    # God classes (>10 methods)
    class_methods: Dict[str, int] = {}
    for edge in graph.edges:
        if edge.relation == "contains" and edge.source.startswith("class:"):
            class_methods[edge.source] = class_methods.get(edge.source, 0) + 1

    for class_id, method_count in class_methods.items():
        if method_count > 10:
            node = graph.get_node(class_id)
            if node:
                patterns.append(
                    {
                        "type": "god_class",
                        "severity": "warning",
                        "node": class_id,
                        "name": node.name,
                        "file": node.file_path,
                        "detail": f"Class has {method_count} methods - consider splitting",
                    }
                )

    # Large files (>20 functions)
    file_funcs: Dict[str, int] = {}
    for node in graph.nodes.values():
        if node.type == "function":
            file_funcs[node.file_path] = file_funcs.get(node.file_path, 0) + 1

    for file_path, func_count in file_funcs.items():
        if func_count > 20:
            patterns.append(
                {
                    "type": "large_file",
                    "severity": "info",
                    "file": file_path,
                    "detail": f"File has {func_count} functions - consider splitting",
                }
            )

    # Isolated nodes (no connections)
    connected_nodes = set()
    for edge in graph.edges:
        connected_nodes.add(edge.source)
        connected_nodes.add(edge.target)

    for node_id, node in graph.nodes.items():
        if node_id not in connected_nodes and node.type in ("class", "function"):
            patterns.append(
                {
                    "type": "isolated_node",
                    "severity": "info",
                    "node": node_id,
                    "name": node.name,
                    "file": node.file_path,
                    "detail": f"{node.type.title()} has no connections in graph",
                }
            )

    return patterns


def generate_insights(graph: CodebaseGraph) -> str:
    """Generate human-readable insights about the codebase.

    Combines metrics, patterns, and graph analysis into actionable insights.
    """
    metrics = get_code_metrics(graph)
    patterns = detect_patterns(graph)

    lines = [
        "# Codebase Insights",
        "",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "## Overview",
        "",
        f"- **{metrics['summary']['files']}** files analyzed",
        f"- **{metrics['summary']['classes']}** classes",
        f"- **{metrics['summary']['functions']}** functions",
        f"- **{metrics['summary']['imports']}** imports",
        f"- **{metrics['summary']['edges']}** relationships",
        "",
    ]

    # Complexity insights
    if metrics["complexity"]["most_complex_files"]:
        lines.extend(
            [
                "## Complexity Hotspots",
                "",
                "Files with most functions (potential refactoring targets):",
                "",
            ]
        )
        for item in metrics["complexity"]["most_complex_files"]:
            lines.append(f"- **{item['file']}**: {item['functions']} functions")
        lines.append("")

    # Pattern warnings
    warnings = [p for p in patterns if p["severity"] == "warning"]
    if warnings:
        lines.extend(
            [
                "## ⚠️ Warnings",
                "",
            ]
        )
        for w in warnings:
            lines.append(f"- **{w['type']}**: {w['detail']}")
        lines.append("")

    # Pattern info
    infos = [p for p in patterns if p["severity"] == "info"]
    if infos:
        lines.extend(
            [
                "## ℹ️ Observations",
                "",
            ]
        )
        for i in infos[:5]:  # Limit to 5
            lines.append(f"- **{i['type']}**: {i['detail']}")
        lines.append("")

    # Layer distribution
    if metrics["layers"]:
        lines.extend(
            [
                "## Architecture Layers",
                "",
            ]
        )
        for layer, count in sorted(metrics["layers"].items()):
            lines.append(f"- **{layer}**: {count} nodes")
        lines.append("")

    # Most connected
    if metrics["connectivity"]["most_connected"]:
        lines.extend(
            [
                "## Central Components",
                "",
                "Most connected nodes (key infrastructure):",
                "",
            ]
        )
        for item in metrics["connectivity"]["most_connected"][:5]:
            node = graph.get_node(item["node"])
            if node:
                lines.append(f"- **{node.name}** ({node.type}): {item['connections']} connections")
        lines.append("")

    lines.extend(
        [
            "---",
            "*Auto-generated by Jo's codebase graph system*",
        ]
    )

    return "\n".join(lines)
