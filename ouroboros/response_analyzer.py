"""Response Analyzer - Detects hallucinations, drift, and avoidance in LLM responses.

Phase 1: Response Quality Analysis
- Analyzes LLM responses for quality issues
- Provides targeted feedback for the next round
- Integrates with loop.py for continuous improvement
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.utils import utc_now_iso


@dataclass
class QualityIssue:
    """A detected quality issue in the response."""

    issue_type: str  # "hallucination", "drift", "avoidance", "overconfidence"
    severity: str  # "high", "medium", "low"
    description: str
    evidence: List[str] = field(default_factory=list)
    suggestion: str = ""


@dataclass
class ResponseAnalysis:
    """Complete analysis of an LLM response."""

    issues: List[QualityIssue] = field(default_factory=list)
    quality_score: float = 1.0  # 0.0 to 1.0
    drift_detected: bool = False
    hallucination_detected: bool = False
    avoidance_detected: bool = False
    confidence: str = "normal"  # "low", "normal", "high", "overconfident"
    feedback_for_next_round: str = ""


class ResponseAnalyzer:
    """Analyzes LLM responses for quality issues."""

    def __init__(self):
        self._response_history: List[Dict[str, Any]] = []
        self._tool_call_history: List[str] = []

    def analyze(
        self,
        response_text: str,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
        repo_dir: str = "",
    ) -> ResponseAnalysis:
        """Analyze a response and return quality issues."""
        issues: List[QualityIssue] = []

        # Track for drift detection
        self._track_response(response_text, tool_calls)

        # Detect hallucinations
        hall_issues = self._detect_hallucinations(response_text, tool_calls, repo_dir)
        issues.extend(hall_issues)

        # Detect drift
        drift_issues = self._detect_drift(response_text, tool_calls)
        issues.extend(drift_issues)

        # Detect avoidance
        avoid_issues = self._detect_avoidance(response_text, tool_calls, messages)
        issues.extend(avoid_issues)

        # Detect overconfidence
        conf_issues = self._detect_overconfidence(response_text, tool_calls)
        issues.extend(conf_issues)

        # Calculate quality score
        quality_score = self._calculate_quality_score(issues)

        # Generate feedback
        feedback = self._generate_feedback(issues)

        return ResponseAnalysis(
            issues=issues,
            quality_score=quality_score,
            drift_detected=any(i.issue_type == "drift" for i in issues),
            hallucination_detected=any(i.issue_type == "hallucination" for i in issues),
            avoidance_detected=any(i.issue_type == "avoidance" for i in issues),
            confidence=self._assess_confidence(response_text, issues),
            feedback_for_next_round=feedback,
        )

    def _track_response(self, response_text: str, tool_calls: List[Dict[str, Any]]) -> None:
        """Track response for drift detection."""
        # Track tool calls for pattern detection
        for tc in tool_calls:
            tool_name = tc.get("tool", tc.get("function", {}).get("name", "unknown"))
            self._tool_call_history.append(tool_name)

        # Keep last 20 responses
        self._response_history.append(
            {
                "text": response_text[:500],  # First 500 chars
                "tools": [tc.get("tool", "unknown") for tc in tool_calls],
                "timestamp": utc_now_iso(),
            }
        )

        if len(self._response_history) > 20:
            self._response_history = self._response_history[-20:]
        if len(self._tool_call_history) > 50:
            self._tool_call_history = self._tool_call_history[-50:]

    def _detect_hallucinations(
        self,
        response: str,
        tool_calls: List[Dict[str, Any]],
        repo_dir: str,
    ) -> List[QualityIssue]:
        """Detect potential hallucinations in the response."""
        issues: List[QualityIssue] = []

        # Pattern 1: Claims about files/functions that might not exist
        fake_patterns = [
            r"function\s+(\w+)\s*\(",  # Claims function exists
            r"class\s+(\w+)\s*[:(]",  # Claims class exists
            r"`(\w+)`",  # Backtick-quoted identifiers
        ]

        claimed_identifiers: List[str] = []
        for pattern in fake_patterns:
            matches = re.findall(pattern, response)
            claimed_identifiers.extend(matches)

        # Check for over-specific claims without verification
        unverifiable_claims = [
            r"this will definitely work",
            r"guaranteed to",
            r"absolutely certain",
            r"without a doubt",
            r"the code is perfect",
            r"there are no bugs",
        ]

        has_unverifiable = any(re.search(p, response, re.IGNORECASE) for p in unverifiable_claims)

        if has_unverifiable and not tool_calls:
            issues.append(
                QualityIssue(
                    issue_type="hallucination",
                    severity="medium",
                    description="Confident claim without any code verification",
                    evidence=["Made unverifiable claim", "No tool calls to verify"],
                    suggestion="Verify claims with repo_read or grep before stating as fact.",
                )
            )

        # Pattern 2: References to specific line numbers without checking
        line_refs = re.findall(r"line\s+(\d+)", response, re.IGNORECASE)
        if line_refs and "repo_read" not in str(tool_calls):
            issues.append(
                QualityIssue(
                    issue_type="hallucination",
                    severity="high",
                    description=f"References to specific lines ({', '.join(line_refs[:3])}) without reading the file",
                    evidence=[f"Claimed line {n} exists" for n in line_refs[:3]],
                    suggestion="Read the file first with repo_read to verify line references.",
                )
            )

        # Pattern 3: Vague but confident imports/dependencies
        import_claims = re.findall(r"(?:import|from)\s+([\w.]+)", response)
        if import_claims and not any("import" in str(tc) or "shell" in str(tc) for tc in tool_calls):
            # Check if claimed imports exist
            issues.append(
                QualityIssue(
                    issue_type="hallucination",
                    severity="low",
                    description=f"References imports ({len(import_claims)}) without verification",
                    evidence=[f"Claims: {', '.join(import_claims[:5])}"],
                    suggestion="Verify imports exist with repo_read or shell_run.",
                )
            )

        # Pattern 4: Claims about files that don't actually exist
        if repo_dir and os.path.isdir(repo_dir):
            issues.extend(self._verify_file_claims(response, repo_dir))

        # Pattern 5: Fabricated test counts
        issues.extend(self._verify_test_claims(response, repo_dir))

        # Pattern 6: Fabricated metrics (coverage %, performance numbers)
        issues.extend(self._verify_metric_claims(response, tool_calls))

        return issues

    def _verify_file_claims(self, response: str, repo_dir: str) -> List[QualityIssue]:
        """Verify that files mentioned in the response actually exist."""
        issues: List[QualityIssue] = []
        repo_path = Path(repo_dir)

        # Extract file paths mentioned in response
        # Pattern: paths like ouroboros/foo.py, tests/test_bar.py, scripts/baz.sh, etc.
        file_patterns = [
            r"(?:ouroboros|tests?|scripts?|vault|supervisor|memory)[/\\][\w./\\-]+\.(?:py|sh|json|md|yaml|yml|toml)",
            r"(?:src|lib|pkg)[/\\][\w./\\-]+\.(?:py|sh|json|md)",
        ]

        claimed_files: List[str] = []
        for pattern in file_patterns:
            matches = re.findall(pattern, response)
            claimed_files.extend(matches)

        # Normalize and check existence
        non_existent: List[str] = []
        for f in claimed_files:
            normalized = f.replace("\\", "/").strip("./")
            full_path = repo_path / normalized
            if not full_path.exists():
                non_existent.append(normalized)

        if non_existent:
            # Check context: are these files being claimed as CREATED/MODIFIED?
            creation_verbs = r"(?:created?|added?|wrote|introduced?|modified?|updated?|fixed?|refactored?)"
            claimed_as_changed = []
            for f in non_existent:
                # Look for the file near creation verbs
                escaped = re.escape(f)
                context_pattern = creation_verbs + r".{0,80}" + escaped
                alt_pattern = (
                    escaped + r".{0,80}" + "(?:created|added|wrote|introduced|modified|updated|fixed|refactored)"
                )
                if re.search(context_pattern, response, re.IGNORECASE) or re.search(
                    alt_pattern, response, re.IGNORECASE
                ):
                    claimed_as_changed.append(f)

            severity = "high" if len(claimed_as_changed) >= 2 else "medium" if claimed_as_changed else "low"
            description = (
                f"Claims {len(claimed_as_changed)} files were created/modified but they don't exist"
                if claimed_as_changed
                else f"References {len(non_existent)} files that don't exist"
            )
            issues.append(
                QualityIssue(
                    issue_type="hallucination",
                    severity=severity,
                    description=description,
                    evidence=[f"Missing: {', '.join(non_existent[:5])}"],
                    suggestion="Verify files exist with repo_list or glob_files before claiming changes.",
                )
            )

        return issues

    def _verify_test_claims(self, response: str, repo_dir: str) -> List[QualityIssue]:
        """Verify test count claims match reality."""
        issues: List[QualityIssue] = []

        # Look for test count claims like "9 tests total", "5 new tests", "90 tests"
        test_count_patterns = [
            r"(\d+)\s+(?:new\s+)?tests?\s+(?:total|passed|run|exist|added|created|covering)",
            r"(?:total|of)\s+(\d+)\s+tests?",
            r"(\d+)\s+tests?\s+(?:in\s+)?(?:the\s+)?(?:suite|project|codebase|repo)",
            r"pytest.*?(\d+)\s+(?:passed|tests)",
        ]

        claimed_counts: List[int] = []
        for pattern in test_count_patterns:
            matches = re.findall(pattern, response, re.IGNORECASE)
            for m in matches:
                try:
                    claimed_counts.append(int(m))
                except ValueError:
                    pass

        if claimed_counts and repo_dir and os.path.isdir(repo_dir):
            # Deduplicate claimed counts
            claimed_counts = list(set(claimed_counts))
            # Count actual tests by scanning test files
            test_dir = Path(repo_dir) / "tests"
            if test_dir.exists():
                actual_count = 0
                for py_file in test_dir.glob("test_*.py"):
                    try:
                        content = py_file.read_text(encoding="utf-8", errors="replace")
                        actual_count += len(re.findall(r"def\s+test_\w+", content))
                    except Exception:
                        pass

                for claimed in claimed_counts:
                    # Allow small variance (collect vs run counts differ)
                    if actual_count > 0 and abs(claimed - actual_count) > max(5, actual_count * 0.2):
                        issues.append(
                            QualityIssue(
                                issue_type="hallucination",
                                severity="high",
                                description=f"Claims {claimed} tests exist but actual count is ~{actual_count}",
                                evidence=[f"Claimed: {claimed}", f"Actual: {actual_count}"],
                                suggestion="Run 'pytest --collect-only -q' to get the real test count.",
                            )
                        )

        return issues

    def _verify_metric_claims(self, response: str, tool_calls: List[Dict[str, Any]]) -> List[QualityIssue]:
        """Verify that performance/coverage metrics were actually measured."""
        issues: List[QualityIssue] = []
        response_lower = response.lower()

        # Coverage percentage claims without running coverage
        coverage_match = re.search(r"(?:coverage|cov)[:\s]*(\d+)\s*%", response_lower)
        if coverage_match:
            used_coverage = any("coverage" in str(tc) or "pytest" in str(tc) or "--cov" in str(tc) for tc in tool_calls)
            if not used_coverage:
                issues.append(
                    QualityIssue(
                        issue_type="hallucination",
                        severity="high",
                        description=f"Claims {coverage_match.group(1)}% coverage without running coverage tools",
                        evidence=["Coverage claimed", "No coverage tool call detected"],
                        suggestion="Run 'pytest --cov' to get actual coverage data.",
                    )
                )

        # Performance timing claims without benchmarks
        timing_match = re.search(r"(\d+\.?\d*)\s*s(?:econds?)?\s*(?:average|avg|mean|runtime|latency)", response_lower)
        if timing_match and not tool_calls:
            issues.append(
                QualityIssue(
                    issue_type="hallucination",
                    severity="high",
                    description=f"Claims {timing_match.group(1)}s performance without running benchmarks",
                    evidence=["Timing metric claimed", "No tool calls to measure it"],
                    suggestion="Use time.time() or a benchmarking tool to measure actual performance.",
                )
            )

        return issues

    def _detect_drift(
        self,
        response: str,
        tool_calls: List[Dict[str, Any]],
    ) -> List[QualityIssue]:
        """Detect if the agent is drifting in circles."""
        issues: List[QualityIssue] = []

        # Check for repetitive tool calls
        if len(self._tool_call_history) >= 6:
            recent = self._tool_call_history[-6:]
            if len(set(recent)) <= 2:  # Only 1-2 unique tools
                tool_counts: Dict[str, int] = {}
                for t in recent:
                    tool_counts[t] = tool_counts.get(t, 0) + 1
                repetitive = [f"{t}: {c}x" for t, c in tool_counts.items() if c >= 3]
                if repetitive:
                    issues.append(
                        QualityIssue(
                            issue_type="drift",
                            severity="medium",
                            description="Repetitive tool calls detected",
                            evidence=repetitive,
                            suggestion="Try a different approach. Consider using grep to find patterns or repo_list to explore structure.",
                        )
                    )

        # Check for repetitive phrases in response
        response_lower = response.lower()
        repetitive_phrases = [
            "let me check",
            "i need to",
            "first, let's",
            "looking at the",
        ]
        phrase_count = sum(1 for p in repetitive_phrases if p in response_lower)

        if phrase_count >= 4:
            issues.append(
                QualityIssue(
                    issue_type="drift",
                    severity="low",
                    description="Repetitive opening phrases",
                    evidence=["Uses the same phrases repeatedly"],
                    suggestion="Vary your language. Get to the point directly.",
                )
            )

        # Check for "I'll try again" or similar circular language
        circular_phrases = [
            r"let me try (another|a different|the same)",
            r"i'll attempt (to|the same)",
            r"trying again",
            r"perhaps i should",
            r"maybe we can",
        ]
        circular_count = sum(1 for p in circular_phrases if re.search(p, response_lower))
        if circular_count >= 3:
            issues.append(
                QualityIssue(
                    issue_type="drift",
                    severity="medium",
                    description="Circular reasoning pattern detected",
                    evidence=[f"{circular_count} attempts to try different approaches"],
                    suggestion="Step back. What problem are you actually solving? Read the full context.",
                )
            )

        return issues

    def _detect_avoidance(
        self,
        response: str,
        tool_calls: List[Dict[str, Any]],
        messages: List[Dict[str, Any]],
    ) -> List[QualityIssue]:
        """Detect if the agent is avoiding required actions."""
        issues: List[QualityIssue] = []

        tool_names = [tc.get("tool", tc.get("function", {}).get("name", "")) for tc in tool_calls]

        # Pattern 1: Task requires reading but agent is guessing
        task_requires_read = False
        response_lower = response.lower()

        # Check if response contains assumptions
        assumption_patterns = [
            r"i assume",
            r"it seems like",
            r"probably",
            r"might be",
            r"could be",
            r"should be",
            r"typically",
        ]
        assumption_count = sum(1 for p in assumption_patterns if re.search(p, response_lower))

        # If many assumptions and no reading
        if assumption_count >= 3 and "repo_read" not in tool_names and "grep" not in tool_names:
            issues.append(
                QualityIssue(
                    issue_type="avoidance",
                    severity="medium",
                    description="Making assumptions without verification",
                    evidence=[f"{assumption_count} assumption phrases detected", "No file reading performed"],
                    suggestion="Read the actual code before making assumptions. Use repo_read or grep.",
                )
            )

        # Pattern 2: Describing code without showing it
        describes_code = bool(re.search(r"(?:function|class|method|variable)\s+\w+", response))
        shows_code = "```" in response or "repo_read" in tool_names

        if describes_code and not shows_code:
            issues.append(
                QualityIssue(
                    issue_type="avoidance",
                    severity="low",
                    description="Describes code without showing actual implementation",
                    evidence=["Mentions code structure but doesn't show it"],
                    suggestion="Show the actual code with repo_read or grep results.",
                )
            )

        # Pattern 3: Answering without understanding the full context
        long_question = any(m.get("role") == "user" and len(m.get("content", "")) > 500 for m in messages)
        if long_question and len(response) < 100 and not tool_calls:
            issues.append(
                QualityIssue(
                    issue_type="avoidance",
                    severity="high",
                    description="Brief response to complex question without investigation",
                    evidence=["Complex question received", "Short response without tools"],
                    suggestion="The question is complex. Use tools to investigate before answering.",
                )
            )

        return issues

    def _detect_overconfidence(
        self,
        response: str,
        tool_calls: List[Dict[str, Any]],
    ) -> List[QualityIssue]:
        """Detect overconfidence relative to verification."""
        issues: List[QualityIssue] = []

        response_lower = response.lower()

        # Strong certainty markers
        certainty_markers = [
            r"\bdefinitely\b",
            r"\babsolutely\b",
            r"\bcertainly\b",
            r"\bclearly\b",
            r"\bobviously\b",
            r"\balways\b",
            r"\bnever\b",
            r"\bimpossible\b",
            r"\bguaranteed\b",
        ]

        certainty_count = sum(1 for p in certainty_markers if re.search(p, response_lower))

        # No verification performed
        verification_tools = ["repo_read", "grep", "shell_run", "repo_list", "glob_files"]
        has_verification = any(v in str(tool_calls) for v in verification_tools)

        if certainty_count >= 3 and not has_verification:
            issues.append(
                QualityIssue(
                    issue_type="overconfidence",
                    severity="medium",
                    description="High certainty without verification",
                    evidence=[f"{certainty_count} certainty markers", "No verification tools used"],
                    suggestion="Verify with repo_read or grep before making absolute statements.",
                )
            )

        # Overly simple solutions to complex problems
        complex_indicators = ["complex", "difficult", "challenging", "multiple", "several issues"]
        simple_solutions = ["simple", "easy", "just do", "just change", "straightforward"]

        has_complex = any(c in response_lower for c in complex_indicators)
        has_simple = any(s in response_lower for s in simple_solutions)

        if has_complex and has_simple:
            issues.append(
                QualityIssue(
                    issue_type="overconfidence",
                    severity="low",
                    description="Dismissed complex problem as simple",
                    evidence=["Problem described as complex", "Solution described as simple/easy"],
                    suggestion="Complex problems often have hidden complexity. Be thorough.",
                )
            )

        return issues

    def _calculate_quality_score(self, issues: List[QualityIssue]) -> float:
        """Calculate overall quality score based on issues."""
        if not issues:
            return 1.0

        severity_weights = {
            "high": 0.3,
            "medium": 0.15,
            "low": 0.05,
        }

        total_penalty = sum(severity_weights.get(i.severity, 0.1) for i in issues)
        return max(0.0, 1.0 - total_penalty)

    def _assess_confidence(self, response: str, issues: List[QualityIssue]) -> str:
        """Assess the confidence level of the response."""
        if any(i.issue_type == "overconfidence" and i.severity == "high" for i in issues):
            return "overconfident"
        if any(i.issue_type == "avoidance" for i in issues):
            return "low"
        if any(i.issue_type == "hallucination" for i in issues):
            return "low"
        return "normal"

    def _generate_feedback(self, issues: List[QualityIssue]) -> str:
        """Generate targeted feedback for the next round."""
        if not issues:
            return ""

        feedback_parts = []

        for issue in sorted(issues, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x.severity]):
            if issue.suggestion:
                feedback_parts.append(f"[{issue.severity.upper()}] {issue.suggestion}")

        if feedback_parts:
            return "\n".join(["[RESPONSE QUALITY CHECK]", *feedback_parts[:3]])

        return ""

    def reset(self) -> None:
        """Reset analysis state for a new task."""
        self._response_history.clear()
        self._tool_call_history.clear()


# Global analyzer instance
_analyzer: Optional[ResponseAnalyzer] = None


def get_analyzer() -> ResponseAnalyzer:
    """Get or create the global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = ResponseAnalyzer()
    return _analyzer


def analyze_response(
    response_text: str,
    tool_calls: List[Dict[str, Any]],
    messages: List[Dict[str, Any]],
    repo_dir: str = "",
) -> ResponseAnalysis:
    """Convenience function to analyze a response."""
    return get_analyzer().analyze(response_text, tool_calls, messages, repo_dir)
