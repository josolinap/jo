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
import subprocess
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
    confidence: float = 1.0  # 0.0-1.0: AST-resolved=0.9, structural=1.0, heuristic=0.3
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CodebaseGraph:
    """Knowledge graph of a codebase."""

    nodes: Dict[str, GraphNode] = field(default_factory=dict)
    edges: List[GraphEdge] = field(default_factory=list)
    scanned_at: str = ""
    repo_dir: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

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
            graph.add_node(node)
        for edge_data in data.get("edges", []):
            edge = GraphEdge(
                source=edge_data["source"],
                target=edge_data["target"],
                relation=edge_data["relation"],
                confidence=edge_data.get("confidence", 1.0),
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
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            content = file_path.read_text(encoding="latin-1")
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
                        confidence=0.85,
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
                        confidence=0.85,
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
                    confidence=1.0,
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
                            confidence=0.9,
                        )
                    )

            # Extract methods (sync + async)
            for item in ast.iter_child_nodes(node):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
                            confidence=1.0,
                        )
                    )

    # Extract top-level functions (sync + async)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
                    confidence=1.0,
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

    Includes freshness metadata: git SHA, timestamp, node/edge counts.
    This lets Jo detect when the note is stale.

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
        # Get git SHA for freshness tracking
        git_sha = ""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            git_sha = result.stdout.strip()[:12] if result.returncode == 0 else ""
        except Exception:
            pass

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
        freshness_note = f" (git: {git_sha})" if git_sha else ""
        lines = [
            "# Codebase Overview",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}{freshness_note}",
            f"Repository: {graph.repo_dir}",
            "",
            f"> Freshness: This note reflects the codebase at commit `{git_sha}`. "
            f"If HEAD has moved since generation, run `codebase_graph.scan_repo()` to refresh.",
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

        def _visit_func(self, node: Any) -> None:
            if current_context and current_context[-1].startswith("class:"):
                func_id = f"func:{rel_path}:{current_context[-1].split(':')[-1]}.{node.name}"
            else:
                func_id = f"func:{rel_path}:{node.name}"
            current_context.append(func_id)
            self.generic_visit(node)
            current_context.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef):
            self._visit_func(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
            self._visit_func(node)

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
                    # AST-based call detection: high confidence for simple names,
                    # medium for attribute access (receiver type unknown)
                    call_conf = 0.9 if isinstance(node.func, ast.Name) else 0.5
                    edges.append(
                        GraphEdge(
                            source=caller,
                            target=target_id,
                            relation="calls",
                            confidence=call_conf,
                            metadata={"line": node.lineno},
                        )
                    )

            self.generic_visit(node)

    visitor = CallVisitor()
    visitor.visit(tree)
    return edges


def analyze_impact(
    graph: CodebaseGraph,
    changed_node_id: str,
    max_depth: int = 3,
    min_confidence: float = 0.0,
    direction: str = "upstream",
) -> Dict[str, Any]:
    """Analyze the blast radius of changing a node.

    Depth-grouped impact analysis inspired by GitNexus:
    - Depth 1: WILL BREAK - direct dependents, must update
    - Depth 2: LIKELY AFFECTED - indirect dependents, should test
    - Depth 3: MAY NEED TESTING - transitive, test if critical

    Args:
        graph: CodebaseGraph to analyze
        changed_node_id: ID of the node being changed
        max_depth: Maximum traversal depth (default 3)
        min_confidence: Minimum edge confidence to traverse (default 0.0)
        direction: "upstream" (who depends on this) or "downstream" (what does this depend on)

    Returns:
        Dict with depth-grouped results, confidence scores, and risk assessment
    """
    if direction not in ("upstream", "downstream"):
        raise ValueError(f"direction must be 'upstream' or 'downstream', got '{direction}'")

    # BFS with depth tracking and parent mapping (for confidence lookup)
    depth_groups: Dict[int, List[str]] = {}
    parent_map: Dict[str, str] = {}  # child -> parent (the node that discovered it)
    visited = {changed_node_id}
    current_level = {changed_node_id}

    for depth in range(1, max_depth + 1):
        next_level = set()
        for node_id in current_level:
            for edge in graph.edges:
                if edge.confidence < min_confidence:
                    continue
                if direction == "upstream":
                    if edge.target == node_id and edge.source not in visited:
                        next_level.add(edge.source)
                        visited.add(edge.source)
                        parent_map[edge.source] = node_id
                else:
                    if edge.source == node_id and edge.target not in visited:
                        next_level.add(edge.target)
                        visited.add(edge.target)
                        parent_map[edge.target] = node_id

        if next_level:
            depth_groups[depth] = sorted(next_level)
        current_level = next_level

    # Build depth labels
    depth_labels = {
        1: "WILL BREAK",
        2: "LIKELY AFFECTED",
        3: "MAY NEED TESTING",
    }

    # Risk assessment
    total_affected = sum(len(nodes) for nodes in depth_groups.values())
    if total_affected == 0:
        risk_level = "low"
    elif total_affected <= 3:
        risk_level = "low"
    elif total_affected <= 10:
        risk_level = "medium"
    else:
        risk_level = "high"

    # Get details for each affected node
    affected_details: Dict[int, List[Dict[str, Any]]] = {}
    for depth, node_ids in depth_groups.items():
        details = []
        for node_id in node_ids:
            node = graph.get_node(node_id)
            # Get connecting edge confidence (look at edge to parent, not just changed_node)
            edge_conf = 0.0
            parent = parent_map.get(node_id, changed_node_id)
            for edge in graph.edges:
                if edge.confidence < min_confidence:
                    continue
                if direction == "upstream":
                    if edge.source == node_id and edge.target == parent:
                        edge_conf = max(edge_conf, edge.confidence)
                else:
                    if edge.source == parent and edge.target == node_id:
                        edge_conf = max(edge_conf, edge.confidence)

            if node:
                details.append(
                    {
                        "id": node_id,
                        "name": node.name,
                        "type": node.type,
                        "file": node.file_path,
                        "line": node.line_number,
                        "confidence": round(edge_conf, 2),
                    }
                )
            else:
                details.append(
                    {
                        "id": node_id,
                        "name": node_id.split(":")[-1] if ":" in node_id else node_id,
                        "type": "unknown",
                        "file": "",
                        "confidence": round(edge_conf, 2),
                    }
                )
        affected_details[depth] = details

    # Change node info
    changed_node = graph.get_node(changed_node_id)
    target_info = {
        "id": changed_node_id,
        "name": changed_node.name if changed_node else changed_node_id,
        "type": changed_node.type if changed_node else "unknown",
        "file": changed_node.file_path if changed_node else "",
        "line": changed_node.line_number if changed_node else 0,
    }

    return {
        "target": target_info,
        "direction": direction,
        "total_affected": total_affected,
        "risk_level": risk_level,
        "depth_groups": affected_details,
        "depth_labels": depth_labels,
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


# ============================================================================
# ONTOLOGY STRUCTURING - Inspired by TrustGraph's precision retrieval
# ============================================================================


@dataclass
class OntologyDefinition:
    """Defines what a task type requires and produces."""

    task_type: str  # "debug", "review", "evolve", "refactor", "test"
    requires: List[str]  # What's needed: ["error_message", "file_context"]
    produces: List[str]  # What's output: ["fix", "test", "verification"]
    typical_tools: List[str]  # Tools typically used: ["repo_read", "run_tests"]
    relationships: List[str]  # Relationship types used: ["imports", "calls"]
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_type": self.task_type,
            "requires": self.requires,
            "produces": self.produces,
            "typical_tools": self.typical_tools,
            "relationships": self.relationships,
            "description": self.description,
        }


# Task ontology definitions for precision task understanding
TASK_ONTOLOGY: Dict[str, OntologyDefinition] = {
    "debug": OntologyDefinition(
        task_type="debug",
        requires=["error_message", "file_context", "stack_trace"],
        produces=["fix", "test", "verification"],
        typical_tools=["repo_read", "run_shell", "run_tests"],
        relationships=["calls", "imports", "contains"],
        description="Find and fix bugs in code",
    ),
    "review": OntologyDefinition(
        task_type="review",
        requires=["code", "requirements", "context"],
        produces=["feedback", "suggestions", "improvements"],
        typical_tools=["repo_read", "grep", "git_diff"],
        relationships=["imports", "calls", "inherits", "contains"],
        description="Review code for quality and correctness",
    ),
    "evolve": OntologyDefinition(
        task_type="evolve",
        requires=["goal", "current_state", "verification_criteria"],
        produces=["changes", "tests", "verification"],
        typical_tools=["repo_read", "code_edit", "run_tests"],
        relationships=["imports", "calls", "contains"],
        description="Evolve codebase toward a goal",
    ),
    "refactor": OntologyDefinition(
        task_type="refactor",
        requires=["target_code", "refactoring_goal"],
        produces=["refactored_code", "tests", "verification"],
        typical_tools=["repo_read", "code_edit_lines", "run_tests"],
        relationships=["imports", "calls", "contains", "inherits"],
        description="Improve code structure without changing behavior",
    ),
    "test": OntologyDefinition(
        task_type="test",
        requires=["target_code", "test_requirements"],
        produces=["test_code", "test_results", "coverage"],
        typical_tools=["repo_read", "code_edit", "run_tests"],
        relationships=["imports", "calls", "contains"],
        description="Create or improve tests",
    ),
    "implement": OntologyDefinition(
        task_type="implement",
        requires=["specification", "existing_code", "constraints"],
        produces=["new_code", "tests", "documentation"],
        typical_tools=["repo_read", "code_edit", "run_tests"],
        relationships=["imports", "calls", "contains"],
        description="Implement new features",
    ),
    "analyze": OntologyDefinition(
        task_type="analyze",
        requires=["target_code", "analysis_goal"],
        produces=["analysis_report", "insights", "recommendations"],
        typical_tools=["repo_read", "grep", "extraction"],
        relationships=["imports", "calls", "inherits", "contains"],
        description="Analyze code structure and behavior",
    ),
}


@dataclass
class RelationshipStrength:
    """Tracks the strength and usefulness of a relationship."""

    source: str
    target: str
    relation: str
    strength: float = 1.0  # 0.0-1.0
    usage_count: int = 0  # How often this relationship was useful
    last_used: str = ""  # When it was last used
    context: str = ""  # What task context it was useful in

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
            "strength": self.strength,
            "usage_count": self.usage_count,
            "last_used": self.last_used,
            "context": self.context,
        }


