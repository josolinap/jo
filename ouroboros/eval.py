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


# ============================================================================
# BLIND VALIDATION - Inspired by Zeroshot's isolated validator concept
# ============================================================================


@dataclass
class BlindValidationResult:
    """Result of blind validation (no implementation context)."""

    passed: bool
    score: float  # 0.0 - 1.0
    findings: List[str]  # Actionable findings if failed
    checked_items: List[str]  # What was checked
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "score": self.score,
            "findings": self.findings,
            "checked_items": self.checked_items,
            "metadata": self.metadata,
        }


def blind_validate(
    task: str,
    result: str,
    code: str = "",
    repo_dir: Optional[Path] = None,
) -> BlindValidationResult:
    """Validate task result WITHOUT seeing implementation details.

    BLIND VALIDATION (Zeroshot-inspired):
    - Validator sees ONLY: task description + final result
    - Validator does NOT see: tool calls, reasoning, implementation steps

    This prevents "confirmation bias" where implementation details
    convince the validator that bad code is good.

    Args:
        task: Original task description
        result: Final output/result to validate
        code: Optional code content (if task involved coding)
        repo_dir: Repository directory

    Returns:
        BlindValidationResult with pass/fail and actionable findings
    """
    findings = []
    checked_items = []
    score = 1.0

    # Check 1: Does result address the task?
    checked_items.append("Task addressing")
    task_keywords = set(task.lower().split())
    result_lower = result.lower()

    # Simple heuristic: check if key task words appear in result
    key_matches = sum(1 for kw in task_keywords if len(kw) > 3 and kw in result_lower)
    if key_matches < 2 and len(task_keywords) > 3:
        findings.append(f"Result may not address task: '{task[:50]}...' not clearly addressed")
        score -= 0.2

    # Check 2: Is result substantive (not just "done" or "fixed")?
    checked_items.append("Result substance")
    if len(result.strip()) < 20:
        findings.append("Result too brief - expected detailed output")
        score -= 0.3

    # Check 3: If code involved, check for basic quality
    if code:
        checked_items.append("Code syntax")
        try:
            compile(code, "<string>", "exec")
        except SyntaxError as e:
            findings.append(f"Syntax error in code: {e}")
            score -= 0.4

        checked_items.append("Code completeness")
        # Check for TODO/FIXME markers
        if "TODO" in code or "FIXME" in code or "HACK" in code:
            findings.append("Code contains TODO/FIXME markers - may be incomplete")
            score -= 0.1

        # Check for bare except
        if "except:" in code and "pass" in code:
            findings.append("Code has bare 'except: pass' - errors silently swallowed")
            score -= 0.2

        # Check for pass-only functions
        if re.search(r"def \w+\([^)]*\):\s*pass", code):
            findings.append("Code has empty function definitions (pass only)")
            score -= 0.1

    # Check 4: Does result mention what was changed/fixed?
    checked_items.append("Change documentation")
    change_indicators = ["fixed", "added", "updated", "changed", "created", "modified", "removed"]
    has_change_mention = any(ind in result_lower for ind in change_indicators)
    if not has_change_mention and code:
        findings.append("Result doesn't describe what was changed")
        score -= 0.1

    # Check 5: Verify result isn't hallucinated
    checked_items.append("Hallucination check")
    unverifiable_claims = [
        "definitely works",
        "guaranteed to",
        "100% correct",
        "no bugs",
        "perfect solution",
    ]
    for claim in unverifiable_claims:
        if claim in result_lower:
            findings.append(f"Overconfident claim detected: '{claim}' - verify with tests")
            score -= 0.15

    # Check 6: If task mentions specific requirements, check they're addressed
    checked_items.append("Requirements check")
    requirement_patterns = [
        r"must\s+(\w+)",
        r"should\s+(\w+)",
        r"need[s]?\s+to\s+(\w+)",
        r"require[s]?\s+(\w+)",
    ]
    for pattern in requirement_patterns:
        matches = re.findall(pattern, task.lower())
        for req in matches:
            if req not in result_lower:
                findings.append(f"Requirement '{req}' may not be addressed in result")
                score -= 0.1

    # Calculate final score and pass/fail
    score = max(0.0, min(1.0, score))
    passed = score >= 0.7 and len(findings) == 0

    return BlindValidationResult(
        passed=passed,
        score=score,
        findings=findings,
        checked_items=checked_items,
        metadata={
            "task_length": len(task),
            "result_length": len(result),
            "code_provided": bool(code),
        },
    )


def blind_validate_with_action(
    task: str,
    result: str,
    code: str = "",
    repo_dir: Optional[Path] = None,
) -> str:
    """Run blind validation and return actionable feedback.

    This is the main entry point for blind validation in Jo's loop.
    Returns a message that can be injected into the LLM context.

    Args:
        task: Original task description
        result: Final output to validate
        code: Optional code content
        repo_dir: Repository directory

    Returns:
        Formatted feedback string (empty if passed)
    """
    validation = blind_validate(task, result, code, repo_dir)

    if validation.passed:
        return ""

    # Format actionable feedback
    lines = [
        "[BLIND VALIDATION] Task result has issues:",
        "",
        f"Score: {validation.score:.0%}",
        "",
        "**Findings:**",
    ]

    for i, finding in enumerate(validation.findings, 1):
        lines.append(f"{i}. {finding}")

    lines.extend(
        [
            "",
            "**What was checked:** " + ", ".join(validation.checked_items),
            "",
            "Please address these findings and try again.",
        ]
    )

    return "\n".join(lines)
