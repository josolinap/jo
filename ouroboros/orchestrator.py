"""
Orchestrator — coordinates inner skills, parallel reasoning, deliberation, and checkpoints.

This is the central coordinator that ties together:
1. Classification Engine — classifies incoming tasks
2. Inner Skills — runs cognitive operations before tool execution
3. Parallel Reasoning — spawns 12 concurrent reasoning paths
4. Deliberation — merges results from parallel paths
5. Work Checkpoints — saves/restores state for each parallel work

Usage:
    orchestrator = get_orchestrator(llm_chat_fn)
    result = orchestrator.process_complex_task(task_text)
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class OrchestrationResult:
    success: bool
    task_type: str
    classification_confidence: float
    parallel_used: bool
    parallel_count: int
    deliberation_confidence: float
    consensus: str
    recommended_action: str
    inner_skills_used: List[str]
    checkpoint_status: Dict[str, Any]
    duration_ms: float = 0.0
    error: Optional[str] = None


class Orchestrator:
    """Central coordinator for inner skills, parallel reasoning, and checkpoints."""

    def __init__(self, llm_chat_fn: Callable, checkpoint_dir: Optional[Path] = None):
        self.llm_chat_fn = llm_chat_fn
        self.checkpoint_dir = checkpoint_dir

        # Lazy-initialized components
        self._classification_engine = None
        self._parallel_reasoner = None
        self._checkpoint_manager = None

    @property
    def classification_engine(self):
        if self._classification_engine is None:
            from ouroboros.classification_engine import get_classification_engine

            self._classification_engine = get_classification_engine(self.llm_chat_fn)
        return self._classification_engine

    @property
    def parallel_reasoner(self):
        if self._parallel_reasoner is None:
            from ouroboros.parallel_reasoning import get_parallel_reasoner

            self._parallel_reasoner = get_parallel_reasoner(self.llm_chat_fn)
        return self._parallel_reasoner

    @property
    def checkpoint_manager(self):
        if self._checkpoint_manager is None:
            from ouroboros.work_checkpoint import get_checkpoint_manager

            self._checkpoint_manager = get_checkpoint_manager(self.checkpoint_dir)
        return self._checkpoint_manager

    def process_complex_task(
        self,
        task_text: str,
        force_parallel: bool = False,
        max_paths: int = 12,
    ) -> OrchestrationResult:
        """Process a task through the full orchestration pipeline."""
        start = time.time()

        # Step 1: Classify the task
        classification = self.classification_engine.classify(task_text)
        log.info(
            f"[Orchestrator] Classified task: type={classification.task_type}, "
            f"complexity={classification.complexity}, confidence={classification.confidence:.2f}"
        )

        # Step 2: Run inner skills for deliberation before action
        from ouroboros.inner_skills import execute_inner_skills_batch, format_inner_skill_results

        inner_results = execute_inner_skills_batch(
            task_text=task_text,
            llm_chat_fn=self.llm_chat_fn,
        )
        inner_skills_used = [r.skill_name for r in inner_results]
        inner_skill_text = format_inner_skill_results(inner_results)

        log.info(f"[Orchestrator] Inner skills activated: {inner_skills_used}")

        # Step 3: Decide whether to use parallel reasoning
        use_parallel = (
            force_parallel or classification.complexity == "high" or classification.suggested_perspectives >= 8
        )

        if use_parallel:
            # Step 4: Run parallel reasoning with checkpoints
            parallel_count = min(max_paths, classification.suggested_perspectives)

            def checkpoint_callback(work_id, perspective, status, progress=0.0, result=None, error=None):
                try:
                    if status == "pending":
                        self.checkpoint_manager.create_work(work_id, perspective)
                    else:
                        self.checkpoint_manager.update_work(
                            work_id,
                            status=status,
                            progress=progress,
                            result=result,
                            error=error,
                        )
                except Exception as e:
                    log.warning(f"[Orchestrator] Checkpoint callback failed: {e}")

            try:
                deliberation = self.parallel_reasoner.reason_in_parallel(
                    task=task_text,
                    task_type=classification.task_type,
                    base_prompt=inner_skill_text,
                    max_paths=parallel_count,
                    checkpoint_fn=checkpoint_callback,
                )

                duration_ms = (time.time() - start) * 1000

                return OrchestrationResult(
                    success=True,
                    task_type=classification.task_type,
                    classification_confidence=classification.confidence,
                    parallel_used=True,
                    parallel_count=parallel_count,
                    deliberation_confidence=deliberation.confidence,
                    consensus=deliberation.consensus,
                    recommended_action=deliberation.recommended_action,
                    inner_skills_used=inner_skills_used,
                    checkpoint_status=self.checkpoint_manager.get_all_status(),
                    duration_ms=duration_ms,
                )

            except Exception as e:
                log.warning(f"[Orchestrator] Parallel reasoning failed, falling back: {e}")
                # Fall through to single-path processing

        # Single-path processing (fallback or simple tasks)
        duration_ms = (time.time() - start) * 1000

        return OrchestrationResult(
            success=True,
            task_type=classification.task_type,
            classification_confidence=classification.confidence,
            parallel_used=False,
            parallel_count=0,
            deliberation_confidence=0.0,
            consensus=inner_skill_text or "No deliberation needed for simple task.",
            recommended_action=f"Proceed with {classification.task_type} approach.",
            inner_skills_used=inner_skills_used,
            checkpoint_status={},
            duration_ms=duration_ms,
        )

    def get_status_report(self) -> str:
        """Get a formatted status report of all systems."""
        lines = ["## Orchestrator Status"]

        # Checkpoint status
        try:
            cp_status = self.checkpoint_manager.get_all_status()
            lines.append(f"\n### Checkpoints")
            lines.append(f"- Active works: {cp_status['total']}")
            lines.append(f"- Running: {cp_status['running']}")
            lines.append(f"- Done: {cp_status['done']}")
            lines.append(f"- Failed: {cp_status['failed']}")
        except Exception:
            lines.append("\n### Checkpoints: unavailable")

        return "\n".join(lines)

    def shutdown(self) -> None:
        """Shutdown all components."""
        if self._parallel_reasoner:
            self._parallel_reasoner.shutdown()


# Singleton
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator(
    llm_chat_fn: Optional[Callable] = None,
    checkpoint_dir: Optional[Path] = None,
) -> Orchestrator:
    """Get or create the singleton orchestrator."""
    global _orchestrator
    if _orchestrator is None:
        if llm_chat_fn is None:
            raise ValueError("llm_chat_fn required for first initialization")
        _orchestrator = Orchestrator(llm_chat_fn, checkpoint_dir)
    return _orchestrator


def reset_orchestrator() -> None:
    """Reset the singleton."""
    global _orchestrator
    if _orchestrator:
        _orchestrator.shutdown()
    _orchestrator = None