class OntologyTracker:
    """Tracks relationship strength and usefulness over time.

    Inspired by TrustGraph's approach to precision retrieval:
    - Tracks which relationships are most useful
    - Strengthens useful relationships
    - Weakens unused relationships
    - Provides insights for task routing
    """

    def __init__(self, storage_path: Optional[Path] = None):
        self._storage_path = storage_path or Path(os.environ.get("REPO_DIR", ".")) / "ontology_tracker.json"
        self._relationships: Dict[str, RelationshipStrength] = {}
        self._load()

    def _load(self) -> None:
        """Load relationship tracking data."""
        if self._storage_path.exists():
            try:
                data = json.loads(self._storage_path.read_text(encoding="utf-8"))
                for key, val in data.items():
                    self._relationships[key] = RelationshipStrength(
                        source=val.get("source", ""),
                        target=val.get("target", ""),
                        relation=val.get("relation", ""),
                        strength=val.get("strength", 1.0),
                        usage_count=val.get("usage_count", 0),
                        last_used=val.get("last_used", ""),
                        context=val.get("context", ""),
                    )
            except Exception as e:
                log.warning(f"Failed to load ontology tracker: {e}")

    def _save(self) -> None:
        """Save relationship tracking data."""
        try:
            self._storage_path.parent.mkdir(parents=True, exist_ok=True)
            data = {k: v.to_dict() for k, v in self._relationships.items()}
            self._storage_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            log.warning(f"Failed to save ontology tracker: {e}")

    def _make_key(self, source: str, target: str, relation: str) -> str:
        """Create a unique key for a relationship."""
        return f"{source}|{target}|{relation}"

    def record_usage(
        self,
        source: str,
        target: str,
        relation: str,
        context: str,
        was_useful: bool = True,
    ) -> None:
        """Record that a relationship was used in a task context."""
        # Validate inputs - don't track empty relationships
        if not source or not target or not relation:
            log.debug(f"Skipping empty relationship: source={source}, target={target}, relation={relation}")
            return

        key = self._make_key(source, target, relation)
        now = datetime.now().isoformat()

        if key not in self._relationships:
            self._relationships[key] = RelationshipStrength(
                source=source,
                target=target,
                relation=relation,
                strength=1.0,
            )

        rel = self._relationships[key]
        rel.usage_count += 1
        rel.last_used = now
        rel.context = context

        # Adjust strength based on usefulness
        if was_useful:
            rel.strength = min(1.0, rel.strength + 0.1)
        else:
            rel.strength = max(0.1, rel.strength - 0.1)

        self._save()

    def get_strength(self, source: str, target: str, relation: str) -> float:
        """Get the strength of a relationship."""
        key = self._make_key(source, target, relation)
        rel = self._relationships.get(key)
        return rel.strength if rel else 1.0

    def get_useful_relationships(
        self,
        task_type: Optional[str] = None,
        min_strength: float = 0.5,
        limit: int = 10,
    ) -> List[RelationshipStrength]:
        """Get most useful relationships, optionally filtered by task type."""
        relationships = list(self._relationships.values())

        # Filter by strength
        relationships = [r for r in relationships if r.strength >= min_strength]

        # Filter by task context if provided
        if task_type:
            relationships = [r for r in relationships if task_type.lower() in r.context.lower()]

        # Sort by strength and usage count
        relationships.sort(key=lambda r: (r.strength, r.usage_count), reverse=True)

        return relationships[:limit]

    def get_insights(self) -> Dict[str, Any]:
        """Get insights about relationship usage patterns."""
        if not self._relationships:
            return {"total_relationships": 0, "insights": []}

        total = len(self._relationships)
        avg_strength = sum(r.strength for r in self._relationships.values()) / total
        most_used = max(self._relationships.values(), key=lambda r: r.usage_count)
        strongest = max(self._relationships.values(), key=lambda r: r.strength)

        # Group by relation type
        by_relation: Dict[str, int] = {}
        for rel in self._relationships.values():
            by_relation[rel.relation] = by_relation.get(rel.relation, 0) + 1

        return {
            "total_relationships": total,
            "average_strength": round(avg_strength, 2),
            "most_used": {
                "source": most_used.source,
                "target": most_used.target,
                "relation": most_used.relation,
                "usage_count": most_used.usage_count,
            },
            "strongest": {
                "source": strongest.source,
                "target": strongest.target,
                "relation": strongest.relation,
                "strength": strongest.strength,
            },
            "by_relation_type": by_relation,
        }


