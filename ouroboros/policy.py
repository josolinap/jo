"""Policy as Code for evolution compliance.

Automated enforcement of coding standards during evolution cycles.
Validates changes against configurable rules before committing.

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
class PolicyRule:
    """A single policy rule."""

    name: str
    description: str
    severity: str  # error, warning, info
    check_fn: Any  # Callable[[str, str], Optional[str]]


@dataclass
class PolicyViolation:
    """A policy violation."""

    rule: str
    file: str
    message: str
    severity: str
    line: Optional[int] = None


@dataclass
class EvolutionPolicy:
    """Policy enforcement for code changes.

    Validates code changes against configurable rules before
    they are committed during evolution cycles.

    Usage:
        policy = EvolutionPolicy()
        violations = policy.validate_changes(changes)
        if not policy.allows_commit(violations):
            # Block commit
            pass
    """

    max_module_lines: int = 1000
    max_function_lines: int = 200
    require_docstrings: bool = False
    no_secrets: bool = True
    no_bare_except: bool = True
    no_print_statements: bool = False
    violations: List[PolicyViolation] = field(default_factory=list)

    def validate_file(self, file_path: str, content: str) -> List[PolicyViolation]:
        """Validate a single file against all policies."""
        violations = []

        # Check module size
        lines = content.count("\n") + 1
        if lines > self.max_module_lines:
            violations.append(
                PolicyViolation(
                    rule="max_module_lines",
                    file=file_path,
                    message=f"{lines} lines exceeds limit of {self.max_module_lines}",
                    severity="error",
                )
            )

        # Parse AST for deeper checks
        try:
            tree = ast.parse(content, filename=file_path)
            violations.extend(self._check_ast(file_path, tree, content))
        except SyntaxError as e:
            violations.append(
                PolicyViolation(
                    rule="syntax_error",
                    file=file_path,
                    message=f"Syntax error: {e}",
                    severity="error",
                    line=e.lineno,
                )
            )

        # Check for secrets
        if self.no_secrets:
            violations.extend(self._check_secrets(file_path, content))

        return violations

    def _check_ast(self, file_path: str, tree: ast.Module, content: str) -> List[PolicyViolation]:
        """Check AST for policy violations."""
        violations = []

        for node in ast.walk(tree):
            # Check function size
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                end_line = getattr(node, "end_lineno", node.lineno + 10)
                func_lines = end_line - node.lineno

                if func_lines > self.max_function_lines:
                    violations.append(
                        PolicyViolation(
                            rule="max_function_lines",
                            file=file_path,
                            message=f"{node.name} has {func_lines} lines (max {self.max_function_lines})",
                            severity="warning",
                            line=node.lineno,
                        )
                    )

                # Check docstrings
                if self.require_docstrings:
                    if not ast.get_docstring(node):
                        violations.append(
                            PolicyViolation(
                                rule="missing_docstring",
                                file=file_path,
                                message=f"{node.name} missing docstring",
                                severity="info",
                                line=node.lineno,
                            )
                        )

            # Check for bare except
            if self.no_bare_except and isinstance(node, ast.ExceptHandler):
                if node.type is None:
                    violations.append(
                        PolicyViolation(
                            rule="bare_except",
                            file=file_path,
                            message="Bare except clause - catch specific exceptions",
                            severity="warning",
                            line=node.lineno,
                        )
                    )

            # Check for print statements
            if self.no_print_statements and isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "print":
                    violations.append(
                        PolicyViolation(
                            rule="print_statement",
                            file=file_path,
                            message="Use logging instead of print()",
                            severity="info",
                            line=node.lineno,
                        )
                    )

        return violations

    def _check_secrets(self, file_path: str, content: str) -> List[PolicyViolation]:
        """Check for potential secrets in content."""
        violations = []
        secret_patterns = [
            ("API key", r"(?i)api[_-]?key\s*=\s*['\"][a-zA-Z0-9]{20,}"),
            ("Password", r"(?i)password\s*=\s*['\"][^\s'\"]{8,}"),
            ("Token", r"(?i)token\s*=\s*['\"][a-zA-Z0-9]{20,}"),
            ("Private key", r"-----BEGIN (RSA |EC )?PRIVATE KEY-----"),
        ]

        import re

        for name, pattern in secret_patterns:
            if re.search(pattern, content):
                violations.append(
                    PolicyViolation(
                        rule="potential_secret",
                        file=file_path,
                        message=f"Potential {name} detected - verify this is not a secret",
                        severity="error",
                    )
                )

        return violations

    def validate_changes(self, changes: List[Dict[str, Any]]) -> List[PolicyViolation]:
        """Validate a list of file changes."""
        all_violations = []

        for change in changes:
            file_path = change.get("file", "unknown")
            content = change.get("content", "")

            if content:
                all_violations.extend(self.validate_file(file_path, content))

        self.violations = all_violations
        return all_violations

    def allows_commit(self, violations: Optional[List[PolicyViolation]] = None) -> bool:
        """Check if commit is allowed given violations."""
        if violations is None:
            violations = self.violations

        # Block on any error-level violations
        errors = [v for v in violations if v.severity == "error"]
        return len(errors) == 0

    def format_violations(self, violations: Optional[List[PolicyViolation]] = None) -> str:
        """Format violations for display."""
        if violations is None:
            violations = self.violations

        if not violations:
            return "No policy violations"

        lines = ["Policy Violations:", ""]
        for v in violations:
            icon = {"error": "X", "warning": "!", "info": "i"}.get(v.severity, "?")
            loc = f":{v.line}" if v.line else ""
            lines.append(f"  [{icon}] {v.file}{loc}: {v.message}")

        errors = sum(1 for v in violations if v.severity == "error")
        warnings = sum(1 for v in violations if v.severity == "warning")
        lines.append(f"\nTotal: {errors} errors, {warnings} warnings")

        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Get policy summary."""
        errors = sum(1 for v in self.violations if v.severity == "error")
        warnings = sum(1 for v in self.violations if v.severity == "warning")
        infos = sum(1 for v in self.violations if v.severity == "info")

        return {
            "total": len(self.violations),
            "errors": errors,
            "warnings": warnings,
            "infos": infos,
            "allows_commit": self.allows_commit(),
        }


# Default policy for Jo
def create_default_policy() -> EvolutionPolicy:
    """Create default policy for Jo's evolution cycles."""
    return EvolutionPolicy(
        max_module_lines=1000,
        max_function_lines=200,
        require_docstrings=False,
        no_secrets=True,
        no_bare_except=True,
        no_print_statements=False,
    )
