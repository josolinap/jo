"""AST-based cohesion analysis for module decomposition.

Analyzes code structure to find natural extraction boundaries.
Computes cohesion scores between function groups.

Following Principle 5 (Minimalism): under 300 lines.
"""

from __future__ import annotations

import ast
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


@dataclass
class FunctionCluster:
    """A cluster of related functions."""

    functions: List[str] = field(default_factory=list)
    shared_imports: Set[str] = field(default_factory=set)
    shared_variables: Set[str] = field(default_factory=set)
    call_graph: Dict[str, Set[str]] = field(default_factory=dict)
    cohesion_score: float = 0.0
    coupling_score: float = 0.0


@dataclass
class CohesionAnalyzer:
    """AST-based analysis for finding module extraction boundaries.

    Computes cohesion (how related functions are) and coupling
    (how many external dependencies) to suggest decomposition.

    Usage:
        analyzer = CohesionAnalyzer()
        result = analyzer.analyze_file("ouroboros/loop.py")
        for cluster in result["extractable"]:
            print(f"Extract {cluster.functions} -> cohesion={cluster.cohesion_score}")
    """

    min_cluster_size: int = 2
    min_cohesion: float = 0.6
    max_coupling: float = 0.4

    def analyze_file(self, file_path: str) -> Dict[str, Any]:
        """Analyze a single Python file for cohesion.

        Returns dict with:
        - clusters: list of FunctionCluster
        - extractable: clusters that meet extraction criteria
        - suggestions: human-readable extraction suggestions
        """
        path = Path(file_path)
        if not path.exists():
            return {"error": f"File not found: {file_path}"}

        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as e:
            return {"error": f"Syntax error: {e}"}

        # Extract structure
        functions = self._extract_functions(tree)
        imports = self._extract_imports(tree)
        call_graph = self._build_call_graph(tree, functions)

        # Find clusters based on shared imports and calls
        clusters = self._find_clusters(functions, imports, call_graph)

        # Score each cluster
        for cluster in clusters:
            cluster.cohesion_score = self._compute_cohesion(cluster, call_graph)
            cluster.coupling_score = self._compute_coupling(cluster, functions, call_graph)

        # Filter extractable clusters
        extractable = [
            c
            for c in clusters
            if len(c.functions) >= self.min_cluster_size
            and c.cohesion_score >= self.min_cohesion
            and c.coupling_score <= self.max_coupling
        ]

        # Generate suggestions
        suggestions = []
        for cluster in extractable:
            module_name = self._suggest_module_name(cluster.functions)
            suggestions.append(
                {
                    "functions": cluster.functions,
                    "cohesion": round(cluster.cohesion_score, 2),
                    "coupling": round(cluster.coupling_score, 2),
                    "suggested_module": module_name,
                }
            )

        return {
            "file": str(path),
            "total_functions": len(functions),
            "total_imports": len(imports),
            "clusters": len(clusters),
            "extractable": extractable,
            "suggestions": suggestions,
        }

    def _extract_functions(self, tree: ast.Module) -> Dict[str, Dict[str, Any]]:
        """Extract function definitions and their properties."""
        functions = {}

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = {
                    "name": node.name,
                    "lineno": node.lineno,
                    "end_lineno": getattr(node, "end_lineno", node.lineno + 10),
                    "calls": set(),
                    "imports_used": set(),
                    "variables_used": set(),
                }

                # Extract what this function uses
                for child in ast.walk(node):
                    if isinstance(child, ast.Name):
                        func_info["variables_used"].add(child.id)
                    elif isinstance(child, ast.Call):
                        if isinstance(child.func, ast.Name):
                            func_info["calls"].add(child.func.id)
                        elif isinstance(child.func, ast.Attribute):
                            if isinstance(child.func.value, ast.Name):
                                func_info["calls"].add(f"{child.func.value.id}.{child.func.attr}")

                functions[node.name] = func_info

        return functions

    def _extract_imports(self, tree: ast.Module) -> Set[str]:
        """Extract all imports in the module."""
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
        return imports

    def _build_call_graph(self, tree: ast.Module, functions: Dict[str, Dict[str, Any]]) -> Dict[str, Set[str]]:
        """Build call graph between functions."""
        call_graph = {name: info["calls"] for name, info in functions.items()}

        # Filter to only calls to other functions in the same module
        func_names = set(functions.keys())
        filtered = {}
        for caller, callees in call_graph.items():
            filtered[caller] = {c for c in callees if c in func_names}
        return filtered

    def _find_clusters(
        self,
        functions: Dict[str, Dict[str, Any]],
        imports: Set[str],
        call_graph: Dict[str, Set[str]],
    ) -> List[FunctionCluster]:
        """Find natural clusters of related functions."""
        # Simple prefix-based clustering
        prefix_groups = defaultdict(list)

        for name in functions:
            parts = name.split("_")
            if len(parts) > 1:
                prefix = "_".join(parts[:2]) + "_"
            else:
                prefix = "other"
            prefix_groups[prefix].append(name)

        clusters = []
        for prefix, func_list in prefix_groups.items():
            if len(func_list) < 2:
                continue

            cluster = FunctionCluster(functions=func_list)

            # Find shared imports
            shared_vars = set.intersection(*[functions[f]["variables_used"] for f in func_list]) if func_list else set()
            cluster.shared_variables = shared_vars

            # Build cluster call graph
            for func in func_list:
                cluster.call_graph[func] = call_graph.get(func, set())

            clusters.append(cluster)

        return clusters

    def _compute_cohesion(self, cluster: FunctionCluster, call_graph: Dict[str, Set[str]]) -> float:
        """Compute cohesion score for a cluster (0-1, higher is better)."""
        if len(cluster.functions) < 2:
            return 0.0

        # Count internal calls (within cluster)
        internal_calls = 0
        possible_calls = len(cluster.functions) * (len(cluster.functions) - 1)

        for func in cluster.functions:
            callees = call_graph.get(func, set())
            for callee in callees:
                if callee in cluster.functions:
                    internal_calls += 1

        if possible_calls == 0:
            return 0.0

        return min(1.0, internal_calls / possible_calls + 0.5)

    def _compute_coupling(
        self,
        cluster: FunctionCluster,
        functions: Dict[str, Dict[str, Any]],
        call_graph: Dict[str, Set[str]],
    ) -> float:
        """Compute coupling score for a cluster (0-1, lower is better)."""
        if not cluster.functions:
            return 0.0

        # Count external calls (outside cluster)
        external_calls = 0
        total_calls = 0

        for func in cluster.functions:
            callees = call_graph.get(func, set())
            for callee in callees:
                total_calls += 1
                if callee not in cluster.functions:
                    external_calls += 1

        if total_calls == 0:
            return 0.0

        return external_calls / total_calls

    def _suggest_module_name(self, functions: List[str]) -> str:
        """Suggest a module name based on function prefix."""
        if not functions:
            return "extracted"

        # Use common prefix
        first = functions[0]
        parts = first.split("_")
        if len(parts) > 1:
            # Remove leading underscore and function name
            prefix = "_".join(parts[:-1]).lstrip("_")
            return prefix if prefix else "extracted"
        return "extracted"


def analyze_module_cohesion(file_path: str) -> Dict[str, Any]:
    """Quick cohesion analysis for a module."""
    analyzer = CohesionAnalyzer()
    return analyzer.analyze_file(file_path)
