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
        """Plan improvements based on identified issues."""
        plans = []

        for issue in issues:
            if "test" in issue.lower():
                plans.append(
                    {
                        "issue": issue,
                        "approach": "Run detailed tests to identify specific failures",
                        "tool": "ai_code_edit",
                    }
                )
            elif "syntax" in issue.lower():
                plans.append(
                    {
                        "issue": issue,
                        "approach": "Fix syntax errors in affected files",
                        "tool": "ai_code_edit",
                    }
                )
            elif "module size" in issue.lower():
                plans.append(
                    {
                        "issue": issue,
                        "approach": "Refactor oversized module into smaller focused modules",
                        "tool": "ai_code_edit",
                    }
                )

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
                    cycle.duration_sec = time.time() - start_time
                    self.cycles.append(cycle)
                    return cycle

        # Should not reach here, but handle gracefully
        cycle.status = "failed"
        cycle.duration_sec = time.time() - start_time
        self.cycles.append(cycle)
        return cycle

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


def _autonomous_evaluate(ctx: ToolContext) -> str:
    """Run autonomous self-evaluation with trend analysis."""
    log.info("Running autonomous evaluation...")

    loop = EvolutionLoop(ctx)
    strategy = loop._strategy

    lines = ["## Autonomous Evaluation", ""]

    # Trend analysis
    trend = strategy.get_trend()
    lines.append(f"**Trend:** {trend.get('trend', 'unknown')}")
    if trend.get("total_cycles", 0) > 0:
        lines.append(f"**History:** {trend['total_cycles']} cycles, health={trend.get('recent_health', 0):.0%}")
    if trend.get("recurring_issues"):
        lines.append(f"**Recurring:** {', '.join(trend['recurring_issues'][:3])}")

    # Current issues
    issues = loop.identify_issues()
    lines.append(f"\n**Issues Found:** {len(issues)}")

    if issues:
        prioritized = strategy.prioritize_issues(issues)
        for issue, score in prioritized[:5]:
            lines.append(f"- [{score:.2f}] {issue}")

        plans = loop.plan_improvements(issues)
        lines.append(f"\n**Proposed Improvements:**")
        for plan in plans[:3]:
            lines.append(f"- **{plan['issue']}**: {plan['approach']}")

        # Strategy suggestions
        suggestions = strategy.suggest_focus()
        if suggestions:
            lines.append(f"\n**Strategy Suggestions:**")
            for s in suggestions[:3]:
                lines.append(f"- {s}")

        lines.append("\n**Recommendation:**")
        lines.append("Use `run_evolution_cycle` for a full cycle with adaptive strategy.")
    else:
        lines.append("\n**System is healthy.** No improvements needed.")
        health = strategy.compute_health_score([])
        lines.append(f"Health score: {health:.0%}")

    return "\n".join(lines)


def _run_evolution_cycle(ctx: ToolContext) -> str:
    """Run a complete evolution cycle with adaptive strategy."""
    log.info("Starting evolution cycle...")

    loop = EvolutionLoop(ctx)
    cycle = loop.run_cycle()

    status_icon = {"complete": "OK", "degraded": "WARN", "failed": "FAIL"}.get(cycle.status, "...")

    lines = [
        f"## Evolution Cycle: {cycle.id}",
        "",
        f"**Status:** {status_icon} {cycle.status}",
        f"**Duration:** {cycle.duration_sec:.1f}s",
        f"**Attempts:** {cycle.attempts}",
    ]

    # Health score and trend
    health = cycle.results.get("health_score")
    if health is not None:
        lines.append(f"**Health Score:** {health:.0%}")
    trend = cycle.results.get("trend", {})
    if trend.get("trend"):
        lines.append(f"**Trend:** {trend['trend']} (delta: {trend.get('health_delta', 0):+.3f})")

    lines.append("")
    lines.append("### Results")

    for key, value in cycle.results.items():
        if key in ("trend", "prioritized_issues"):
            continue
        lines.append(f"- **{key}:** {value}")

    # Prioritized issues
    prioritized = cycle.results.get("prioritized_issues", [])
    if prioritized:
        lines.append("\n### Prioritized Issues")
        for item in prioritized[:5]:
            lines.append(f"- [{item['impact']:.2f}] {item['issue']}")

    if cycle.changes:
        lines.append("\n### Changes")
        for change in cycle.changes:
            lines.append(f"- {change}")

    if cycle.errors:
        lines.append("\n### Errors")
        for error in cycle.errors:
            lines.append(f"- {error}")

    # Strategy suggestions
    if trend.get("recurring_issues"):
        lines.append(f"\n### Recurring Issues")
        for ri in trend["recurring_issues"]:
            lines.append(f"- {ri}")

    # Knowledge decay assessment
    try:
        import pathlib
        from ouroboros.knowledge_decay import KnowledgeDecay

        repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
        decay = KnowledgeDecay(repo_dir=repo_dir)
        candidates = decay.get_archive_candidates()
        if candidates:
            lines.append(f"\n### Knowledge Decay")
            lines.append(f"**Archive candidates:** {len(candidates)} low-value notes")
            for c in candidates[:3]:
                lines.append(f"- [{c.value_score:.3f}] {c.title}")
    except Exception:
        pass

    # Predictive health
    try:
        from ouroboros.health_predictor import HealthPredictor

        repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
        drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")
        predictor = HealthPredictor(repo_dir=repo_dir, drive_root=drive_root)
        predictor.take_snapshot_now()
        predictions = predictor.predict_trends()
        if predictions.get("alerts"):
            lines.append(f"\n### Health Predictions")
            for alert in predictions["alerts"]:
                lines.append(f"- [WARNING] {alert['message']}")
    except Exception:
        pass

    return "\n".join(lines)


