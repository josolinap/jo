#!/usr/bin/env python3
"""Comprehensive system health and performance audit."""
import ast
import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple, Optional

REPO_ROOT = Path(__file__).parent.parent
OUROBOROS_DIR = REPO_ROOT / "ouroboros"
SUPERVISOR_DIR = REPO_ROOT / "supervisor"
LOGS_DIR = REPO_ROOT / "logs"

def count_lines(path: Path) -> int:
    """Count lines in a file."""
    try:
        return len(path.read_text().splitlines())
    except Exception:
        return 0

def find_oversized_functions(dir_path: Path, max_lines: int = 150) -> List[Tuple[str, str, int, int]]:
    """Find functions exceeding max_lines."""
    oversized = []
    for py_file in dir_path.rglob("*.py"):
        try:
            with open(py_file) as f:
                lines = f.readlines()
            tree = ast.parse("".join(lines))
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    func_lines = node.end_lineno - node.lineno + 1
                    if func_lines > max_lines:
                        oversized.append((
                            str(py_file.relative_to(REPO_ROOT)),
                            node.name,
                            node.lineno,
                            func_lines
                        ))
        except Exception:
            continue
    return sorted(oversized, key=lambda x: x[3], reverse=True)

def find_oversized_modules(dir_path: Path, max_lines: int = 1000) -> List[Tuple[str, int]]:
    """Find modules exceeding max_lines."""
    oversized = []
    for py_file in dir_path.rglob("*.py"):
        lines = count_lines(py_file)
        if lines > max_lines:
            oversized.append((
                str(py_file.relative_to(REPO_ROOT)),
                lines
            ))
    return sorted(oversized, key=lambda x: x[1], reverse=True)

def analyze_vault_integrity() -> Dict:
    """Check vault structure and links."""
    vault_dir = REPO_ROOT / "vault"
    if not vault_dir.exists():
        return {"error": "Vault directory not found"}
    
    notes = list(vault_dir.rglob("*.md"))
    total_notes = len(notes)
    
    # Count wikilinks and broken links
    total_wikilinks = 0
    unique_targets = set()
    broken_links = []
    
    for note in notes:
        try:
            content = note.read_text()
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            total_wikilinks += len(links)
            for link in links:
                target = link.split('|')[0].strip()
                unique_targets.add(target)
                # Check if target note exists
                if not (vault_dir / f"{target}.md").exists():
                    broken_links.append((str(note.relative_to(vault_dir)), target))
        except Exception:
            continue
    
    # Calculate orphaned notes (no backlinks)
    orphaned = 0
    for note in notes:
        note_name = note.stem
        found = False
        try:
            content = note.read_text()
            if f"[[{note_name}]]" in content:
                found = True
        except Exception:
            continue
        if not found:
            orphaned += 1
    
    return {
        "total_notes": total_notes,
        "total_wikilinks": total_wikilinks,
        "unique_targets": len(unique_targets),
        "broken_links": len(broken_links),
        "orphaned_notes": orphaned,
        "broken_link_examples": broken_links[:10],
    }

def analyze_tool_performance() -> Dict:
    """Analyze tool execution logs."""
    tools_log = LOGS_DIR / "tools.jsonl"
    if not tools_log.exists():
        return {"error": "tools.jsonl not found"}
    
    entries = []
    total_cost = 0
    total_duration = 0
    tool_counts = defaultdict(int)
    cache_hits = 0
    errors = 0
    
    with open(tools_log) as f:
        for line in f:
            try:
                entry = json.loads(line.strip())
                entries.append(entry)
                tool = entry.get("tool", "unknown")
                tool_counts[tool] += 1
                
                cost = entry.get("cost_usd", 0)
                if cost:
                    total_cost += cost
                
                duration = entry.get("duration_ms")
                if duration:
                    total_duration += duration
                
                if entry.get("cache_hit"):
                    cache_hits += 1
                    
                if "error" in entry or "stderr" in entry:
                    errors += 1
            except json.JSONDecodeError:
                continue
    
    avg_duration = total_duration / len(entries) if entries else 0
    
    # Top 10 most used tools
    top_tools = sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "total_calls": len(entries),
        "total_cost_usd": round(total_cost, 6),
        "avg_duration_ms": round(avg_duration, 2),
        "cache_hit_rate": round(cache_hits / len(entries) * 100, 1) if entries else 0,
        "error_rate": round(errors / len(entries) * 100, 1) if entries else 0,
        "top_tools": top_tools,
    }

def check_test_coverage() -> Dict:
    """Check test file structure and coverage."""
    tests_dir = REPO_ROOT / "tests"
    if not tests_dir.exists():
        return {"error": "tests directory not found"}
    
    test_files = list(tests_dir.glob("test_*.py"))
    test_functions = 0
    
    for test_file in test_files:
        try:
            with open(test_file) as f:
                content = f.read()
                # Count test functions
                test_functions += len(re.findall(r'def test_\w+\(', content))
        except Exception:
            continue
    
    return {
        "test_files": len(test_files),
        "test_functions": test_functions,
        "has_coverage_file": (REPO_ROOT / ".coveragerc").exists() or (REPO_ROOT / "pyproject.toml").exists(),
    }

