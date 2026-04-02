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


# Import shared models from codebase_models to avoid circular imports
from ouroboros.codebase_models import GraphNode, GraphEdge, CodebaseGraph

# Re-export for backward compatibility
__all__ = ["GraphNode", "GraphEdge", "CodebaseGraph"]


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
            log.debug("Unexpected error", exc_info=True)

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


# Re-export analysis functions from codebase_analysis for backward compatibility
from ouroboros.codebase_analysis import (  # noqa: E402
    extract_function_calls,
    analyze_impact,
    get_code_metrics,
    detect_patterns,
    generate_insights,
)


# --- Task Ontology Classification ---

_ONTOLOGY_KEYWORDS = {
    "code": ["code", "file", "function", "class", "implement", "edit", "fix", "refactor", "bug", "test", "python"],
    "research": ["research", "search", "find", "investigate", "analyze", "compare", "understand", "explain"],
    "vault": ["vault", "note", "concept", "wiki", "knowledge", "document", "journal", "identity"],
    "git": ["git", "commit", "push", "pull", "branch", "merge", "diff", "status", "log", "tag"],
    "web": ["web", "url", "fetch", "browse", "scrape", "download", "http", "website"],
    "system": ["health", "status", "config", "setting", "monitor", "performance", "drift", "version"],
}

_ONTOLOGY_DEFAULTS = {
    "code": {
        "requires": ["repository access", "tool schemas", "codebase graph"],
        "produces": ["code changes", "commit", "test results"],
        "typical_tools": ["codebase_impact", "symbol_context", "code_edit", "repo_commit_push"],
    },
    "research": {
        "requires": ["web access", "knowledge base"],
        "produces": ["analysis", "summary", "recommendations"],
        "typical_tools": ["web_search", "web_fetch", "query_knowledge", "vault_search"],
    },
    "vault": {
        "requires": ["vault access", "wikilink parser"],
        "produces": ["vault notes", "connections", "knowledge updates"],
        "typical_tools": ["vault_read", "vault_write", "vault_search", "vault_link"],
    },
    "git": {
        "requires": ["git repository", "github API"],
        "produces": ["commits", "branches", "releases"],
        "typical_tools": ["git_status", "git_diff", "repo_commit_push"],
    },
    "web": {
        "requires": ["browser", "HTTP client"],
        "produces": ["scraped content", "screenshots", "analysis"],
        "typical_tools": ["web_search", "web_fetch", "browse_page", "browser_action"],
    },
    "system": {
        "requires": ["health monitor", "drift detector"],
        "produces": ["health reports", "diagnostics"],
        "typical_tools": ["codebase_health", "drift_detector", "system_map"],
    },
    "general": {
        "requires": ["LLM access", "tool schemas"],
        "produces": ["response", "tool results"],
        "typical_tools": ["repo_read", "query_knowledge", "web_search"],
    },
}


def get_ontology_for_task(task_text: str) -> Dict[str, Any]:
    """Classify a task and return ontology information.

    Returns dict with: task_type, requires, produces, typical_tools
    """
    text_lower = task_text.lower()
    scores: Dict[str, int] = {}

    for task_type, keywords in _ONTOLOGY_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[task_type] = score

    if scores:
        task_type = max(scores, key=lambda k: scores[k])
    else:
        task_type = "general"

    defaults = _ONTOLOGY_DEFAULTS.get(task_type, _ONTOLOGY_DEFAULTS["general"])

    return {
        "task_type": task_type,
        "requires": defaults["requires"],
        "produces": defaults["produces"],
        "typical_tools": defaults["typical_tools"],
    }


# Public ontology exports (used by self_check.py and other modules)
TASK_ONTOLOGY: Dict[str, Any] = {
    task_type: {
        "keywords": keywords,
        "requires": _ONTOLOGY_DEFAULTS.get(task_type, {}).get("requires", []),
        "produces": _ONTOLOGY_DEFAULTS.get(task_type, {}).get("produces", []),
        "typical_tools": _ONTOLOGY_DEFAULTS.get(task_type, {}).get("typical_tools", []),
    }
    for task_type, keywords in _ONTOLOGY_KEYWORDS.items()
}


# Re-export from ontology_tracker for backward compatibility
from ouroboros.ontology_tracker import (  # noqa: E402
    OntologyTracker,
    get_ontology_tracker,
    record_task_tool_usage,
    record_task_produces,
    record_tool_co_occurrence,
    record_task_sequence,
    get_task_ontology_profile,
    save_ontology_tracker,
)
