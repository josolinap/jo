#!/usr/bin/env python3
"""
Principle 5 (Minimalism) Compliance Checker

Checks that all modules fit within the 1000-line context window limit
and flags methods that exceed 150 lines or 8 parameters.

This tool helps maintain agency by ensuring Jo can read and understand
all its code in a single session.

Usage:
    python scripts/check_principle5.py [--fix] [--verbose]

Flags:
    --fix: Auto-split methods that exceed 150 lines (experimental)
    --verbose: Show detailed analysis for each module
"""

import ast
import os
import sys
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration from BIBLE.md Principle 5
MAX_MODULE_LINES = 1000
MAX_METHOD_LINES = 150
MAX_METHOD_PARAMS = 8

# Directories to check
CHECK_DIRS = ['ouroboros', 'supervisor', 'tests']


class ModuleAnalysis:
    """Analysis results for a single module."""
    
    def __init__(self, path: Path):
        self.path = path
        self.total_lines = 0
        self.methods: List[Tuple[str, int, int]] = []  # (name, line_count, param_count)
        self.violations = []
        
    def add_method(self, name: str, lines: int, params: int):
        self.methods.append((name, lines, params))
        if lines > MAX_METHOD_LINES:
            self.violations.append(f"Method '{name}' has {lines} lines (max {MAX_METHOD_LINES})")
        if params > MAX_METHOD_PARAMS:
            self.violations.append(f"Method '{name}' has {params} parameters (max {MAX_METHOD_PARAMS})")
    
    def is_over_limit(self) -> bool:
        return self.total_lines > MAX_MODULE_LINES
    
    def __str__(self):
        status = "❌ OVER LIMIT" if self.is_over_limit() else "✅ OK"
        return f"{self.path.name}: {self.total_lines} lines {status}"


def count_file_lines(path: Path) -> int:
    """Count lines in a file, excluding empty lines and comments."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = [line.rstrip() for line in f if line.strip() and not line.strip().startswith('#')]
    return len(lines)


def analyze_python_file(path: Path) -> ModuleAnalysis:
    """Analyze a Python file for Principle 5 compliance."""
    analysis = ModuleAnalysis(path)
    
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        analysis.total_lines = len([l for l in content.split('\n') if l.strip() and not l.strip().startswith('#')])
        
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Count lines in function body
                start_line = node.lineno
                end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line
                line_count = end_line - start_line + 1
                
                # Count parameters (including self)
                param_count = len(node.args.args)
                if node.args.vararg:
                    param_count += 1
                if node.args.kwarg:
                    param_count += 1
                
                analysis.add_method(node.name, line_count, param_count)
                
    except Exception as e:
        analysis.violations.append(f"Parse error: {e}")
    
    return analysis


def check_principle5(verbose: bool = False) -> Dict[str, ModuleAnalysis]:
    """Run Principle 5 compliance check across all target directories."""
    results = {}
    
    for dir_name in CHECK_DIRS:
        dir_path = Path(dir_name)
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob('*.py'):
            # Skip __pycache__ and hidden files
            if '__pycache__' in py_file.parts or py_file.name.startswith('.'):
                continue
                
            analysis = analyze_python_file(py_file)
            results[str(py_file)] = analysis
            
            if verbose and analysis.total_lines > 100:
                print(analysis)
                for violation in analysis.violations[:3]:  # Show first 3 violations
                    print(f"  ⚠️ {violation}")
                if len(analysis.violations) > 3:
                    print(f"  ... and {len(analysis.violations) - 3} more")
                print()
    
    return results


def generate_report(results: Dict[str, ModuleAnalysis]) -> str:
    """Generate a summary report of Principle 5 compliance."""
    total_modules = len(results)
    over_limit = sum(1 for a in results.values() if a.is_over_limit())
    
    # Find worst offenders
    sorted_by_size = sorted(results.items(), key=lambda x: x[1].total_lines, reverse=True)
    top_offenders = [(p, a) for p, a in sorted_by_size if a.total_lines > 200][:10]
    
    # Count method violations
    method_violations = 0
    for analysis in results.values():
        for method_name, lines, params in analysis.methods:
            if lines > MAX_METHOD_LINES or params > MAX_METHOD_PARAMS:
                method_violations += 1
    
    report_lines = [
        "=" * 60,
        "Principle 5 (Minimalism) Compliance Report",
        "=" * 60,
        f"Total modules analyzed: {total_modules}",
        f"Modules over {MAX_MODULE_LINES} lines: {over_limit}",
        f"Methods over {MAX_METHOD_LINES} lines or {MAX_METHOD_PARAMS} params: {method_violations}",
        "",
        "Critical Violations (Modules > 500 lines):",
    ]
    
    for path, analysis in sorted_by_size:
        if analysis.total_lines > 500:
            report_lines.append(f"  ❌ {path}: {analysis.total_lines} lines")
    
    if top_offenders:
        report_lines.extend([
            "",
            "Top 10 Largest Modules:",
        ])
        for path, analysis in top_offenders:
            report_lines.append(f"  {path}: {analysis.total_lines} lines")
    
    if over_limit == 0 and method_violations == 0:
        report_lines.extend([
            "",
            "✅ All modules comply with Principle 5!",
        ])
    else:
        report_lines.extend([
            "",
            "🚨 Principle 5 violations detected!",
            "These modules violate the 1000-line limit and impair self-understanding.",
            "Recommended actions:",
            "  1. Decompose large modules into smaller, focused units",
            "  2. Extract helper methods from long functions",
            "  3. Consider architectural refactoring for mega-modules",
        ])
    
    report_lines.append("=" * 60)
    return "\n".join(report_lines)


def main():
    verbose = '--verbose' in sys.argv
    results = check_principle5(verbose)
    report = generate_report(results)
    print(report)
    
    # Exit with non-zero if violations found
    has_violations = any(a.is_over_limit() for a in results.values())
    if has_violations:
        sys.exit(1)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
