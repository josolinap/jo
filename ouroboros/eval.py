"""Task evaluator for Jo - scores outputs and enables self-correction."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class EvalResult:
    metric: str
    score: float
    details: str
    passed: bool


@dataclass
class EvalReport:
    overall_score: float
    passed: bool
    metrics: List[EvalResult]
    suggestions: List[str]


class TaskEvaluator:
    """Evaluates task outputs against quality criteria."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)
        self._enabled = os.environ.get("OUROBOROS_EVAL", "0") == "1"
        self._min_score = float(os.environ.get("OUROBOROS_EVAL_MIN_SCORE", "0.7"))
        self._criteria: Dict[str, Callable] = {
            "syntax": self._eval_syntax,
            "completeness": self._eval_completeness,
            "consistency": self._eval_consistency,
            "test_coverage": self._eval_test_coverage,
            "readability": self._eval_readability,
        }

    def is_enabled(self) -> bool:
        return self._enabled

    def evaluate(
        self,
        task: str,
        output: str,
        files_changed: Optional[List[str]] = None,
    ) -> Optional[EvalReport]:
        """Run all evaluations and return report."""
        if not self._enabled:
            return None

        if files_changed is None:
            files_changed = self._extract_changed_files(output)

        results = []

        for name, func in self._criteria.items():
            try:
                result = func(task, output, files_changed)
                if result:
                    results.append(result)
            except Exception as e:
                log.warning(f"Eval criterion {name} failed: {e}")

        if not results:
            return None

        overall = sum(r.score for r in results) / len(results)
        passed = overall >= self._min_score

        suggestions = []
        for r in results:
            if r.score < self._min_score:
                suggestions.append(f"{r.metric.title()}: {r.details}")

        return EvalReport(
            overall_score=overall,
            passed=passed,
            metrics=results,
            suggestions=suggestions,
        )

    def _extract_changed_files(self, output: str) -> List[str]:
        """Extract file paths mentioned in output."""
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

    def _eval_syntax(self, task: str, output: str, files: List[str]) -> Optional[EvalResult]:
        """Check if code has syntax errors."""
        py_files = [f for f in files if f.endswith(".py")]
        if not py_files:
            return None

        errors = []
        python_exes = ["py", "python3", "python"]

        for f in py_files:
            path = self.repo_dir / f
            if not path.exists():
                continue

            for python in python_exes:
                try:
                    result = subprocess.run(
                        [python, "-m", "py_compile", str(path)],
                        capture_output=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        stderr = result.stderr.decode() if result.stderr else ""
                        errors.append(f"{f}: {stderr[:100]}")
                    break
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    continue
                except Exception as e:
                    log.debug(f"Syntax check failed for {f}: {e}")

        if errors:
            return EvalResult(
                metric="syntax",
                score=0.0,
                details=f"Errors in: {', '.join(errors[:3])}",
                passed=False,
            )

        return EvalResult(
            metric="syntax",
            score=1.0,
            details="All Python files have valid syntax",
            passed=True,
        )

    def _eval_completeness(self, task: str, output: str, files: List[str]) -> EvalResult:
        """Check if task appears complete."""
        score = 1.0
        details: List[str] = []

        todos_added = 0
        for f in files:
            if f.endswith(".py"):
                path = self.repo_dir / f
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8", errors="ignore")
                        if "# TODO" in content or "# FIXME" in content:
                            todos_added += content.count("# TODO")
                            todos_added += content.count("# FIXME")
                    except Exception:
                        pass

        if todos_added > 5:
            score -= 0.3
            details.append(f"Added {todos_added} TODOs - task may be incomplete")

        completion_signals = [
            "completed",
            "done",
            "finished",
            "successfully",
            "implemented",
            "created",
        ]
        has_completion = any(signal in output.lower() for signal in completion_signals)
        if not has_completion:
            score -= 0.1
            details.append("Response doesn't clearly indicate completion")

        if not files:
            score -= 0.2
            details.append("No files were modified")

        return EvalResult(
            metric="completeness",
            score=max(0.0, score),
            details="; ".join(details) if details else "Task appears complete",
            passed=score >= self._min_score,
        )

    def _eval_consistency(self, task: str, output: str, files: List[str]) -> EvalResult:
        """Check for internal consistency."""
        issues: List[str] = []
        py_files = [f for f in files if f.endswith(".py")]

        if not py_files:
            return EvalResult(
                metric="consistency",
                score=1.0,
                details="No Python files to check",
                passed=True,
            )

        naming_issues = 0
        for f in py_files:
            path = self.repo_dir / f
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    snake_case = len(re.findall(r"\b[a-z][a-z0-9_]+\b", content))
                    camel_case = len(re.findall(r"\b[a-z][a-zA-Z0-9]+\b(?!\s*\()", content))
                    pascal_case = len(re.findall(r"\b[A-Z][a-zA-Z0-9]+\b(?!\s*\()", content))

                    if snake_case > 0 and (camel_case > 5 or pascal_case > 5):
                        naming_issues += 1
                except Exception:
                    pass

        if naming_issues > len(py_files) / 2:
            issues.append("Mixed naming conventions detected")

        score = 1.0 - (len(issues) * 0.2)

        return EvalResult(
            metric="consistency",
            score=max(0.0, score),
            details="; ".join(issues) if issues else "Consistent style",
            passed=score >= self._min_score,
        )

    def _eval_test_coverage(self, task: str, output: str, files: List[str]) -> EvalResult:
        """Check if tests were added for new code."""
        test_files = [f for f in files if "test" in f.lower()]
        code_files = [f for f in files if f.endswith(".py") and "test" not in f.lower()]

        if not code_files:
            return EvalResult(
                metric="test_coverage",
                score=1.0,
                details="No code files modified",
                passed=True,
            )

        if not test_files:
            has_test_signal = "test" in task.lower()
            if has_test_signal:
                return EvalResult(
                    metric="test_coverage",
                    score=0.3,
                    details="Task mentions tests but none were added",
                    passed=False,
                )
            return EvalResult(
                metric="test_coverage",
                score=0.7,
                details="No tests added (not explicitly required)",
                passed=True,
            )

        ratio = len(test_files) / len(code_files)
        score = min(1.0, ratio * 1.5)

        return EvalResult(
            metric="test_coverage",
            score=score,
            details=f"{len(test_files)} tests for {len(code_files)} code files",
            passed=score >= self._min_score,
        )

    def _eval_readability(self, task: str, output: str, files: List[str]) -> EvalResult:
        """Check code readability."""
        py_files = [f for f in files if f.endswith(".py")]

        if not py_files:
            return EvalResult(
                metric="readability",
                score=1.0,
                details="No Python files to check",
                passed=True,
            )

        issues = []
        for f in py_files:
            path = self.repo_dir / f
            if path.exists():
                try:
                    content = path.read_text(encoding="utf-8", errors="ignore")
                    lines = content.split("\n")

                    long_lines = sum(1 for line in lines if len(line) > 120)
                    if long_lines > len(lines) * 0.1:
                        issues.append(f"{f}: {long_lines} long lines (>120 chars)")

                    empty_lines = sum(1 for line in lines if line.strip() == "")
                    if empty_lines > len(lines) * 0.3:
                        issues.append(f"{f}: excessive empty lines")
                except Exception:
                    pass

        score = 1.0 - (len(issues) * 0.15)

        return EvalResult(
            metric="readability",
            score=max(0.0, score),
            details="; ".join(issues[:2]) if issues else "Good readability",
            passed=score >= self._min_score,
        )

    def format_report(self, report: EvalReport) -> str:
        """Format report for display."""
        if not report:
            return ""

        lines = [
            f"## Quality Check: {report.overall_score:.0%}",
            "",
        ]

        if report.suggestions:
            lines.append("**Issues Found:**")
            for suggestion in report.suggestions[:5]:
                lines.append(f"- {suggestion}")
        else:
            lines.append("**All checks passed** ✓")

        lines.append("")
        lines.append("### Breakdown")
        for metric in report.metrics:
            status = "✓" if metric.passed else "✗"
            lines.append(f"{status} {metric.metric}: {metric.score:.0%} - {metric.details}")

        return "\n".join(lines)


_evaluator: Optional[TaskEvaluator] = None


def get_evaluator(repo_dir: Path) -> TaskEvaluator:
    """Get singleton evaluator instance."""
    global _evaluator
    if _evaluator is None:
        _evaluator = TaskEvaluator(repo_dir)
    return _evaluator


def evaluate_task(
    task: str,
    output: str,
    files_changed: Optional[List[str]] = None,
    repo_dir: Optional[Path] = None,
) -> Optional[str]:
    """Evaluate task and return formatted report if issues found."""
    if repo_dir is None:
        return None

    evaluator = get_evaluator(repo_dir)
    if not evaluator.is_enabled():
        return None

    report = evaluator.evaluate(task, output, files_changed)
    if report and not report.passed:
        return evaluator.format_report(report)

    return None
