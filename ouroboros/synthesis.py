"""Semantic synthesizer for Jo - post-task consistency and quality checks."""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

log = logging.getLogger(__name__)


@dataclass
class SynthesisIssue:
    issue_type: str
    severity: str
    description: str
    files: List[str]
    suggestion: str
    auto_fixable: bool = False


@dataclass
class SynthesisReport:
    issues: List[SynthesisIssue]
    files_analyzed: int
    suggestions: List[str]


class SemanticSynthesizer:
    """Post-task synthesis for consistency and quality."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)
        self._enabled = os.environ.get("OUROBOROS_SYNTHESIS", "0") == "1"
        self._checkers: List[Tuple[str, callable]] = [
            ("naming", self._check_naming_consistency),
            ("imports", self._check_import_organization),
            ("docstrings", self._check_docstring_consistency),
            ("formatting", self._check_formatting_consistency),
            ("refactor_hints", self._check_refactor_opportunities),
        ]

    def is_enabled(self) -> bool:
        return self._enabled

    def synthesize(
        self, task: str, output: str, files_changed: Optional[List[str]] = None
    ) -> Optional[SynthesisReport]:
        """Analyze files and return synthesis issues."""
        if not self._enabled:
            return None

        if not files_changed:
            files_changed = self._extract_files_from_output(output)

        py_files = [f for f in files_changed if f.endswith(".py")]
        if not py_files:
            return None

        all_issues: List[SynthesisIssue] = []

        for check_name, check_func in self._checkers:
            try:
                issues = check_func(py_files)
                all_issues.extend(issues)
            except Exception as e:
                log.debug(f"Synthesis check '{check_name}' failed: {e}")

        suggestions = []
        for issue in all_issues[:5]:
            suggestions.append(f"{issue.description}: {issue.suggestion}")

        return SynthesisReport(
            issues=all_issues,
            files_analyzed=len(py_files),
            suggestions=suggestions,
        )

    def _extract_files_from_output(self, output: str) -> List[str]:
        """Extract file paths from output."""
        files: List[str] = []
        patterns = [
            r"(?:modified|created|updated|changed):\s*(.+\.py)",
            r"```(?:python|py)\n.+/([^\n/]+\.py)",
            r"(?:\w+/)+[\w-]+\.py",
        ]
        for pattern in patterns:
            matches = re.findall(pattern, output, re.IGNORECASE)
            files.extend(matches)
        return list(set(files))[:20]

    def _read_file(self, filepath: str) -> Optional[str]:
        """Read file content safely."""
        try:
            path = self.repo_dir / filepath
            if path.exists():
                return path.read_text(encoding="utf-8", errors="ignore")
        except Exception as e:
            log.debug(f"Failed to read {filepath}: {e}")
        return None

    def _check_naming_consistency(self, files: List[str]) -> List[SynthesisIssue]:
        """Check if naming conventions are consistent across files."""
        issues: List[SynthesisIssue] = []

        snake_case_names: Set[str] = set()
        camel_case_names: Set[str] = set()
        pascal_case_names: Set[str] = set()

        for f in files:
            content = self._read_file(f)
            if not content:
                continue

            for match in re.finditer(r"\b([a-z][a-z0-9_]+)\b", content):
                name = match.group(1)
                if len(name) >= 3 and name not in {"and", "for", "not", "the", "import"}:
                    snake_case_names.add(name)

            for match in re.finditer(r"\b([a-z][a-zA-Z0-9]+)\b", content):
                name = match.group(1)
                if len(name) >= 3 and name[0].islower():
                    camel_case_names.add(name)

            for match in re.finditer(r"\b([A-Z][a-zA-Z0-9]+)\b", content):
                name = match.group(1)
                if len(name) >= 2:
                    pascal_case_names.add(name)

        if len(snake_case_names) > 0 and len(camel_case_names) > 10:
            issues.append(
                SynthesisIssue(
                    issue_type="naming",
                    severity="medium",
                    description="Mixed naming conventions detected",
                    files=files[:3],
                    suggestion="Use snake_case for variables/functions, PascalCase for classes. Avoid camelCase in Python.",
                    auto_fixable=False,
                )
            )

        return issues

    def _check_import_organization(self, files: List[str]) -> List[SynthesisIssue]:
        """Check if imports are properly organized."""
        issues: List[SynthesisIssue] = []

        has_unorganized_imports = False
        affected_files: List[str] = []

        for f in files:
            content = self._read_file(f)
            if not content:
                continue

            lines = content.split("\n")
            imports: List[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("import ") or stripped.startswith("from "):
                    imports.append(stripped)

            if len(imports) > 3:
                sorted_imports = sorted(imports, key=lambda x: (not x.startswith("from "), x))
                if imports != sorted_imports:
                    has_unorganized_imports = True
                    affected_files.append(f)

        if has_unorganized_imports:
            issues.append(
                SynthesisIssue(
                    issue_type="imports",
                    severity="low",
                    description="Import statements may not be organized",
                    files=affected_files[:3],
                    suggestion="Organize imports: stdlib first, then third-party, then local. Use 'isort' to auto-fix.",
                    auto_fixable=True,
                )
            )

        return issues

    def _check_docstring_consistency(self, files: List[str]) -> List[SynthesisIssue]:
        """Check for docstring consistency."""
        issues: List[SynthesisIssue] = []

        has_docstrings = 0
        no_docstrings = 0

        for f in files:
            content = self._read_file(f)
            if not content:
                continue

            functions = re.findall(r"def (\w+)\([^)]*\):", content)
            if not functions:
                continue

            for func in functions:
                if func.startswith("_"):
                    continue

                pattern = rf"def {func}\([^)]*\):\s*(?:\"\"\".*?\"\"\"|'''.*?'''|\n\s+#)"
                if re.search(pattern, content, re.DOTALL):
                    has_docstrings += 1
                else:
                    no_docstrings += 1

        if has_docstrings > 0 and no_docstrings > has_docstrings:
            issues.append(
                SynthesisIssue(
                    issue_type="docstrings",
                    severity="low",
                    description=f"Only {has_docstrings} of {has_docstrings + no_docstrings} public functions have docstrings",
                    files=files[:3],
                    suggestion="Add docstrings to all public functions describing purpose, args, and return values.",
                    auto_fixable=False,
                )
            )

        return issues

    def _check_formatting_consistency(self, files: List[str]) -> List[SynthesisIssue]:
        """Check for formatting consistency issues."""
        issues: List[SynthesisIssue] = []

        single_quotes = 0
        double_quotes = 0

        for f in files:
            content = self._read_file(f)
            if not content:
                continue

            single_quotes += len(re.findall(r"'[^']*'", content))
            double_quotes += len(re.findall(r'"[^"]*"', content))

        if single_quotes > 20 and double_quotes > 20:
            ratio = min(single_quotes, double_quotes) / max(single_quotes, double_quotes)
            if ratio > 0.4:
                issues.append(
                    SynthesisIssue(
                        issue_type="formatting",
                        severity="low",
                        description="Mixed quote styles (single and double quotes)",
                        files=files[:3],
                        suggestion="Choose one quote style. Python convention: double quotes for strings.",
                        auto_fixable=True,
                    )
                )

        return issues

    def _check_refactor_opportunities(self, files: List[str]) -> List[SynthesisIssue]:
        """Find code patterns that could be refactored."""
        issues: List[SynthesisIssue] = []

        repeated_blocks: Dict[str, int] = {}
        long_functions: List[Tuple[str, int]] = []

        for f in files:
            content = self._read_file(f)
            if not content:
                continue

            functions = re.finditer(r"def (\w+)\([^)]*\):", content)
            lines = content.split("\n")

            for match in functions:
                func_name = match.group(1)
                start = match.end()
                indent = len(lines[match.start() // 100]) - len(lines[match.start() // 100].lstrip())

                func_lines = []
                for i, line in enumerate(lines[start : start + 100]):
                    if line.strip() and not line.startswith(" " * (indent + 1)):
                        break
                    func_lines.append(line)

                if len(func_lines) > 50:
                    long_functions.append((f, len(func_lines)))

            code_blocks = re.findall(r"(?:if|for|while).*:\s*\n((?:\s{4,}.+\n)+)", content)
            for block in code_blocks:
                block_hash = hash(block.strip())
                repeated_blocks[block_hash] = repeated_blocks.get(block_hash, 0) + 1

        if long_functions:
            issues.append(
                SynthesisIssue(
                    issue_type="refactor_hints",
                    severity="low",
                    description=f"Found {len(long_functions)} long functions (>50 lines)",
                    files=[f for f, _ in long_functions[:3]],
                    suggestion="Consider breaking long functions into smaller, focused functions.",
                    auto_fixable=False,
                )
            )

        repeated = [count for count in repeated_blocks.values() if count > 2]
        if len(repeated) > 3:
            issues.append(
                SynthesisIssue(
                    issue_type="refactor_hints",
                    severity="medium",
                    description=f"Found {len(repeated)} repeated code blocks",
                    files=files[:3],
                    suggestion="Extract repeated code into helper functions or constants.",
                    auto_fixable=False,
                )
            )

        return issues

    def format_report(self, report: SynthesisReport) -> str:
        """Format synthesis report for display."""
        if not report or not report.issues:
            return ""

        lines = [
            "## Synthesis Report",
            f"Reviewed {report.files_analyzed} files",
            "",
        ]

        auto_fixable = [i for i in report.issues if i.auto_fixable]
        manual_only = [i for i in report.issues if not i.auto_fixable]

        if auto_fixable:
            lines.append("### Auto-fixable Issues")
            for issue in auto_fixable[:3]:
                lines.append(f"- [{issue.issue_type}] {issue.description}")
                lines.append(f"  Fix: {issue.suggestion}")

        if manual_only:
            lines.append("")
            lines.append("### Suggestions for Improvement")
            for issue in manual_only[:5]:
                lines.append(f"- **[{issue.issue_type}]** {issue.description}")
                lines.append(f"  → {issue.suggestion}")

        return "\n".join(lines)


_synthesizer: Optional[SemanticSynthesizer] = None


def get_synthesizer(repo_dir: Path) -> SemanticSynthesizer:
    """Get singleton synthesizer instance."""
    global _synthesizer
    if _synthesizer is None:
        _synthesizer = SemanticSynthesizer(repo_dir)
    return _synthesizer


def synthesize_task(
    task: str,
    output: str,
    files_changed: Optional[List[str]] = None,
    repo_dir: Optional[Path] = None,
) -> Optional[str]:
    """Run synthesis and return formatted report."""
    if repo_dir is None:
        return None

    synthesizer = get_synthesizer(repo_dir)
    if not synthesizer.is_enabled():
        return None

    report = synthesizer.synthesize(task, output, files_changed)
    if report and report.issues:
        return synthesizer.format_report(report)

    return None
