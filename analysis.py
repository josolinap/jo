#!/usr/bin/env python3
"""
Quick analysis of codebase for evolution cycle
"""
import os
import re
from pathlib import Path

def analyze_codebase():
    """Analyze codebase for quality issues"""
    issues = []
    
    # Check for large files
    py_files = list(Path(".").rglob("*.py"))
    
    for py_file in py_files:
        if "test_" in str(py_file) or "archive" in str(py_file):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                line_count = len(lines)
                
                # Check modules over 1000 lines
                if line_count > 1000:
                    issues.append(f"Large module: {py_file} ({line_count} lines)")
                
                # Check functions over 150 lines
                content = ''.join(lines)
                function_pattern = r'def\s+\w+\([^)]*\):\s*\n((?:[ \t]+.*\n)+)'
                functions = re.finditer(function_pattern, content)
                
                for match in functions:
                    func_lines = match.group(1).count('\n')
                    if func_lines > 150:
                        issues.append(f"Large function in {py_file}: ~{func_lines} lines")
                        
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    return issues

if __name__ == "__main__":
    issues = analyze_codebase()
    print("Code Quality Issues:")
    for issue in issues:
        print(f"  - {issue}")