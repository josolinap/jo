#!/usr/bin/env python3
"""
Jo Pattern Scanner - Analyze architecture for patterns and opportunities
Part of the Jo Pattern Discovery Engine project
"""

import os
import json
from pathlib import Path
from collections import defaultdict, Counter
import re
from typing import Dict, List, Any

class PatternScanner:
    """Scans Jo's codebase for architectural patterns, metrics, and opportunities"""
    
    def __init__(self, repo_root="."):
        self.repo_root = Path(repo_root)
        self.patterns = defaultdict(list)
        self.metrics = {}
        
    def scan(self):
        """Run all scanning analyses"""
        self.scan_module_sizes()
        self.scan_imports()
        self.scan_tool_definitions()
        self.scan_protected_files()
        self.scan_vault_connectivity()
        self.scan_bible_principles()
        self.compute_metrics()
        
    def scan_module_sizes(self):
        """Check minimalism principle compliance"""
        for py_file in self.repo_root.glob("**/*.py"):
            if any(skip in str(py_file) for skip in ["test", "__pycache__", ".pyc"]):
                continue
            try:
                lines = py_file.read_text().count('\n')
                self.patterns['module_sizes'].append({
                    'file': str(py_file.relative_to(self.repo_root)),
                    'lines': lines
                })
            except Exception:
                continue
                
    def scan_imports(self):
        """Build dependency graph"""
        import_pattern = re.compile(r'^(?:from|import)\s+(\S+)', re.MULTILINE)
        for py_file in self.repo_root.glob("**/*.py"):
            if any(skip in str(py_file) for skip in ["test", "__pycache__", ".pyc"]):
                continue
            try:
                content = py_file.read_text()
                imports = import_pattern.findall(content)
                for imp in imports:
                    self.patterns['imports'].append({
                        'from': str(py_file.relative_to(self.repo_root)),
                        'to': imp.split('.')[0],
                        'full': imp
                    })
            except Exception:
                continue
                
    def scan_tool_definitions(self):
        """Catalog all available tools"""
        tools_dir = self.repo_root / "ouroboros" / "tools"
        if tools_dir.exists():
            for module in tools_dir.glob("*.py"):
                if module.name != "__init__.py":
                    content = module.read_text()
                    # Look for get_tools() function
                    if "def get_tools" in content:
                        self.patterns['tool_modules'].append({
                            'module': str(module.relative_to(tools_dir)),
                            'has_get_tools': True
                        })
                        
    def scan_protected_files(self):
        """Analyze protection coverage"""
        protected_file = self.repo_root / ".jo_protected"
        if protected_file.exists():
            protected = protected_file.read_text().splitlines()
            self.patterns['protected_files'] = [
                p for p in protected 
                if p and not p.startswith('#') and p.strip()
            ]
            
    def scan_vault_connectivity(self):
        """Check vault knowledge graph health"""
        vault_dir = self.repo_root / "vault"
        if vault_dir.exists():
            notes = list(vault_dir.rglob("*.md"))
            self.patterns['vault_notes'] = [str(n.relative_to(vault_dir)) for n in notes]
            
    def scan_bible_principles(self):
        """Scan for BIBLE.md principle references in code"""
        bible_refs = re.findall(r'Principle\s+(\d+|0)', re.escape("Principle"))
        bible_file = self.repo_root / "BIBLE.md"
        if bible_file.exists():
            bible_content = bible_file.read_text()
            # Extract principle numbers
            principles = re.findall(r'## Principle (\d+|0):', bible_content)
            self.patterns['bible_principles'] = principles
            
    def compute_metrics(self):
        """Compute summary metrics"""
        # Module size distribution
        sizes = [p['lines'] for p in self.patterns['module_sizes']]
        self.metrics['total_modules'] = len(sizes)
        self.metrics['avg_module_lines'] = sum(sizes) / len(sizes) if sizes else 0
        self.metrics['max_module_lines'] = max(sizes) if sizes else 0
        self.metrics['large_modules'] = [p for p in self.patterns['module_sizes'] if p['lines'] > 1000]
        self.metrics['modules_over_150_lines'] = [p for p in self.patterns['module_sizes'] if p['lines'] > 150]
        
        # Import analysis
        imports_by_module = defaultdict(set)
        for imp in self.patterns['imports']:
            imports_by_module[imp['from']].add(imp['to'])
        self.metrics['import_counts'] = {m: len(imports) for m, imports in imports_by_module.items()}
        self.metrics['avg_imports_per_module'] = sum(self.metrics['import_counts'].values()) / len(self.metrics['import_counts']) if self.metrics['import_counts'] else 0
        
        # Tool count
        self.metrics['total_tools'] = len(self.patterns['tool_modules'])
        
        # Protection ratio
        total_code_files = len([p for p in self.patterns['module_sizes']])
        protected = len(self.patterns.get('protected_files', []))
        self.metrics['protection_ratio'] = protected / total_code_files if total_code_files else 0
        self.metrics['protected_file_count'] = protected
        
        # Vault health
        vault_notes = self.patterns.get('vault_notes', [])
        self.metrics['vault_note_count'] = len(vault_notes)
        
        # BIBLE principles found
        self.metrics['principles_referenced'] = len(self.patterns.get('bible_principles', []))
        
    def get_report(self, format='text'):
        """Generate report in specified format"""
        if format == 'json':
            return json.dumps({
                'patterns': dict(self.patterns),
                'metrics': self.metrics
            }, indent=2)
            
        # Text format
        report = []
        report.append("# Jo Pattern Scanner Report")
        report.append(f"\n## Summary Metrics")
        report.append(f"- Total Python modules: {self.metrics.get('total_modules', 0)}")
        report.append(f"- Average module size: {self.metrics.get('avg_module_lines', 0):.0f} lines")
        report.append(f"- Largest module: {self.metrics.get('max_module_lines', 0)} lines")
        report.append(f"- Modules > 150 lines: {len(self.metrics.get('modules_over_150_lines', []))}")
        report.append(f"- Modules > 1000 lines: {len(self.metrics.get('large_modules', []))}")
        report.append(f"- Total tools: {self.metrics.get('total_tools', 0)}")
        report.append(f"- Average imports per module: {self.metrics.get('avg_imports_per_module', 0):.1f}")
        report.append(f"- Protected files: {self.metrics.get('protected_file_count', 0)}")
        report.append(f"- Vault notes: {self.metrics.get('vault_note_count', 0)}")
        report.append(f"- BIBLE principles referenced: {self.metrics.get('principles_referenced', 0)}")
        
        if self.metrics.get('large_modules'):
            report.append("\n## Large Modules (Minimalism Violations)")
            for mod in sorted(self.metrics['large_modules'], key=lambda x: x['lines'], reverse=True)[:15]:
                report.append(f"- {mod['file']}: {mod['lines']} lines")
                
        if self.metrics.get('modules_over_150_lines'):
            report.append("\n## Modules Requiring Review (>150 lines)")
            for mod in sorted(self.metrics['modules_over_150_lines'], key=lambda x: x['lines'], reverse=True)[:20]:
                report.append(f"- {mod['file']}: {mod['lines']} lines")
        
        report.append("\n## Tool Modules")
        for tool in sorted(self.patterns.get('tool_modules', []), key=lambda x: x.get('module', '')):
            report.append(f"- {tool.get('module', str(tool))}")
            
        if self.patterns.get('protected_files'):
            report.append("\n## Protected Files")
            for p in self.patterns['protected_files'][:10]:
                report.append(f"- {p}")
            if len(self.patterns['protected_files']) > 10:
                report.append(f"... and {len(self.patterns['protected_files']) - 10} more")
                
        report.append("\n## BIBLE Principle Coverage")
        principles = self.patterns.get('bible_principles', [])
        report.append(f"- Principles found in code: {', '.join(sorted(set(principles))) if principles else 'None detected'}")
        
        report.append("\n## Evolution Signals")
        report.append("- High import counts may indicate God Object anti-pattern")
        report.append("- Large modules suggest decomposition opportunity")
        report.append("- Low tool count may indicate underutilized extension mechanism")
        report.append("- Protection ratio shows stability of core architecture")
        
        return "\n".join(report)

def main():
    import sys
    scanner = PatternScanner()
    scanner.scan()
    
    output_format = 'json' if '--json' in sys.argv else 'text'
    print(scanner.get_report(format=output_format))
    
if __name__ == "__main__":
    main()
