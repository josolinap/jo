"""Codebase analysis functions for impact analysis and metrics.

Extracted from codebase_graph.py (Principle 5: Minimalism).
Provides: impact analysis, code metrics, pattern detection, insights generation.
"""

from __future__ import annotations

import ast
import logging
from datetime import datetime
from typing import Any, Dict, List

from ouroboros.codebase_graph import CodebaseGraph, GraphEdge

log = logging.getLogger(__name__)


def extract_function_calls(tree: ast.Module, file_path: str, repo_dir: Any) -> List[GraphEdge]:
    """Extract function calls from AST to build call graph.

    This enables understanding WHO calls WHAT - critical for impact analysis.
    """
    from pathlib import Path

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
    """
    if direction not in ("upstream", "downstream"):
        raise ValueError(f"direction must be 'upstream' or 'downstream', got '{direction}'")

    # BFS with depth tracking and parent mapping (for confidence lookup)
    depth_groups: Dict[int, List[str]] = {}
    parent_map: Dict[str, str] = {}
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
    """Calculate code metrics from the graph."""
    file_count = sum(1 for n in graph.nodes.values() if n.type == "file")
    class_count = sum(1 for n in graph.nodes.values() if n.type == "class")
    func_count = sum(1 for n in graph.nodes.values() if n.type == "function")
    import_count = sum(1 for n in graph.nodes.values() if n.type == "import")

    funcs_per_file: Dict[str, int] = {}
    for node in graph.nodes.values():
        if node.type == "function":
            funcs_per_file[node.file_path] = funcs_per_file.get(node.file_path, 0) + 1

    avg_funcs_per_file = sum(funcs_per_file.values()) / max(len(funcs_per_file), 1)
    complex_files = sorted(funcs_per_file.items(), key=lambda x: x[1], reverse=True)[:5]

    inheritance_edges = [e for e in graph.edges if e.relation == "inherits"]
    classes_with_bases = len(set(e.source for e in inheritance_edges))

    layer_counts: Dict[str, int] = {}
    for node in graph.nodes.values():
        layer = node.layer or "unknown"
        layer_counts[layer] = layer_counts.get(layer, 0) + 1

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
    """Detect code patterns and potential issues."""
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
    """Generate human-readable insights about the codebase."""
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

    if metrics["complexity"]["most_complex_files"]:
        lines.extend(["## Complexity Hotspots", "", "Files with most functions (potential refactoring targets):", ""])
        for item in metrics["complexity"]["most_complex_files"]:
            lines.append(f"- **{item['file']}**: {item['functions']} functions")
        lines.append("")

    warnings = [p for p in patterns if p["severity"] == "warning"]
    if warnings:
        lines.extend(["## Warnings", ""])
        for w in warnings:
            lines.append(f"- **{w['type']}**: {w['detail']}")
        lines.append("")

    infos = [p for p in patterns if p["severity"] == "info"]
    if infos:
        lines.extend(["## Observations", ""])
        for i in infos[:5]:
            lines.append(f"- **{i['type']}**: {i['detail']}")
        lines.append("")

    if metrics["layers"]:
        lines.extend(["## Architecture Layers", ""])
        for layer, count in sorted(metrics["layers"].items()):
            lines.append(f"- **{layer}**: {count} nodes")
        lines.append("")

    if metrics["connectivity"]["most_connected"]:
        lines.extend(["## Central Components", "", "Most connected nodes (key infrastructure):", ""])
        for item in metrics["connectivity"]["most_connected"][:5]:
            node = graph.get_node(item["node"])
            if node:
                lines.append(f"- **{node.name}** ({node.type}): {item['connections']} connections")
        lines.append("")

    lines.extend(["---", "*Auto-generated by Jo's codebase graph system*"])

    return "\n".join(lines)
