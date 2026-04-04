"""Tool functions for evolution loop.

Extracted from tools/evolution_loop.py (Principle 5: Minimalism).
Handles: autonomous evaluation, evolution cycles, readiness checks, dashboards.
"""

from __future__ import annotations

import logging
import pathlib
from typing import Any, List

from ouroboros.tools.registry import ToolContext

log = logging.getLogger(__name__)


def _autonomous_evaluate(ctx: ToolContext) -> str:
    """Run autonomous self-evaluation with trend analysis."""
    from ouroboros.tools.evolution_loop import EvolutionLoop

    log.info("Running autonomous evaluation...")

    loop = EvolutionLoop(ctx)
    strategy = loop._strategy

    lines = ["## Autonomous Evaluation", ""]

    trend = strategy.get_trend()
    lines.append(f"**Trend:** {trend.get('trend', 'unknown')}")
    if trend.get("total_cycles", 0) > 0:
        lines.append(f"**History:** {trend['total_cycles']} cycles, health={trend.get('recent_health', 0):.0%}")
    if trend.get("recurring_issues"):
        lines.append(f"**Recurring:** {', '.join(trend['recurring_issues'][:3])}")

    issues = loop.identify_issues()
    lines.append(f"\n**Issues Found:** {len(issues)}")

    if issues:
        prioritized = strategy.prioritize_issues(issues)
        for issue, score in prioritized[:5]:
            lines.append(f"- [{score:.2f}] {issue}")

        plans = loop.plan_improvements(issues)
        lines.append(f"\n**Proposed Improvements:**")
        for plan in plans[:3]:
            conf = plan.get("confidence", 0.5)
            conf_level = plan.get("confidence_level", "?")
            lines.append(f"- [{conf:.0%} {conf_level}] **{plan['issue']}**: {plan['approach']}")

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
    from ouroboros.tools.evolution_loop import EvolutionLoop

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

    health = cycle.results.get("health_score")
    if health is not None:
        lines.append(f"**Health Score:** {health:.0%}")
    trend = cycle.results.get("trend", {})
    if trend.get("trend"):
        lines.append(f"**Trend:** {trend['trend']} (delta: {trend.get('health_delta', 0):+.3f})")

    confidence = cycle.results.get("confidence", {})
    if confidence:
        lines.append(f"**Confidence:** {confidence.get('overall', 0):.0%} ({confidence.get('level', 'unknown')})")
        if confidence.get("low_confidence_count", 0) > 0:
            lines.append(f"**Low-confidence plans:** {confidence['low_confidence_count']}")

    lines.append("")
    lines.append("### Results")

    for key, value in cycle.results.items():
        if key in ("trend", "prioritized_issues"):
            continue
        lines.append(f"- **{key}:** {value}")

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

    if trend.get("recurring_issues"):
        lines.append(f"\n### Recurring Issues")
        for ri in trend["recurring_issues"]:
            lines.append(f"- {ri}")

    try:
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
        lines.append(f"OK **{tool}** - {cap}")

    lines.append("\n### Missing Capabilities")
    for tool, cap in missing:
        lines.append(f"MISSING **{tool}** - {cap}")

    readiness = len(available) / len(checks) * 100
    lines.append(f"\n**Readiness:** {readiness:.0f}%")

    if readiness >= 75:
        lines.append("\n**Ready for autonomous evolution!**")
    elif readiness >= 50:
        lines.append("\n**Partially ready.** Some capabilities missing.")
    else:
        lines.append("\n**Not ready.** Significant capabilities missing.")

    return "\n".join(lines)


def _evolution_policy(ctx: ToolContext) -> str:
    """Show current evolution policy and constraints."""
    try:
        from ouroboros.policy import create_default_policy

        policy = create_default_policy()
        lines = [
            "## Evolution Policy",
            "",
            f"**Max module lines:** {policy.max_module_lines}",
            f"**Max function lines:** {policy.max_function_lines}",
            f"**Require docstrings:** {policy.require_docstrings}",
            f"**No secrets:** {policy.no_secrets}",
            f"**No bare except:** {policy.no_bare_except}",
            f"**No print statements:** {policy.no_print_statements}",
        ]
        return "\n".join(lines)
    except Exception as e:
        return f"Policy unavailable: {e}"


