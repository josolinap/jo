"""Ouroboros agent — thin orchestrator, delegates to loop/context/tools."""

from __future__ import annotations

import logging
import os
import pathlib
import signal
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.llm import LLMClient
from ouroboros.loop import run_llm_loop
from ouroboros.context import build_context, get_system_prompt
from ouroboros.tools.registry import ToolRegistry
from ouroboros.memory import Memory
from ouroboros.pipeline import get_pipeline, PipelineContext, PipelinePhase
from ouroboros.utils import utc_now_iso, estimate_tokens

log = logging.getLogger(__name__)


class Agent:
    """Thin orchestrator: builds context, runs loop, handles tools."""

    def __init__(
        self,
        *,
        repo_dir: pathlib.Path,
        memory: Memory,
        tool_registry: ToolRegistry,
        llm: LLMClient,
        model: str,
        reasoning_effort: Optional[str] = None,
        max_rounds: int = 50,
        emit_progress=None,
        task_id: str = "",
        event_queue=None,
        drive_root: Optional[pathlib.Path] = None,
    ):
        self.repo_dir = repo_dir
        self.memory = memory
        self.tool_registry = tool_registry
        self.llm = llm
        self.model = model
        self.reasoning_effort = reasoning_effort
        self.max_rounds = max_rounds
        self.emit_progress = emit_progress or (lambda x: None)
        self.task_id = task_id
        self.event_queue = event_queue
        self.drive_root = drive_root

    def run_task(self, task_text: str, chat_mode: bool = False) -> Tuple[str, Dict[str, Any]]:
        """Execute a single task and return final response with usage."""
        start_time = time.time()
        accumulated_usage: Dict[str, Any] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cached_prompt_tokens": 0,
            "cost": 0.0,
            "model": self.model,
            "reasoning_effort": self.reasoning_effort,
        }

        pipeline = get_pipeline()
        pipeline_ctx = None
        if pipeline.is_enabled():
            pipeline_ctx = PipelineContext(task=task_text)
            # DIAGNOSE phase
            diag_result = pipeline.run_diagnose(pipeline_ctx)
            if not diag_result.success:
                return f"[Pipeline error in DIAGNOSE: {diag_result.error}]", accumulated_usage
            # PLAN phase
            plan_result = pipeline.run_plan(pipeline_ctx)
            if not plan_result.success:
                return f"[Pipeline error in PLAN: {plan_result.error}]", accumulated_usage

        # Build initial context (system + user task + recent history)
        system_prompt = get_system_prompt(self.repo_dir)
        messages = build_context(
            repo_dir=self.repo_dir,
            memory=self.memory,
            task_text=task_text,
            system_prompt=system_prompt,
            chat_mode=chat_mode,
        )

        # If pipeline is planning to decompose, we could add that to context or schedule subtasks
        if pipeline_ctx and pipeline_ctx.metadata.get("needs_orchestration"):
            self.emit_progress("🔄 Pipeline suggests task decomposition — using task graph")
            # For now, just note it; future: actually decompose

        # Run the core LLM loop
        final_content, loop_usage, llm_trace = run_llm_loop(
            messages=messages,
            repo_dir=self.repo_dir,
            llm=self.llm,
            tool_registry=self.tool_registry,
            model=self.model,
            reasoning_effort=self.reasoning_effort,
            max_rounds=self.max_rounds,
            emit_progress=self.emit_progress,
            task_id=self.task_id,
            event_queue=self.event_queue,
            drive_root=self.drive_root,
            task_text=task_text,
        )

        # Merge usage
        for k in ["prompt_tokens", "completion_tokens", "cached_prompt_tokens", "cost"]:
            accumulated_usage[k] += loop_usage.get(k, 0)
        accumulated_usage["model"] = loop_usage.get("model", self.model)

        # Pipeline VERIFY and SYNTHESIZE phases
        if pipeline_ctx:
            pipeline_ctx.metadata["final_output"] = final_content
            # Collect changed files from git if any
            try:
                from ouroboros.git_ops import get_git_status
                git_status = get_git_status(self.repo_dir)
                changed_files = [f for f in git_status.get("modified", []) + git_status.get("added", [])]
                pipeline_ctx.metadata["files_changed"] = changed_files
            except Exception:
                pipeline_ctx.metadata["files_changed"] = []

            verify_result = pipeline.run_verify(pipeline_ctx)
            if not verify_result.success:
                self.emit_progress(f"⚠️ Verify failed: {verify_result.error}")
            synthesize_result = pipeline.run_synthesize(pipeline_ctx)
            if not synthesize_result.success:
                self.emit_progress(f"⚠️ Synthesize failed: {synthesize_result.error}")

            # Append pipeline reports to final content
            reports = []
            if verify_result.output and verify_result.output.get("report"):
                reports.append("## Verification\n" + verify_result.output["report"])
            if synthesize_result.output and synthesize_result.output.get("report"):
                reports.append("## Synthesis\n" + synthesize_result.output["report"])
            if reports:
                final_content = final_content + "\n\n" + "\n\n".join(reports)

        duration = time.time() - start_time
        accumulated_usage["duration_sec"] = duration

        log.info(
            f"Task completed. Tokens: {accumulated_usage['prompt_tokens']}+{accumulated_usage['completion_tokens']} "
            f"cached:{accumulated_usage['cached_prompt_tokens']} Cost:${accumulated_usage['cost']:.3f} Time:{duration:.1f}s"
        )

        return final_content, accumulated_usage
