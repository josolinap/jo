#!/usr/bin/env python3
"""
Code Health Monitor — tracks code quality metrics and minimalism violations.
Serves as an automated guardrail for agency by ensuring the codebase remains
understandable and maintainable.

This tool can be run independently without modifying protected files.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Tuple

# Constants
MODULE_SIZE_LIMIT = 1000  # lines (minimalism principle)
FUNCTION_SIZE_LIMIT = 150  # lines
PARAMETER_COUNT_LIMIT = 8  # parameters

REPO_ROOT = Path(__file__).parent


@dataclass
class HealthMetrics:
    """Metrics for code health."""
    modules_over_limit: List[Dict[str, int]]
    functions_over_limit: List[Dict[str, int]]
    total_lines: int
    total_modules: int
    score: float  # 0-100, higher is better

    def to_dict(self) -> Dict:
        return asdict(self)


def find_python_files(base_dir: Path) -> List[Path]:
    """Recursively find all Python files."""
    return list(base_dir.rglob("*.py"))


def analyze_module_size(path: Path) -> Tuple[int, List[ Tuple[int, str, int] ]]:
    """Return (line_count, [(line_start, function_name, line_count), ...])"""
    with open(path) as f:
        lines = f.readlines()

    total = len(lines)
    functions = []
    current_func = None
    start_line = 0
    indent_level = 0

    for i, line in enumerate(lines, 1):
        stripped = line.lstrip()
        if stripped.startswith("def ") or stripped.startswith("async def "):
            if current_func is not None:
                functions.append((start_line, current_func, i - start_line - 1))
            current_func = stripped.split("(")[0].split()[-1]
            start_line = i
            indent_level = len(line) - len(stripped)
        elif stripped and not stripped.startswith("#"):
            current_indent = len(line) - len(stripped)
            if current_func is not None and current_indent <= indent_level:
                functions.append((start_line, current_func, i - start_line - 1))
                current_func = None

    if current_func is not None:
        functions.append((start_line, current_func, total - start_line + 1))

    return total, functions


def count_parameters(func_code: str) -> int:
    """Count parameters in a function signature."""
    import ast
    try:
        tree = ast.parse(func_code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return len(node.args.args)
    except Exception:
        return 0
    return 0


def analyze_parameter_counts(path: Path, functions: List[Tuple[int, str, int]]) -> List[Tuple[int, str, int]]:
    """Extract function code and count parameters for those with many lines."""
    with open(path) as f:
        lines = f.readlines()

    over_limit = []
    for start, name, length in functions:
        if length > 50:  # only check substantial functions
            func_lines = lines[start-1:start-1+length]
            func_code = "".join(func_lines)
            param_count = count_parameters(func_code)
            if param_count > PARAMETER_COUNT_LIMIT:
                over_limit.append((start, name, param_count))

    return over_limit


def check_repo_health() -> HealthMetrics:
    """Perform full health check of Python modules."""
    modules = find_python_files(REPO_ROOT / "ouroboros") + find_python_files(REPO_ROOT / "supervisor")

    total_lines = 0
    total_modules = len(modules)
    modules_over = []
    functions_over = []

    for path in modules:
        if any(part.startswith(".") for part in path.parts):
            continue

        line_count, functions = analyze_module_size(path)
        total_lines += line_count

        if line_count > MODULE_SIZE_LIMIT:
            modules_over.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "lines": line_count,
                "limit": MODULE_SIZE_LIMIT,
            })

        for start, name, length in functions:
            if length > FUNCTION_SIZE_LIMIT:
                functions_over.append({
                    "path": str(path.relative_to(REPO_ROOT)),
                    "function": name,
                    "lines": length,
                    "start_line": start,
                    "limit": FUNCTION_SIZE_LIMIT,
                })

        param_violations = analyze_parameter_counts(path, functions)
        for start, name, count in param_violations:
            functions_over.append({
                "path": str(path.relative_to(REPO_ROOT)),
                "function": name,
                "parameters": count,
                "start_line": start,
                "limit": PARAMETER_COUNT_LIMIT,
                "type": "parameter_count",
            })

    # Calculate health score (simple heuristic)
    score = 100.0
    score -= len(modules_over) * 5
    score -= len(functions_over) * 2
    score = max(0, min(100, score))

    return HealthMetrics(
        modules_over_limit=modules_over,
        functions_over_limit=functions_over,
        total_lines=total_lines,
        total_modules=total_modules,
        score=score,
    )


def main() -> int:
    """CLI entry point."""
    metrics = check_repo_health()

    print(json.dumps(metrics.to_dict(), indent=2))

    # Also print human-readable summary
    print("\n=== Code Health Report ===")
    print(f"Total modules: {metrics.total_modules}")
    print(f"Total lines: {metrics.total_lines}")
    print(f"Health score: {metrics.score:.1f}/100")

    if metrics.modules_over_limit:
        print(f"\n⚠️  Modules exceeding {MODULE_SIZE_LIMIT} lines:")
        for mod in metrics.modules_over_limit:
            print(f"  {mod['path']}: {mod['lines']} lines (+{mod['lines'] - MODULE_SIZE_LIMIT})")

    if metrics.functions_over_limit:
        print(f"\n⚠️  Functions exceeding limits:")
        for func in metrics.functions_over_limit:
            if "parameters" in func:
                print(f"  {func['path']}:{func['function']} - {func['parameters']} params (limit {PARAMETER_COUNT_LIMIT})")
            else:
                print(f"  {func['path']}:{func['function']} - {func['lines']} lines (limit {FUNCTION_SIZE_LIMIT})")

    if metrics.score >= 90:
        print("\n✅ Codebase health is good.")
        return 0
    elif metrics.score >= 70:
        print("\n⚠️  Codebase needs attention.")
        return 1
    else:
        print("\n❌ Codebase health is poor.")
        return 2


if __name__ == "__main__":
    sys.exit(main())
