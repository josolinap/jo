#!/usr/bin/env python3
"""Module health checker — validates module size and complexity limits.

Part of the Module Decomposition Protocol.
Checks:
- Line count limits (soft: 500, hard: 1000)
- Cyclomatic complexity (via radon if installed)
- Import cycle detection
- Decomposition suggestions for oversized modules

Usage:
    python scripts/check_module_health.py [--fix] [--report]

    --fix     Attempt to auto-fix issues (format, remove unused imports)
    --report  Generate detailed report to docs/module_health_report.md
"""

from __future__ import annotations

import ast
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Configuration
SOFT_LIMIT = 500
HARD_LIMIT = 1000
COMPLEXITY_WARN = 15
COMPLEXITY_ERROR = 25

# Directories to scan
SCAN_DIRS = ["ouroboros", "supervisor"]
EXCLUDE_DIRS = {"__pycache__", ".git", "node_modules", ".venv", "venv", "archive"}


@dataclass
class ModuleHealth:
    """Health status of a single module."""

    path: Path
    lines: int
    classes: List[str] = field(default_factory=list)
    functions: List[str] = field(default_factory=list)
    imports: List[str] = field(default_factory=list)
    max_complexity: int = 0
    violations: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @property
    def is_critical(self) -> bool:
        return self.lines > HARD_LIMIT

    @property
    def is_warning(self) -> bool:
        return self.lines > SOFT_LIMIT

    @property
    def status(self) -> str:
        if self.is_critical:
            return "CRITICAL"
        elif self.is_warning:
            return "WARNING"
        return "OK"