def analyze_memory_patterns() -> Dict:
    """Check for potential memory leaks in code patterns."""
    issues = []
    
    # Check for common memory leak patterns
    files_to_check = [
        OUROBOROS_DIR / "context.py",
        OUROBOROS_DIR / "memory.py",
        OUROBOROS_DIR / "loop.py",
        SUPERVISOR_DIR / "telegram.py",
    ]
    
    for file_path in files_to_check:
        if not file_path.exists():
            continue
        try:
            with open(file_path) as f:
                content = f.read()
                lines = f.readlines()
                
            # Check for growing lists without bounds
            if ".append(" in content and "pop(0)" not in content and "deque" not in content:
                if file_path.name == "context.py":
                    issues.append(f"{file_path.name}: Potential unbounded list growth (no pop(0) or deque usage)")
            
            # Check for large global/mutable defaults
            if "def __init__" in content:
                init_lines = [l for l in lines if "def __init__" in l]
                for line in init_lines:
                    if "=" in line and "None" not in line:
                        # Might have mutable default
                        issues.append(f"{file_path.name}: Check for mutable default arguments in __init__")
                        
        except Exception:
            continue
    
    return {
        "potential_issues": issues[:10],
        "files_checked": [p.name for p in files_to_check if p.exists()],
    }

def main():
    print("=" * 80)
    print("SYSTEM HEALTH AND PERFORMANCE AUDIT")
    print("=" * 80)
    
    # 1. Module Complexity
    print("\n1. MODULE COMPLEXITY ANALYSIS")
    print("-" * 80)
    oversized_mods = find_oversized_modules(OUROBOROS_DIR, 1000)
    if oversized_mods:
        print(f"⚠️  Modules > 1000 lines: {len(oversized_mods)}")
        for path, lines in oversized_mods[:10]:
            print(f"   {path}: {lines} lines")
    else:
        print("✓ All modules within 1000-line limit")
    
    oversized_supervisor = find_oversized_modules(SUPERVISOR_DIR, 1000)
    if oversized_supervisor:
        print(f"⚠️  Supervisor modules > 1000 lines: {len(oversized_supervisor)}")
        for path, lines in oversized_supervisor[:5]:
            print(f"   {path}: {lines} lines")
    
    # 2. Function Complexity
    print("\n2. FUNCTION COMPLEXITY ANALYSIS")
    print("-" * 80)
    oversized_funcs = find_oversized_functions(OUROBOROS_DIR, 150)
    if oversized_funcs:
        print(f"⚠️  Functions > 150 lines: {len(oversized_funcs)}")
        for path, name, start, lines in oversized_funcs[:10]:
            print(f"   {path}:{name}() - {lines} lines (starting at {start})")
    else:
        print("✓ All functions within 150-line limit")
    
    # 3. Vault Integrity
    print("\n3. VAULT INTEGRITY")
    print("-" * 80)
    vault_stats = analyze_vault_integrity()
    if "error" in vault_stats:
        print(f"✗ {vault_stats['error']}")
    else:
        print(f"Total notes: {vault_stats['total_notes']}")
        print(f"Total wikilinks: {vault_stats['total_wikilinks']}")
        print(f"Unique targets: {vault_stats['unique_targets']}")
        if vault_stats['broken_links'] > 0:
            print(f"✗ Broken links: {vault_stats['broken_links']}")
            for src, target in vault_stats['broken_link_examples']:
                print(f"   {src} -> [[{target}]]")
        else:
            print("✓ No broken links")
        if vault_stats['orphaned_notes'] > 0:
            print(f"⚠️  Orphaned notes (no backlinks): {vault_stats['orphaned_notes']}")
        else:
            print("✓ All notes have backlinks")
    
    # 4. Tool Performance
    print("\n4. TOOL PERFORMANCE METRICS")
    print("-" * 80)
    perf = analyze_tool_performance()
    if "error" in perf:
        print(f"✗ {perf['error']}")
    else:
        print(f"Total tool calls: {perf['total_calls']}")
        print(f"Total cost: ${perf['total_cost_usd']:.6f}")
        print(f"Avg duration: {perf['avg_duration_ms']:.2f}ms")
        print(f"Cache hit rate: {perf['cache_hit_rate']}%")
        print(f"Error rate: {perf['error_rate']}%")
        if perf['error_rate'] > 5:
            print("✗ HIGH ERROR RATE - Investigate tool failures")
        if perf['cache_hit_rate'] < 30:
            print("⚠️  Low cache hit rate - context cache may not be working")
        print("\nTop 10 tools by usage:")
        for tool, count in perf['top_tools']:
            print(f"   {tool}: {count} calls")
    
    # 5. Test Coverage
    print("\n5. TEST COVERAGE")
    print("-" * 80)
    tests = check_test_coverage()
    if "error" in tests:
        print(f"✗ {tests['error']}")
    else:
        print(f"Test files: {tests['test_files']}")
        print(f"Test functions: {tests['test_functions']}")
        if tests['has_coverage_file']:
            print("✓ Coverage configuration exists")
        else:
            print("⚠️  No coverage configuration found")
        if tests['test_functions'] < 50:
            print("⚠️  Low test coverage - consider adding more tests")
        else:
            print("✓ Reasonable test coverage")
    
    # 6. Memory Patterns
    print("\n6. MEMORY LEAK RISK ASSESSMENT")
    print("-" * 80)
    mem = analyze_memory_patterns()
    if mem['potential_issues']:
        print("⚠️  Potential issues detected:")
        for issue in mem['potential_issues']:
            print(f"   • {issue}")
    else:
        print("✓ No obvious memory leak patterns detected")
    print(f"Files checked: {', '.join(mem['files_checked'])}")
    
    print("\n" + "=" * 80)
    print("AUDIT COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    main()