def classify_task_ontology(task: str) -> Optional[OntologyDefinition]:
    """Classify a task into an ontology type based on keywords.

    Returns the matching ontology definition or None.
    """
    task_lower = task.lower()

    # Score each ontology type
    scores: Dict[str, int] = {}
    for task_type, ontology in TASK_ONTOLOGY.items():
        score = 0
        # Check task type name
        if task_type in task_lower:
            score += 10
        # Check description keywords
        for word in ontology.description.lower().split():
            if word in task_lower:
                score += 2
        # Check requires keywords
        for req in ontology.requires:
            if req.replace("_", " ") in task_lower:
                score += 1
        scores[task_type] = score

    # Return highest scoring ontology
    if scores:
        best_type = max(scores.items(), key=lambda x: x[1])
        if best_type[1] > 0:
            return TASK_ONTOLOGY.get(best_type[0])

    return None


def get_ontology_for_task(task: str) -> Dict[str, Any]:
    """Get ontology information for a task.

    Returns task requirements, expected outputs, and relevant relationships.
    """
    ontology = classify_task_ontology(task)

    if ontology:
        return {
            "task_type": ontology.task_type,
            "requires": ontology.requires,
            "produces": ontology.produces,
            "typical_tools": ontology.typical_tools,
            "relationships": ontology.relationships,
            "description": ontology.description,
        }

    # Default ontology for unknown tasks
    return {
        "task_type": "general",
        "requires": ["context", "goal"],
        "produces": ["result", "verification"],
        "typical_tools": ["repo_read", "code_edit", "run_tests"],
        "relationships": ["imports", "calls", "contains"],
        "description": "General-purpose task",
    }


def enhance_graph_with_ontology(
    graph: CodebaseGraph,
    task: str,
    tracker: Optional[OntologyTracker] = None,
) -> CodebaseGraph:
    """Enhance a codebase graph with ontology information.

    Adds task context and relationship strength to graph.
    """
    ontology = get_ontology_for_task(task)

    # Add ontology metadata to graph
    graph.metadata = {
        "task_type": ontology["task_type"],
        "requires": ontology["requires"],
        "produces": ontology["produces"],
        "typical_tools": ontology["typical_tools"],
    }

    # If tracker provided, add relationship strengths
    if tracker:
        for edge in graph.edges:
            edge.metadata["strength"] = tracker.get_strength(edge.source, edge.target, edge.relation)

    return graph
