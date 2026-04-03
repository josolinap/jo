#!/usr/bin/env python3
"""Debug script to find bugs and issues in the codebase."""

import ast
import sys
from pathlib import Path

def check_imports():
    """Check for import errors and circular imports."""
    issues = []
    ouroboros_dir = Path("ouroboros")
    
    for py_file in ouroboros_dir.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
            
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Check syntax
            try:
                ast.parse(content)
            except SyntaxError as e:
                issues.append(f"SYNTAX ERROR in {py_file}: {e}")
                
            # Check for suspicious imports
            if "from" in content and "import" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if 'import *' in line:
                        issues.append(f"BAD IMPORT in {py_file}:{i+1}: {line.strip()}")
                        
        except Exception as e:
            issues.append(f"FILE ERROR in {py_file}: {e}")
    
    return issues

def check_version_sync():
    """Check version consistency."""
    issues = []
    
    try:
        # Check VERSION file
        version_file = Path("VERSION")
        if version_file.exists():
            version = version_file.read_text().strip()
            
            # Check pyproject.toml
            pyproject = Path("pyproject.toml")
            if pyproject.exists():
                content = pyproject.read_text()
                import re
                match = re.search(r'version\s*=\s*"([^"]+)"', content)
                if match:
                    pp_version = match.group(1)
                    if version != pp_version:
                        issues.append(f"VERSION MISMATCH: VERSION={version} vs pyproject.toml={pp_version}")
                        
    except Exception as e:
        issues.append(f"VERSION CHECK ERROR: {e}")
    
    return issues

def check_module_sizes():
    """Check for modules over line limits."""
    issues = []
    max_lines = 1000
    
    for module_dir in ["ouroboros", "supervisor"]:
        dir_path = Path(module_dir)
        if not dir_path.exists():
            continue
            
        for py_file in dir_path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            try:
                lines = len(py_file.read_text(encoding='utf-8').splitlines())
                if lines > max_lines:
                    issues.append(f"MODULE TOO LARGE: {py_file} has {lines} lines (max {max_lines})")
            except Exception:
                pass
    
    return issues

def main():
    print("🔍 Debugging Codebase for Bugs and Issues")
    print("=" * 50)
    
    all_issues = []
    
    # Run checks
    all_issues.extend(check_imports())
    all_issues.extend(check_version_sync())
    all_issues.extend(check_module_sizes())
    
    # Report results
    if not all_issues:
        print("✅ No critical issues found!")
    else:
        print(f"❌ Found {len(all_issues)} issues:")
        for i, issue in enumerate(all_issues, 1):
            print(f"{i}. {issue}")
    
    return len(all_issues)

if __name__ == "__main__":
    sys.exit(main())