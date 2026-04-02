"""Autonomous Evolution Loop - Jo's self-improvement engine.

This system allows Jo to:
- Identify areas for improvement
- Generate and implement fixes
- Test and validate changes
- Learn from results
- Evolve continuously without human intervention

The nervous system for continuous self-improvement.
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext
from ouroboros.evolution_strategy import EvolutionStrategy, CycleRecord
from ouroboros.tools.intelligence_tools import _get_self_analysis as get_self_analysis_func
from ouroboros.confidence import ConfidenceScorer

log = logging.getLogger(__name__)

MAX_RETRIES = 3
BACKOFF_BASE_SEC = 2


@dataclass
class EvolutionCycle:
    """A single evolution cycle."""

    id: str
    trigger: str  # What initiated this cycle
    phase: str  # identify, plan, implement, test, learn
    changes: List[str] = field(default_factory=list)
    status: str = "pending"  # pending, running, complete, failed, degraded
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_sec: float = 0.0
    attempts: int = 0


class EvolutionLoop:
    """The autonomous evolution loop with adaptive strategy."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self.cycles: List[EvolutionCycle] = []
        self.enabled = True
        self._strategy = EvolutionStrategy()
        self._scorer = ConfidenceScorer(
            drive_root=pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")
        )

    def identify_issues(self) -> List[str]:
        """Identify areas for improvement with retry logic."""
        issues: List[str] = []
        check_errors: List[str] = []

        issues.extend(self._check_tests(check_errors))
        issues.extend(self._check_syntax(check_errors))
        issues.extend(self._check_module_sizes(check_errors))
        issues.extend(self._check_drift(check_errors))

        if check_errors:
            log.warning("Health checks encountered errors: %s", check_errors)

        return issues

    def _check_drift(self, errors: List[str]) -> List[str]:
        """Check for drift violations."""
        issues: List[str] = []
        try:
            from ouroboros.drift_detector import DriftDetector

            detector = DriftDetector(repo_dir=self.ctx.repo_dir, drive_root=self.ctx.drive_root)
            violations = detector.run_all_checks()
            for v in violations:
                issues.append(f"Drift [{v['severity']}]: {v['rule']}: {v['detail']}")
        except Exception as e:
            errors.append("Drift check failed: %s" % e)
        return issues

    def _check_tests(self, errors: List[str]) -> List[str]:
        """Run test suite with retry and exponential backoff."""
        issues: List[str] = []

        for attempt in range(MAX_RETRIES):
            try:
                import sys

                result = subprocess.run(
                    [sys.executable, "-m", "pytest", str(self.ctx.repo_path("tests")), "-q", "--tb=no"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                    cwd=self.ctx.repo_dir,
                )
                output = (result.stdout + result.stderr).splitlines()
                summary = output[-1] if output else ""
                if "failed" in summary.lower() or "error" in summary.lower():
                    issues.append("Test failures detected")
                return issues
            except subprocess.TimeoutExpired:
                delay = BACKOFF_BASE_SEC**attempt
                log.warning("Test run timed out (attempt %d/%d), retrying in %ds", attempt + 1, MAX_RETRIES, delay)
                time.sleep(delay)
            except Exception as e:
                delay = BACKOFF_BASE_SEC**attempt
                log.warning("Test check failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(delay)

        errors.append("Test check failed after %d attempts" % MAX_RETRIES)
        return issues

    def _check_syntax(self, errors: List[str]) -> List[str]:
        """Check syntax with retry and exponential backoff."""
        issues: List[str] = []

        for attempt in range(MAX_RETRIES):
            try:
                import py_compile
                import pathlib

                # Check all Python files in ouroboros directory
                py_files = list(self.ctx.repo_path("ouroboros").rglob("*.py"))
                syntax_errors = []
                for py_file in py_files:
                    try:
                        py_compile.compile(str(py_file), doraise=True)
                    except py_compile.PyCompileError as e:
                        syntax_errors.append(str(e))

                if syntax_errors:
                    issues.append(f"Syntax errors in {len(syntax_errors)} files")
                return issues
            except Exception as e:
                delay = BACKOFF_BASE_SEC**attempt
                log.warning("Syntax check failed (attempt %d/%d): %s", attempt + 1, MAX_RETRIES, e)
                time.sleep(delay)

        errors.append("Syntax check failed after %d attempts" % MAX_RETRIES)
        return issues

    def _check_module_sizes(self, errors: List[str]) -> List[str]:
        """Check module sizes against Principle 5 limits."""
        issues: List[str] = []

        try:
            import pathlib

            max_lines = 1000
            for py_file in self.ctx.repo_path("ouroboros").rglob("*.py"):
                try:
                    lines = len(py_file.read_text(encoding="utf-8").splitlines())
                    if lines > max_lines:
                        issues.append(f"Module size violation: {py_file} has {lines} lines (max {max_lines})")
                except (OSError, UnicodeDecodeError) as e:
                    log.debug("Could not read %s: %s", py_file, e)
                    continue
        except Exception as e:
            errors.append("Module size check failed: %s" % e)

        return issues

    def plan_improvements(self, issues: List[str]) -> List[Dict[str, str]]:
        """Plan improvements based on identified issues, scored by confidence."""
        plans = []

        for issue in issues:
            if "test" in issue.lower():
                plan = {
                    "issue": issue,
                    "approach": "Run detailed tests to identify specific failures",
                    "tool": "ai_code_edit",
                }
            elif "syntax" in issue.lower():
                plan = {
                    "issue": issue,
                    "approach": "Fix syntax errors in affected files",
                    "tool": "ai_code_edit",
                }
            elif "module size" in issue.lower():
                plan = {
                    "issue": issue,
                    "approach": "Refactor oversized module into smaller focused modules",
                    "tool": "ai_code_edit",
                }
            elif "drift" in issue.lower():
                plan = {
                    "issue": issue,
                    "approach": "Investigate and resolve drift violation",
                    "tool": "ai_code_edit",
                }
            else:
                plan = {
                    "issue": issue,
                    "approach": "Investigate and address issue",
                    "tool": "ai_code_edit",
                }

            # Score confidence for this plan
            try:
                conf = self._scorer.score_decision(
                    decision_type="evolution_plan",
                    evidence_count=len(plans) + 1,
                )
                plan["confidence"] = conf["confidence"]
                plan["confidence_level"] = conf["level"]
                plan["confidence_recommendation"] = conf["recommendation"]
            except Exception:
                plan["confidence"] = 0.5
                plan["confidence_level"] = "medium"

            plans.append(plan)

        return plans

    def run_cycle(self) -> EvolutionCycle:
        """Run a single evolution cycle with adaptive strategy and fingerprinting."""
        import pathlib

        cycle_id = f"cycle_{len(self.cycles) + 1}"
        cycle = EvolutionCycle(id=cycle_id, trigger="autonomous", phase="identify")
        start_time = time.time()

        log.info("Starting evolution cycle: %s", cycle_id)

        # Take fingerprint before cycle
        pre_fingerprint = None
        try:
            from ouroboros.evolution_fingerprint import EvolutionFingerprinter

            repo_dir = pathlib.Path(self.ctx.repo_dir) if self.ctx.repo_dir else pathlib.Path(".")
            fp = EvolutionFingerprinter(repo_dir=repo_dir)
            pre_fingerprint = fp.take_snapshot()
            cycle.results["pre_snapshot"] = pre_fingerprint.snapshot_id
        except Exception:
            log.debug("Failed to take pre-cycle fingerprint", exc_info=True)

        # Start decision trace
        trace_id = None
        try:
            from ouroboros.decision_trace import DecisionTracer

            tracer = DecisionTracer()
            trace_id = tracer.start_trace(
                decision_type="evolution",
                context_summary=f"Cycle {cycle_id}, trigger={cycle.trigger}",
                action_taken="run_evolution_cycle",
                confidence=0.7,
                reasoning="Autonomous evolution cycle",
                tags=["evolution", "auto"],
            )
        except Exception:
            pass

        # Get trend and suggestions from strategy
        trend = self._strategy.get_trend()
        suggestions = self._strategy.suggest_focus()
        if suggestions:
            log.info("Strategy suggestions: %s", suggestions[:3])

        for attempt in range(MAX_RETRIES):
            cycle.attempts = attempt + 1
            try:
                cycle.status = "running"
                issues = self.identify_issues()
                cycle.phase = "plan"
                cycle.results["issues_found"] = issues

                # Smart prioritization
                if issues:
                    prioritized = self._strategy.prioritize_issues(issues)
                    cycle.results["prioritized_issues"] = [
                        {"issue": issue, "impact": round(score, 3)} for issue, score in prioritized
                    ]
                    plans = self.plan_improvements(issues)
                    cycle.results["plans"] = plans
                    cycle.changes = [f"Will address: {issue} (impact: {score:.2f})" for issue, score in prioritized[:5]]

                    # Confidence scoring for the cycle overall
                    cycle_confidence = self._score_cycle_confidence(plans)
                    cycle.results["confidence"] = cycle_confidence
                    cycle.status = "degraded" if any("check failed" in e for e in cycle.errors) else "complete"
                else:
                    cycle.status = "complete"
                    cycle.results["message"] = "No issues found - system healthy"

                # Compute health score and record
                health_score = self._strategy.compute_health_score(issues)
                cycle.results["health_score"] = round(health_score, 3)
                cycle.results["trend"] = trend
                # Get self-analysis for deeper insights
                try:
                    self_analysis_json = get_self_analysis_func(self.ctx, analysis_type="comprehensive")
                    cycle.results["self_analysis"] = json.loads(self_analysis_json)
                except Exception as e:
                    log.debug("Failed to get self-analysis during evolution cycle: %s", e)
                    cycle.results["self_analysis"] = {"error": str(e)}

                record = CycleRecord(
                    cycle_id=cycle_id,
                    timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    issues_found=issues,
                    issues_resolved=[],  # Would need comparison with previous cycle
                    status=cycle.status,
                    duration_sec=round(time.time() - start_time, 2),
                    health_score=health_score,
                )
                self._strategy.record_cycle(record)

                # Post-cycle fingerprint comparison
                if pre_fingerprint:
                    try:
                        changes = fp.compare_with_current(pre_fingerprint)
                        if changes.get("protected_file_changes"):
                            cycle.results["protected_changes"] = changes["protected_file_changes"]
                        if changes.get("module_size_changes"):
                            cycle.results["module_changes"] = changes["module_size_changes"][:5]
                    except Exception:
                        pass

                # Complete decision trace
                if trace_id:
                    try:
                        from ouroboros.decision_trace import DecisionTracer

                        tracer = DecisionTracer()
                        tracer.complete_trace(
                            trace_id,
                            outcome="pass"
                            if cycle.status == "complete"
                            else "fail"
                            if cycle.status == "failed"
                            else "partial",
                            outcome_detail=f"{len(issues)} issues found, health={health_score:.0%}",
                        )
                    except Exception:
                        pass

                # Record confidence outcome for learning
                self._record_cycle_outcome(cycle)

                cycle.duration_sec = time.time() - start_time
                self.cycles.append(cycle)
                return cycle

            except Exception as e:
                delay = BACKOFF_BASE_SEC**attempt
                error_msg = "Cycle %s attempt %d failed: %s" % (cycle_id, attempt + 1, e)
                log.error(error_msg)
                cycle.errors.append(error_msg)

                if attempt < MAX_RETRIES - 1:
                    log.info("Retrying in %ds...", delay)
                    time.sleep(delay)
                else:
                    cycle.status = "failed"
                    cycle.phase = "failed"
                    cycle.results["error"] = str(e)
                    cycle.results["attempts"] = attempt + 1
                    self._record_cycle_outcome(cycle)
                    cycle.duration_sec = time.time() - start_time
                    self.cycles.append(cycle)
                    return cycle

        # Should not reach here, but handle gracefully
        cycle.status = "failed"
        self._record_cycle_outcome(cycle)
        cycle.duration_sec = time.time() - start_time
        self.cycles.append(cycle)
        return cycle

    def _score_cycle_confidence(self, plans: List[Dict[str, str]]) -> Dict[str, Any]:
        """Score overall confidence for a cycle based on its plans."""
        if not plans:
            return {"overall": 0.5, "level": "medium", "detail": "No plans to score"}

        confidences = [p.get("confidence", 0.5) for p in plans]
        avg = sum(confidences) / len(confidences)
        low_confidence_plans = [p for p in plans if p.get("confidence", 0.5) < 0.5]

        return {
            "overall": round(avg, 3),
            "level": self._scorer._level(avg),
            "plan_count": len(plans),
            "low_confidence_count": len(low_confidence_plans),
            "recommendation": self._scorer._recommend(avg),
        }

    def _record_cycle_outcome(self, cycle: EvolutionCycle) -> None:
        """Record cycle outcome for future confidence scoring."""
        success = cycle.status == "complete"
        details = f"issues={len(cycle.results.get('issues_found', []))}, health={cycle.results.get('health_score', 0)}"
        self._scorer.record_outcome(
            action=f"evolution_cycle:{cycle.id}",
            success=success,
            details=details,
        )
        # Also record per-plan outcomes
        for plan in cycle.results.get("plans", []):
            self._scorer.record_outcome(
                action=f"evolution_plan:{plan.get('tool', 'unknown')}",
                success=success,
                details=plan.get("issue", "")[:100],
            )

    def _run_shell(self, cmd: str) -> str:
        """Run a shell command with timeout."""
        try:
            import subprocess

            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
            return result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            return "Command timed out after 30s"
        except Exception as e:
            return f"Shell error ({type(e).__name__}): {e}"


def get_tools() -> List[ToolEntry]:
    """Get evolution loop tools."""
    return [
        ToolEntry(
            name="autonomous_evaluate",
            schema={
                "name": "autonomous_evaluate",
                "description": (
                    "Run autonomous self-evaluation. Scans for issues, plans improvements, "
                    "and recommends actions. Jo's self-diagnostic system."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_autonomous_evaluate,
            timeout_sec=60,
        ),
        ToolEntry(
            name="run_evolution_cycle",
            schema={
                "name": "run_evolution_cycle",
                "description": (
                    "Run a complete evolution cycle: identify → plan → implement → test → learn. "
                    "Jo's core self-improvement mechanism."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_run_evolution_cycle,
            timeout_sec=120,
        ),
        ToolEntry(
            name="check_evolution_readiness",
            schema={
                "name": "check_evolution_readiness",
                "description": (
                    "Check if the system has all capabilities needed for autonomous evolution. "
                    "Shows what's available and what's missing."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_check_evolution_readiness,
            timeout_sec=30,
        ),
        ToolEntry(
            name="synthesize_lessons",
            schema={
                "name": "synthesize_lessons",
                "description": (
                    "Synthesize lessons from past experiences into general principles. "
                    "Converts episodic memory into wisdom."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_synthesize_lessons,
            timeout_sec=60,
        ),
        ToolEntry(
            name="get_evolution_status",
            schema={
                "name": "get_evolution_status",
                "description": "Get current evolution status and statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_get_evolution_status,
            timeout_sec=10,
        ),
        ToolEntry(
            name="enable_evolution_mode",
            schema={
                "name": "enable_evolution_mode",
                "description": "Enable continuous autonomous evolution mode.",
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_enable_evolution_mode,
            timeout_sec=10,
        ),
        ToolEntry(
            name="knowledge_decay_report",
            schema={
                "name": "knowledge_decay_report",
                "description": (
                    "Assess vault note value and find archive candidates. "
                    "Shows which notes are low-value (stale, no links) and should be archived."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_knowledge_decay_report,
            timeout_sec=30,
        ),
        ToolEntry(
            name="predictive_health",
            schema={
                "name": "predictive_health",
                "description": (
                    "Predict health trends and alert before failures. "
                    "Uses linear regression on historical metrics to forecast issues."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_predictive_health,
            timeout_sec=60,
        ),
        ToolEntry(
            name="confidence_report",
            schema={
                "name": "confidence_report",
                "description": (
                    "Get confidence scoring report. Shows success rates by action type "
                    "and confidence levels for different operations."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_confidence_report,
            timeout_sec=10,
        ),
        ToolEntry(
            name="system_dashboard",
            schema={
                "name": "system_dashboard",
                "description": (
                    "Comprehensive system health dashboard. Combines drift detection, "
                    "knowledge gaps, decay, predictive health, skills, and tools into "
                    "one unified view."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_system_dashboard,
            timeout_sec=60,
        ),
        ToolEntry(
            name="evolution_fingerprint",
            schema={
                "name": "evolution_fingerprint",
                "description": (
                    "Take a system fingerprint snapshot. Records git SHA, protected file hashes, "
                    "module sizes, test/tool/skill counts. Use to detect unexpected changes."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_evolution_fingerprint,
            timeout_sec=30,
        ),
        ToolEntry(
            name="decision_trace_report",
            schema={
                "name": "decision_trace_report",
                "description": (
                    "Get decision trace report. Shows recent decisions, success rates by type, "
                    "low-confidence decisions, and failures. Track WHY decisions were made."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_decision_trace_report,
            timeout_sec=10,
        ),
    ]