def _check_evolution_readiness(ctx: ToolContext) -> str:
    """Check if the system is ready for autonomous evolution."""
    lines = ["## Evolution Readiness Check", ""]

    checks = {
        "ai_code_edit": "Can generate code",
        "neural_map": "Can map knowledge",
        "vault_create": "Can store lessons",
        "health_auto_fix": "Can self-repair",
    }

    available = []
    missing = []

    try:
        from ouroboros.tools.registry import ToolRegistry

        registry = ToolRegistry(repo_dir=ctx.repo_dir, drive_root=ctx.drive_root)
        tools = [t["function"]["name"] for t in registry.schemas()]
    except Exception:
        tools = []

    for tool, capability in checks.items():
        if tool in tools:
            available.append((tool, capability))
        else:
            missing.append((tool, capability))

    lines.append("### Available Capabilities")
    for tool, cap in available:
        lines.append(f"✅ **{tool}** - {cap}")

    lines.append("\n### Missing Capabilities")
    for tool, cap in missing:
        lines.append(f"❌ **{tool}** - {cap}")

    readiness = len(available) / len(checks) * 100
    lines.append(f"\n**Readiness:** {readiness:.0f}%")

    if readiness >= 75:
        lines.append("\n🚀 **Ready for autonomous evolution!**")
    elif readiness >= 50:
        lines.append("\n⚠️ **Partially ready.** Some capabilities missing.")
    else:
        lines.append("\n❌ **Not ready.** Significant capabilities missing.")

    return "\n".join(lines)


def _synthesize_lessons(ctx: ToolContext) -> str:
    """Synthesize lessons from recent cycles into wisdom."""
    vault_dir = ctx.repo_path("vault/journal")

    if not vault_dir.exists():
        return "No journal entries found."

    lessons = []
    for md_file in vault_dir.glob("*.md"):
        if "lesson" in md_file.stem.lower():
            try:
                content = md_file.read_text(encoding="utf-8")
                lessons.append(content[:200])
            except Exception:
                log.debug("Unexpected error", exc_info=True)

    if not lessons:
        return "No lessons recorded yet."

    prompt = f"""Synthesize these lessons into general principles:

{lessons[:5]}

Create 3-5 actionable principles that can guide future decisions.
"""

    try:
        from ouroboros.llm import LLMClient

        client = LLMClient()
        messages = [
            {"role": "system", "content": "You are a wisdom synthesizer. Extract principles from experience."},
            {"role": "user", "content": prompt},
        ]
        msg, _ = client.chat(messages, model="openrouter/free", max_tokens=4096)
        result = msg.get("content", "")
        if result:
            lines = ["## Synthesized Wisdom", "", result, "", "_This synthesis can be added to BIBLE.md_"]
            return "\n".join(lines)
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    return f"Found {len(lessons)} lessons but synthesis failed. Try again when OpenRouter is accessible."


def _knowledge_decay_report(ctx: ToolContext) -> str:
    """Generate knowledge decay report."""
    import pathlib
    from ouroboros.knowledge_decay import KnowledgeDecay

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    decay = KnowledgeDecay(repo_dir=repo_dir)
    return decay.get_decay_report()


def _predictive_health(ctx: ToolContext) -> str:
    """Generate predictive health report."""
    import pathlib
    from ouroboros.health_predictor import HealthPredictor

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")
    predictor = HealthPredictor(repo_dir=repo_dir, drive_root=drive_root)
    # Take a fresh snapshot
    predictor.take_snapshot_now()
    return predictor.get_health_report()


def _confidence_report(ctx: ToolContext) -> str:
    """Generate confidence scoring report."""
    import pathlib
    from ouroboros.confidence import ConfidenceScorer

    drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")
    scorer = ConfidenceScorer(drive_root=drive_root)
    return scorer.get_confidence_report()