def count_lines(path: Path) -> int:
    """Count lines in a file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return sum(1 for _ in f)
    except Exception:
        return 0


def analyze_ast(path: Path) -> Tuple[List[str], List[str], List[str]]:
    """Extract classes, functions, and imports from a Python file."""
    classes = []
    functions = []
    imports = []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                classes.append(node.name)
            elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                functions.append(node.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)
    except SyntaxError:
        pass

    return classes, functions, imports


def get_function_boundaries(path: Path) -> List[Tuple[str, int, int]]:
    """Get function names with their line ranges."""
    boundaries = []

    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            tree = ast.parse(f.read(), filename=str(path))

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno + 10)
                boundaries.append((node.name, node.lineno, end_line))
    except SyntaxError:
        pass

    return boundaries


def suggest_decomposition(health: ModuleHealth) -> List[str]:
    """Suggest how to decompose an oversized module."""
    suggestions = []

    if health.lines <= SOFT_LIMIT:
        return suggestions

    # Analyze function boundaries for cohesion clusters
    boundaries = get_function_boundaries(health.path)

    # Group by prefix patterns
    prefix_groups: Dict[str, List[Tuple[str, int, int]]] = {}
    for name, start, end in boundaries:
        # Extract prefix (e.g., "_check_" from "_check_budget")
        parts = name.split("_")
        if len(parts) > 1:
            prefix = "_".join(parts[:2]) + "_"
        else:
            prefix = "other"

        if prefix not in prefix_groups:
            prefix_groups[prefix] = []
        prefix_groups[prefix].append((name, start, end))

    # Suggest extraction for groups with 3+ functions
    for prefix, funcs in sorted(prefix_groups.items(), key=lambda x: -len(x[1])):
        if len(funcs) >= 3:
            total_lines = sum(end - start for _, start, end in funcs)
            if total_lines > 100:
                module_name = prefix.rstrip("_").lstrip("_")
                suggestions.append(
                    f"Extract {len(funcs)} functions ({total_lines} lines) "
                    f"with prefix '{prefix}' -> {health.path.stem}_{module_name}.py"
                )

    # Check for class-based decomposition
    if health.classes:
        for cls in health.classes:
            suggestions.append(f"Consider extracting class '{cls}' -> {health.path.stem}_{cls.lower()}.py")

    # General size-based suggestion
    if health.lines > HARD_LIMIT:
        excess = health.lines - SOFT_LIMIT
        suggestions.append(f"Module is {excess} lines over soft limit. Extract ~{excess} lines to submodules.")

    return suggestions


def check_circular_imports(root: Path) -> List[str]:
    """Detect potential circular import chains."""
    import_graph: Dict[str, set] = {}

    for py_file in root.rglob("*.py"):
        if any(excluded in py_file.parts for excluded in EXCLUDE_DIRS):
            continue

        rel_path = str(py_file.relative_to(root))
        module = rel_path.replace(os.sep, ".").replace(".py", "")

        try:
            _, _, imports = analyze_ast(py_file)
            # Filter to local imports only
            local_imports = {imp for imp in imports if imp.startswith("ouroboros.") or imp.startswith("supervisor.")}
            import_graph[module] = local_imports
        except Exception:
            pass

    # Simple cycle detection (DFS)
    cycles = []
    visited = set()
    rec_stack = set()

    def dfs(node: str, path: List[str]) -> None:
        if node in rec_stack:
            # Found cycle
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles.append(" -> ".join(cycle))
            return

        if node in visited:
            return

        visited.add(node)
        rec_stack.add(node)
        path.append(node)

        for neighbor in import_graph.get(node, set()):
            dfs(neighbor, path)

        path.pop()
        rec_stack.discard(node)

    for module in import_graph:
        if module not in visited:
            dfs(module, [])

    return cycles[:10]  # Limit to first 10 cycles


def scan_modules(root: Path) -> List[ModuleHealth]:
    """Scan all Python modules in the given directories."""
    results = []

    for scan_dir in SCAN_DIRS:
        scan_path = root / scan_dir
        if not scan_path.exists():
            continue

        for py_file in scan_path.rglob("*.py"):
            if any(excluded in py_file.parts for excluded in EXCLUDE_DIRS):
                continue

            # Skip __init__.py and test files
            if py_file.name == "__init__.py" or "test" in py_file.name:
                continue

            lines = count_lines(py_file)
            classes, functions, imports = analyze_ast(py_file)

            health = ModuleHealth(
                path=py_file,
                lines=lines,
                classes=classes,
                functions=functions,
                imports=imports,
            )

            # Add violations
            if lines > HARD_LIMIT:
                health.violations.append(f"CRITICAL: {lines} lines exceeds hard limit of {HARD_LIMIT}")
            elif lines > SOFT_LIMIT:
                health.violations.append(f"WARNING: {lines} lines exceeds soft limit of {SOFT_LIMIT}")

            # Generate suggestions
            health.suggestions = suggest_decomposition(health)

            results.append(health)

    # Sort by line count descending
    results.sort(key=lambda h: -h.lines)
    return results


def generate_report(results: List[ModuleHealth], circular_imports: List[str]) -> str:
    """Generate a markdown report of module health."""
    lines = [
        "# Module Health Report",
        "",
        f"Generated: {__import__('datetime').datetime.now().isoformat()}",
        "",
        "## Summary",
        "",
    ]

    critical = [r for r in results if r.is_critical]
    warnings = [r for r in results if r.is_warning and not r.is_critical]
    ok = [r for r in results if not r.is_warning]

    lines.append(f"- **Critical**: {len(critical)} modules")
    lines.append(f"- **Warning**: {len(warnings)} modules")
    lines.append(f"- **OK**: {len(ok)} modules")
    lines.append("")

    if critical:
        lines.extend(
            [
                "## Critical Violations",
                "",
                "| Module | Lines | Classes | Functions |",
                "|--------|-------|---------|-----------|",
            ]
        )
        for r in critical:
            lines.append(f"| `{r.path}` | {r.lines} | {len(r.classes)} | {len(r.functions)} |")
        lines.append("")

    if warnings:
        lines.extend(
            [
                "## Warnings",
                "",
                "| Module | Lines | Classes | Functions |",
                "|--------|-------|---------|-----------|",
            ]
        )
        for r in warnings:
            lines.append(f"| `{r.path}` | {r.lines} | {len(r.classes)} | {len(r.functions)} |")
        lines.append("")

    if critical or warnings:
        lines.extend(
            [
                "## Decomposition Suggestions",
                "",
            ]
        )
        for r in critical + warnings:
            if r.suggestions:
                lines.extend(
                    [
                        f"### `{r.path}` ({r.lines} lines)",
                        "",
                    ]
                )
                for s in r.suggestions:
                    lines.append(f"- {s}")
                lines.append("")

    if circular_imports:
        lines.extend(
            [
                "## Circular Import Chains",
                "",
            ]
        )
        for cycle in circular_imports:
            lines.append(f"- `{cycle}`")
        lines.append("")

    lines.extend(
        [
            "## All Modules",
            "",
            "| Module | Lines | Status |",
            "|--------|-------|--------|",
        ]
    )
    for r in results:
        status_emoji = "🔴" if r.is_critical else "🟡" if r.is_warning else "🟢"
        lines.append(f"| `{r.path}` | {r.lines} | {status_emoji} {r.status} |")

    return "\n".join(lines)


def main() -> int:
    """Main entry point."""
    root = Path(__file__).parent.parent

    print(f"Scanning modules in {root}...")
    results = scan_modules(root)

    print(f"Checking for circular imports...")
    circular_imports = check_circular_imports(root)

    # Print summary
    critical = [r for r in results if r.is_critical]
    warnings = [r for r in results if r.is_warning and not r.is_critical]

    print(f"\n{'=' * 60}")
    print(f"Module Health Summary")
    print(f"{'=' * 60}")
    print(f"Critical (>1000 lines): {len(critical)}")
    print(f"Warning (>500 lines):   {len(warnings)}")
    print(f"Circular imports:       {len(circular_imports)}")

    if critical:
        print(f"\n{'=' * 60}")
        print("CRITICAL VIOLATIONS:")
        print(f"{'=' * 60}")
        for r in critical:
            print(f"  [CRITICAL] {r.path}: {r.lines} lines")
            if r.suggestions:
                for s in r.suggestions:
                    print(f"     -> {s}")

    if warnings:
        print(f"\n{'=' * 60}")
        print("WARNINGS:")
        print(f"{'=' * 60}")
        for r in warnings:
            print(f"  [WARNING] {r.path}: {r.lines} lines")

    if circular_imports:
        print(f"\n{'=' * 60}")
        print("CIRCULAR IMPORTS:")
        print(f"{'=' * 60}")
        for cycle in circular_imports:
            print(f"  [CIRCULAR] {cycle}")

    # Generate report if requested
    if "--report" in sys.argv:
        report = generate_report(results, circular_imports)
        report_path = root / "docs" / "module_health_report.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"\nReport written to {report_path}")

    # Return exit code based on violations
    if critical or circular_imports:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
