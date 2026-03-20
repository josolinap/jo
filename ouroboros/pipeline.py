"""Structured pipeline architecture for Jo - formalizes execution phases."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class PipelinePhase(Enum):
    DIAGNOSE = "diagnose"
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    SYNTHESIZE = "synthesize"


@dataclass
class PhaseResult:
    phase: PipelinePhase
    success: bool
    output: Any = None
    error: str = ""
    duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineContext:
    task: str
    current_phase: PipelinePhase = PipelinePhase.DIAGNOSE
    messages: List[Dict] = field(default_factory=list)
    results: List[PhaseResult] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_result(self, result: PhaseResult) -> None:
        self.results.append(result)
        if not result.success:
            self.errors.append(f"{result.phase.value}: {result.error}")

    def is_successful(self) -> bool:
        return len(self.errors) == 0


class PhaseHandler:
    """Base class for phase handlers."""

    def __init__(self, name: str):
        self.name = name

    def can_handle(self, ctx: PipelineContext) -> bool:
        raise NotImplementedError

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        raise NotImplementedError


class DiagnoseHandler(PhaseHandler):
    """Phase 1: Understand the task, identify constraints."""

    def __init__(self):
        super().__init__("diagnose")

    def can_handle(self, ctx: PipelineContext) -> bool:
        return ctx.current_phase == PipelinePhase.DIAGNOSE

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        import time

        start = time.time()

        task = ctx.task.lower()
        ctx.metadata["task_type"] = self._classify_task(task)
        ctx.metadata["complexity"] = self._estimate_complexity(task)
        ctx.metadata["requires_code"] = any(
            kw in task for kw in ["code", "file", "function", "class", "implement", "fix", "add"]
        )

        duration = (time.time() - start) * 1000

        return PhaseResult(
            phase=PipelinePhase.DIAGNOSE,
            success=True,
            output={
                "task_type": ctx.metadata["task_type"],
                "complexity": ctx.metadata["complexity"],
            },
            duration_ms=duration,
        )

    def _classify_task(self, task: str) -> str:
        if any(kw in task for kw in ["bug", "fix", "error", "crash", "issue"]):
            return "bug_fix"
        if any(kw in task for kw in ["test", "coverage"]):
            return "testing"
        if any(kw in task for kw in ["refactor", "improve", "optimize"]):
            return "refactor"
        if any(kw in task for kw in ["add", "implement", "create", "new"]):
            return "feature"
        if any(kw in task for kw in ["explain", "what", "how", "why"]):
            return "explanation"
        if any(kw in task for kw in ["review", "check", "audit"]):
            return "review"
        return "general"

    def _estimate_complexity(self, task: str) -> str:
        words = len(task.split())
        if words > 50:
            return "high"
        if words > 20:
            return "medium"
        return "low"


class PlanHandler(PhaseHandler):
    """Phase 2: Break down into sub-tasks if needed."""

    def __init__(self):
        super().__init__("plan")

    def can_handle(self, ctx: PipelineContext) -> bool:
        return ctx.current_phase == PipelinePhase.PLAN

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        import time

        start = time.time()

        complexity = ctx.metadata.get("complexity", "low")
        task_type = ctx.metadata.get("task_type", "general")

        sub_tasks = []
        if complexity == "high":
            sub_tasks = self._decompose_task(ctx.task)

        ctx.metadata["sub_tasks"] = sub_tasks
        ctx.metadata["needs_orchestration"] = len(sub_tasks) > 1

        duration = (time.time() - start) * 1000

        return PhaseResult(
            phase=PipelinePhase.PLAN,
            success=True,
            output={
                "sub_tasks": sub_tasks,
                "needs_orchestration": len(sub_tasks) > 1,
            },
            duration_ms=duration,
        )

    def _decompose_task(self, task: str) -> List[Dict[str, str]]:
        return [
            {"description": "Analyze requirements", "role": "analyzer"},
            {"description": "Implement changes", "role": "coder"},
            {"description": "Verify implementation", "role": "reviewer"},
        ]


class ExecuteHandler(PhaseHandler):
    """Phase 3: Execute tools and gather data."""

    def __init__(self):
        super().__init__("execute")

    def can_handle(self, ctx: PipelineContext) -> bool:
        return ctx.current_phase == PipelinePhase.EXECUTE

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        ctx.metadata["execution_started"] = True
        return PhaseResult(
            phase=PipelinePhase.EXECUTE,
            success=True,
            output={"status": "ready_for_execution"},
        )


class VerifyHandler(PhaseHandler):
    """Phase 4: Check results quality."""

    def __init__(self):
        super().__init__("verify")

    def can_handle(self, ctx: PipelineContext) -> bool:
        return ctx.current_phase == PipelinePhase.VERIFY

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        from ouroboros.eval import evaluate_task
        from pathlib import Path

        repo_dir = os.environ.get("REPO_DIR", ".")
        output = ctx.metadata.get("final_output", "")

        eval_result = evaluate_task(
            task=ctx.task,
            output=output,
            repo_dir=Path(repo_dir),
        )

        passed = eval_result is None

        return PhaseResult(
            phase=PipelinePhase.VERIFY,
            success=passed,
            output={"passed": passed, "report": eval_result},
        )


class SynthesizeHandler(PhaseHandler):
    """Phase 5: Final polish and consistency."""

    def __init__(self):
        super().__init__("synthesize")

    def can_handle(self, ctx: PipelineContext) -> bool:
        return ctx.current_phase == PipelinePhase.SYNTHESIZE

    def execute(self, ctx: PipelineContext) -> PhaseResult:
        from ouroboros.synthesis import synthesize_task
        from pathlib import Path

        repo_dir = os.environ.get("REPO_DIR", ".")
        output = ctx.metadata.get("final_output", "")
        files_changed = ctx.metadata.get("files_changed", [])

        synth_result = synthesize_task(
            task=ctx.task,
            output=output,
            files_changed=files_changed,
            repo_dir=Path(repo_dir),
        )

        return PhaseResult(
            phase=PipelinePhase.SYNTHESIZE,
            success=True,
            output={"report": synth_result},
        )


class Pipeline:
    """Structured execution pipeline with phases."""

    def __init__(self, enabled: bool = False):
        self._enabled = enabled
        self._handlers: Dict[PipelinePhase, PhaseHandler] = {}
        self._register_default_handlers()

    def _register_default_handlers(self) -> None:
        self._handlers = {
            PipelinePhase.DIAGNOSE: DiagnoseHandler(),
            PipelinePhase.PLAN: PlanHandler(),
            PipelinePhase.EXECUTE: ExecuteHandler(),
            PipelinePhase.VERIFY: VerifyHandler(),
            PipelinePhase.SYNTHESIZE: SynthesizeHandler(),
        }

    def is_enabled(self) -> bool:
        return self._enabled

    def run_diagnose(self, ctx: PipelineContext) -> PhaseResult:
        if not self._enabled:
            return PhaseResult(phase=PipelinePhase.DIAGNOSE, success=True)

        ctx.current_phase = PipelinePhase.DIAGNOSE
        handler = self._handlers.get(PipelinePhase.DIAGNOSE)
        if handler:
            return handler.execute(ctx)
        return PhaseResult(phase=PipelinePhase.DIAGNOSE, success=True)

    def run_plan(self, ctx: PipelineContext) -> PhaseResult:
        if not self._enabled:
            return PhaseResult(phase=PipelinePhase.PLAN, success=True)

        ctx.current_phase = PipelinePhase.PLAN
        handler = self._handlers.get(PipelinePhase.PLAN)
        if handler:
            return handler.execute(ctx)
        return PhaseResult(phase=PipelinePhase.PLAN, success=True)

    def run_verify(self, ctx: PipelineContext) -> PhaseResult:
        if not self._enabled:
            return PhaseResult(phase=PipelinePhase.VERIFY, success=True)

        ctx.current_phase = PipelinePhase.VERIFY
        handler = self._handlers.get(PipelinePhase.VERIFY)
        if handler:
            return handler.execute(ctx)
        return PhaseResult(phase=PipelinePhase.VERIFY, success=True)

    def run_synthesize(self, ctx: PipelineContext) -> PhaseResult:
        if not self._enabled:
            return PhaseResult(phase=PipelinePhase.SYNTHESIZE, success=True)

        ctx.current_phase = PipelinePhase.SYNTHESIZE
        handler = self._handlers.get(PipelinePhase.SYNTHESIZE)
        if handler:
            return handler.execute(ctx)
        return PhaseResult(phase=PipelinePhase.SYNTHESIZE, success=True)


_pipeline: Optional[Pipeline] = None


def get_pipeline() -> Pipeline:
    """Get singleton pipeline instance."""
    global _pipeline
    if _pipeline is None:
        enabled = os.environ.get("OUROBOROS_USE_PIPELINE", "0") == "1"
        _pipeline = Pipeline(enabled=enabled)
    return _pipeline