def _synthesize_lessons(ctx: ToolContext) -> str:
    """Synthesize lessons from recent cycles into wisdom."""
    vault_dir = ctx.repo_path("vault/journal")
    if not vault_dir.exists():
        return "No journal entries found."

    entries = sorted(vault_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not entries:
        return "No journal entries to synthesize."

    recent = entries[:10]
    themes: dict = {}

    for entry in recent:
        try:
            content = entry.read_text(encoding="utf-8")
            if "**Lesson:**" in content:
                lesson_start = content.find("**Lesson:**")
                lesson_end = content.find("\n", lesson_start + 50)
                lesson = content[lesson_start:lesson_end].strip()
                themes[lesson] = themes.get(lesson, 0) + 1
        except Exception:
            continue

    if not themes:
        return "No explicit lessons found in recent entries."

    lines = ["## Synthesized Lessons", ""]
    sorted_themes = sorted(themes.items(), key=lambda x: x[1], reverse=True)
    for theme, count in sorted_themes[:5]:
        lines.append(f"- [{count}x] {theme}")

    return "\n".join(lines)


def _knowledge_decay_report(ctx: ToolContext) -> str:
    """Generate knowledge decay report."""
    try:
        from ouroboros.knowledge_decay import KnowledgeDecay

        repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
        decay = KnowledgeDecay(repo_dir=repo_dir)
        return decay.get_decay_report()
    except Exception as e:
        return f"Knowledge decay analysis unavailable: {e}"


def _predictive_health(ctx: ToolContext) -> str:
    """Run predictive health analysis."""
    try:
        from ouroboros.health_predictor import HealthPredictor

        repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
        drive_root = pathlib.Path(ctx.drive_root) if ctx.drive_root else pathlib.Path("~/.jo_data")
        predictor = HealthPredictor(repo_dir=repo_dir, drive_root=drive_root)
        return predictor.get_health_report()
    except Exception as e:
        return f"Predictive health unavailable: {e}"


def _confidence_report(ctx: ToolContext) -> str:
    """Generate confidence scoring report."""
    try:
        from ouroboros.tools.evolution_loop import EvolutionLoop

        loop = EvolutionLoop(ctx)
        return loop._scorer.get_confidence_report()
    except Exception as e:
        return f"Confidence report unavailable: {e}"


def _evolution_fingerprint(ctx: ToolContext) -> str:
    """Generate evolution fingerprint."""
    try:
        from ouroboros.evolution_fingerprint import EvolutionFingerprinter

        repo_dir = pathlib.Path(ctx.repo_dir) if ctx.repo_dir else pathlib.Path(".")
        fp = EvolutionFingerprinter(repo_dir=repo_dir)
        return fp.get_fingerprint_report()
    except Exception as e:
        return f"Evolution fingerprint unavailable: {e}"


def _decision_trace_report(ctx: ToolContext) -> str:
    """Generate decision trace report."""
    try:
        from ouroboros.decision_trace import DecisionTracer

        tracer = DecisionTracer()
        return tracer.get_decision_report()
    except Exception as e:
        return f"Decision trace unavailable: {e}"


def _system_dashboard(ctx: ToolContext) -> str:
    """Generate comprehensive system dashboard."""
    lines = ["# System Dashboard", ""]

    sections = [
        ("Evolution Status", _get_evolution_status),
        ("Knowledge Decay", _knowledge_decay_report),
        ("Predictive Health", _predictive_health),
        ("Confidence", _confidence_report),
        ("Evolution Fingerprint", _evolution_fingerprint),
        ("Decision Trace", _decision_trace_report),
    ]

    for title, func in sections:
        try:
            result = func(ctx)
            if result and not result.startswith(("Unavailable", "Error")):
                lines.append(f"\n## {title}\n")
                lines.append(result)
        except Exception as e:
            lines.append(f"\n## {title}\n")
            lines.append(f"Error: {e}")

    return "\n".join(lines)


def _enable_evolution_mode(ctx: ToolContext) -> str:
    """Enable autonomous evolution mode."""
    try:
        from supervisor.state import load_state, save_state

        state = load_state()
        state["evolution_mode"] = True
        save_state(state)
        return "Evolution mode enabled. The agent will now run autonomous improvement cycles."
    except Exception as e:
        return f"Failed to enable evolution mode: {e}"


def _get_evolution_status(ctx: ToolContext) -> str:
    """Get current evolution status."""
    try:
        from supervisor.state import load_state

        state = load_state()
        mode = state.get("evolution_mode", False)
        cycle = state.get("evolution_cycle", 0)
        history = state.get("evolution_history", [])
        failures = state.get("evolution_consecutive_failures", 0)

        lines = [
            f"**Mode:** {'Active' if mode else 'Inactive'}",
            f"**Cycle:** {cycle}",
            f"**History:** {len(history)} entries",
            f"**Consecutive Failures:** {failures}",
        ]

        if history:
            recent = history[0]
            lines.append(f"\n**Last Cycle:** {recent.get('task_id', 'unknown')}")
            lines.append(f"**Success:** {recent.get('success', False)}")
            lines.append(f"**Commits:** {recent.get('commits', 0)}")

        return "\n".join(lines)
    except Exception as e:
        return f"Status unavailable: {e}"