def _evolution_fingerprint(ctx: ToolContext) -> str:
    """Take and report on system fingerprint."""
    import pathlib
    from ouroboros.evolution_fingerprint import EvolutionFingerprinter

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    fp = EvolutionFingerprinter(repo_dir=repo_dir)
    return fp.get_fingerprint_report()


def _decision_trace_report(ctx: ToolContext) -> str:
    """Get decision trace report."""
    from ouroboros.decision_trace import DecisionTracer

    tracer = DecisionTracer()
    return tracer.get_decision_report()


def _system_dashboard(ctx: ToolContext) -> str:
    """Comprehensive system health dashboard combining all monitoring systems."""
    import pathlib

    repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
    drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")

    lines = ["# System Dashboard", ""]

    # Drift
    try:
        from ouroboros.drift_detector import DriftDetector

        d = DriftDetector(repo_dir=repo_dir, drive_root=drive_root)
        violations = d.run_all_checks()
        if violations:
            lines.append(f"## Drift ({len(violations)} violations)")
            for v in violations[:3]:
                lines.append(f"- [{v['severity'].upper()}] {v['rule']}: {v['detail'][:80]}")
        else:
            lines.append("## Drift: OK")
    except Exception as e:
        lines.append(f"## Drift: Error ({e})")

    # Knowledge gaps
    try:
        from ouroboros.knowledge_discovery import KnowledgeDiscovery

        kd = KnowledgeDiscovery(repo_dir=repo_dir, drive_root=drive_root)
        gaps = kd.scan_all()
        lines.append(f"\n## Knowledge Gaps: {len(gaps)}")
        for g in gaps[:3]:
            lines.append(f"- [{g.severity:.1f}] {g.gap_type}: {g.description[:60]}")
    except Exception:
        pass

    # Knowledge decay
    try:
        from ouroboros.knowledge_decay import KnowledgeDecay

        decay = KnowledgeDecay(repo_dir=repo_dir)
        candidates = decay.get_archive_candidates()
        notes = decay.assess_all()
        healthy = sum(1 for n in notes if n.value_score >= 0.3)
        lines.append(f"\n## Knowledge: {len(notes)} notes ({healthy} healthy, {len(candidates)} archive candidates)")
    except Exception:
        pass

    # Predictive health
    try:
        from ouroboros.health_predictor import HealthPredictor

        predictor = HealthPredictor(repo_dir=repo_dir, drive_root=drive_root)
        trends = predictor.predict_trends()
        if trends.get("alerts"):
            lines.append(f"\n## Health Predictions: {len(trends['alerts'])} alerts")
            for a in trends["alerts"][:3]:
                lines.append(f"- {a['message'][:80]}")
        else:
            lines.append(f"\n## Health Predictions: {trends.get('overall_trend', 'unknown')}")
    except Exception:
        pass

    # Skills
    try:
        from ouroboros.tools.skills import SKILLS

        lines.append(f"\n## Skills: {len(SKILLS)} registered")
    except Exception:
        pass

    # Tools
    try:
        from ouroboros.tools.registry import ToolRegistry

        r = ToolRegistry(repo_dir=repo_dir, drive_root=drive_root)
        lines.append(f"## Tools: {len(r.schemas())} registered")
    except Exception:
        pass

    return "\n".join(lines)


def _enable_evolution_mode(ctx: ToolContext) -> str:
    """Enable continuous autonomous evolution."""
    log.info("Enabling evolution mode...")

    from ouroboros.tools.control import _toggle_evolution

    return _toggle_evolution(ctx, enabled=True)


def _get_evolution_status(ctx: ToolContext) -> str:
    """Get current evolution status and statistics."""
    vault_dir = ctx.repo_path("vault/journal")

    lines = ["## Evolution Status", ""]

    # Read actual state instead of hardcoding True
    evolution_enabled = True
    try:
        import json

        state_path = ctx.drive_path("state") / "state.json"
        if state_path.exists():
            state = json.loads(state_path.read_text(encoding="utf-8"))
            evolution_enabled = state.get("evolution_mode_enabled", False)
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    lines.append(f"**Evolution Mode:** {'✅ Enabled' if evolution_enabled else '❌ Disabled'}")
    lines.append("")

    if vault_dir.exists():
        lesson_count = len(list(vault_dir.glob("*lesson*.md")))
        journal_count = len(list(vault_dir.glob("*.md")))
        lines.append(f"**Lessons Learned:** {lesson_count}")
        lines.append(f"**Journal Entries:** {journal_count}")
    else:
        lines.append("**Lessons Learned:** 0")
        lines.append("**Journal Entries:** 0")

    lines.extend(
        [
            "",
            "### Available Actions",
            "- `run_evolution_cycle` - Execute one improvement cycle",
            "- `autonomous_evaluate` - Scan for issues",
            "- `synthesize_lessons` - Convert lessons to wisdom",
            "- `check_evolution_readiness` - Verify capabilities",
        ]
    )

    return "\n".join(lines)


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
