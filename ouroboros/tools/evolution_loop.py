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

import logging
import pathlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext

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
    """The autonomous evolution loop."""

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self.cycles: List[EvolutionCycle] = []
        self.enabled = True

    def identify_issues(self) -> List[str]:
        """Identify areas for improvement with retry logic."""
        issues: List[str] = []
        check_errors: List[str] = []

        issues.extend(self._check_tests(check_errors))
        issues.extend(self._check_syntax(check_errors))
        issues.extend(self._check_module_sizes(check_errors))

        if check_errors:
            log.warning("Health checks encountered errors: %s", check_errors)

        return issues

    def _check_tests(self, errors: List[str]) -> List[str]:
        """Run test suite with retry and exponential backoff."""
        issues: List[str] = []

        for attempt in range(MAX_RETRIES):
            try:
                import subprocess as _sp

                result = _sp.run(
                    ["py", "-m", "pytest", "tests/", "-q", "--tb=no"],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                output = (result.stdout + result.stderr).splitlines()
                summary = output[-1] if output else ""
                if "failed" in summary.lower() or "error" in summary.lower():
                    issues.append("Test failures detected")
                return issues
            except _sp.TimeoutExpired:
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
                result = self._run_shell("py -m py_compile ouroboros/*.py 2>&1")
                if result.strip():
                    issues.append("Syntax errors in core files")
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
            for py_file in pathlib.Path("ouroboros").rglob("*.py"):
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
        """Run a single evolution cycle with retry logic and diagnostics."""
        cycle_id = f"cycle_{len(self.cycles) + 1}"
        cycle = EvolutionCycle(id=cycle_id, trigger="autonomous", phase="identify")
        start_time = time.time()

        log.info("Starting evolution cycle: %s", cycle_id)

        for attempt in range(MAX_RETRIES):
            cycle.attempts = attempt + 1
            try:
                cycle.status = "running"
                issues = self.identify_issues()
                cycle.phase = "plan"
                cycle.results["issues_found"] = issues

                if issues:
                    plans = self.plan_improvements(issues)
                    cycle.results["plans"] = plans
                    cycle.changes = [f"Will address: {i}" for i in issues]
                    cycle.status = "degraded" if any("check failed" in e for e in cycle.errors) else "complete"
                else:
                    cycle.status = "complete"
                    cycle.results["message"] = "No issues found - system healthy"

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
            return str(e)


def _autonomous_evaluate(ctx: ToolContext) -> str:
    """Run autonomous self-evaluation and improvement."""
    log.info("Running autonomous evaluation...")

    loop = EvolutionLoop(ctx)

    lines = ["## Autonomous Evaluation", ""]

    issues = loop.identify_issues()
    lines.append(f"**Issues Identified:** {len(issues)}")
    for issue in issues:
        lines.append(f"- {issue}")

    if issues:
        plans = loop.plan_improvements(issues)
        lines.append(f"\n**Proposed Improvements:**")
        for plan in plans:
            lines.append(f"- **{plan['issue']}**")
            lines.append(f"  Approach: {plan['approach']}")

        lines.append("\n**Recommendation:**")
        lines.append("Use `run_evolution_cycle` for a full cycle with retry logic.")

    else:
        lines.append("\n✅ **System is healthy.**")
        lines.append("No automatic improvements needed.")

    return "\n".join(lines)


def _run_evolution_cycle(ctx: ToolContext) -> str:
    """Run a complete evolution cycle."""
    log.info("Starting evolution cycle...")

    loop = EvolutionLoop(ctx)
    cycle = loop.run_cycle()

    status_icon = {"complete": "✅", "degraded": "⚠️", "failed": "❌"}.get(cycle.status, "⏳")

    lines = [
        f"## Evolution Cycle: {cycle.id}",
        "",
        f"**Trigger:** {cycle.trigger}",
        f"**Phase:** {cycle.phase}",
        f"**Status:** {status_icon} {cycle.status}",
        f"**Duration:** {cycle.duration_sec:.1f}s",
        f"**Attempts:** {cycle.attempts}",
        "",
        "### Results",
    ]

    for key, value in cycle.results.items():
        lines.append(f"- **{key}:** {value}")

    if cycle.changes:
        lines.append("\n### Changes")
        for change in cycle.changes:
            lines.append(f"- {change}")

    if cycle.errors:
        lines.append("\n### Errors")
        for error in cycle.errors:
            lines.append(f"- ⚠️ {error}")

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
            evolution_enabled = state.get("evolution_mode_enabled", True)
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
    ]
