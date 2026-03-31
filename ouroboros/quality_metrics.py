"""Quality metrics framework for code assessment.

Multi-dimensional quality evaluation inspired by TurboQuant+'s
comprehensive testing approach (500+ tests, multiple validation dimensions).

Following Principle 5 (Minimalism): under 250 lines.
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class QualityScore:
    """Quality score for a module or codebase."""

    complexity: float = 0.0
    cohesion: float = 0.0
    coupling: float = 0.0
    test_coverage: float = 0.0
    doc_coverage: float = 0.0
    security_score: float = 0.0
    overall: float = 0.0


@dataclass
class QualityMetrics:
    """Multi-dimensional quality assessment for code.

    Evaluates code across six dimensions:
    - Complexity: cyclomatic complexity
    - Cohesion: intra-module relatedness
    - Coupling: inter-module dependencies
    - Test coverage: proportion of code tested
    - Documentation: docstring coverage
    - Security: absence of vulnerabilities

    Usage:
        metrics = QualityMetrics()
        score = metrics.evaluate_file("ouroboros/agent.py")
        print(f"Overall: {score.overall:.2f}")
    """

    complexity_weight: float = 0.20
    cohesion_weight: float = 0.15
    coupling_weight: float = 0.15
    test_weight: float = 0.25
    doc_weight: float = 0.10
    security_weight: float = 0.15

    def evaluate_file(self, file_path: str, content: Optional[str] = None) -> QualityScore:
        """Evaluate a single file."""
        if content is None:
            try:
                content = Path(file_path).read_text(encoding="utf-8")
            except Exception:
                return QualityScore()

        try:
            tree = ast.parse(content, filename=file_path)
        except SyntaxError:
            return QualityScore()

        complexity = self._compute_complexity(tree, content)
        cohesion = self._compute_cohesion(tree)
        coupling = self._compute_coupling(tree)
        doc_coverage = self._compute_doc_coverage(tree)
        security = self._compute_security(content)

        overall = (
            complexity * self.complexity_weight
            + cohesion * self.cohesion_weight
            + coupling * self.coupling_weight
            + doc_coverage * self.doc_weight
            + security * self.security_weight
        )

        return QualityScore(
            complexity=complexity,
            cohesion=cohesion,
            coupling=coupling,
            test_coverage=0.0,  # Requires test runner
            doc_coverage=doc_coverage,
            security_score=security,
            overall=overall,
        )

    def _compute_complexity(self, tree: ast.Module, content: str) -> float:
        """Compute complexity score (0-1, higher is better)."""
        lines = content.count("\n") + 1

        # Count decision points
        decision_points = 0
        for node in ast.walk(tree):
            if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
                decision_points += 1
            elif isinstance(node, ast.BoolOp):
                decision_points += len(node.values) - 1

        # Normalize: fewer decision points per line = simpler
        if lines == 0:
            return 1.0
        density = decision_points / lines
        return max(0.0, min(1.0, 1.0 - density * 10))

    def _compute_cohesion(self, tree: ast.Module) -> float:
        """Compute cohesion score (0-1, higher is better)."""
        # Simple heuristic: functions that share variable names are more cohesive
        func_vars = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                vars_used = set()
                for child in ast.walk(node):
                    if isinstance(child, ast.Name):
                        vars_used.add(child.id)
                func_vars[node.name] = vars_used

        if len(func_vars) < 2:
            return 0.5

        # Compute overlap
        overlaps = 0
        pairs = 0
        funcs = list(func_vars.items())
        for i, (name1, vars1) in enumerate(funcs):
            for name2, vars2 in funcs[i + 1 :]:
                if vars1 and vars2:
                    overlap = len(vars1 & vars2) / max(len(vars1 | vars2), 1)
                    overlaps += overlap
                    pairs += 1

        return min(1.0, overlaps / max(pairs, 1) + 0.3)

    def _compute_coupling(self, tree: ast.Module) -> float:
        """Compute coupling score (0-1, higher = less coupling = better)."""
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split(".")[0])

        # Fewer imports = less coupling
        if len(imports) <= 5:
            return 1.0
        elif len(imports) <= 10:
            return 0.8
        elif len(imports) <= 20:
            return 0.6
        else:
            return max(0.3, 1.0 - len(imports) / 50)

    def _compute_doc_coverage(self, tree: ast.Module) -> float:
        """Compute documentation coverage (0-1)."""
        total = 0
        documented = 0

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                total += 1
                if ast.get_docstring(node):
                    documented += 1

        if total == 0:
            return 1.0
        return documented / total

    def _compute_security(self, content: str) -> float:
        """Compute security score (0-1, higher is better)."""
        issues = 0

        # Check for common security issues
        security_patterns = [
            ("eval(", "Use of eval()"),
            ("exec(", "Use of exec()"),
            ("__import__", "Dynamic import"),
            ("subprocess.call(shell=True)", "Shell injection risk"),
            ("os.system(", "OS command injection risk"),
        ]

        for pattern, _ in security_patterns:
            if pattern in content:
                issues += 1

        # Check for hardcoded secrets
        import re

        if re.search(r"(?i)(api_key|password|token)\s*=\s*['\"][a-zA-Z0-9]{8,}", content):
            issues += 1

        return max(0.0, 1.0 - issues * 0.15)

    def evaluate_directory(self, dir_path: str) -> QualityScore:
        """Evaluate all Python files in a directory."""
        path = Path(dir_path)
        if not path.exists():
            return QualityScore()

        scores = []
        for py_file in path.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            scores.append(self.evaluate_file(str(py_file)))

        if not scores:
            return QualityScore()

        return QualityScore(
            complexity=sum(s.complexity for s in scores) / len(scores),
            cohesion=sum(s.cohesion for s in scores) / len(scores),
            coupling=sum(s.coupling for s in scores) / len(scores),
            test_coverage=sum(s.test_coverage for s in scores) / len(scores),
            doc_coverage=sum(s.doc_coverage for s in scores) / len(scores),
            security_score=sum(s.security_score for s in scores) / len(scores),
            overall=sum(s.overall for s in scores) / len(scores),
        )

    def format_score(self, score: QualityScore) -> str:
        """Format quality score for display."""

        def grade(value: float) -> str:
            if value >= 0.9:
                return "A"
            elif value >= 0.8:
                return "B"
            elif value >= 0.7:
                return "C"
            elif value >= 0.6:
                return "D"
            else:
                return "F"

        return (
            f"Quality Score: {grade(score.overall)} ({score.overall:.1%})\n"
            f"  Complexity:   {grade(score.complexity)} ({score.complexity:.1%})\n"
            f"  Cohesion:     {grade(score.cohesion)} ({score.cohesion:.1%})\n"
            f"  Coupling:     {grade(score.coupling)} ({score.coupling:.1%})\n"
            f"  Docs:         {grade(score.doc_coverage)} ({score.doc_coverage:.1%})\n"
            f"  Security:     {grade(score.security_score)} ({score.security_score:.1%})"
        )


def quick_evaluate(file_path: str) -> QualityScore:
    """Quick quality evaluation for a single file."""
    metrics = QualityMetrics()
    return metrics.evaluate_file(file_path)
