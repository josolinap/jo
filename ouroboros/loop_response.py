"""Response handling and analysis for LLM loops.

Extracted from loop.py (Principle 5: Minimalism).
Handles: hallucination analysis, semantic synthesis, task evaluation, text response.
"""

from __future__ import annotations

import logging
import os
import pathlib
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.response_analyzer import analyze_response

log = logging.getLogger(__name__)

# Feature flags
USE_SEMANTIC_SYNTHESIS = os.environ.get("OUROBOROS_SYNTHESIS", "0") == "1"
USE_TASK_EVALUATION = os.environ.get("OUROBOROS_EVAL", "0") == "1"


def _run_hallucination_analysis(
    content: str,
    messages: List[Dict[str, Any]],
    llm_trace: Dict[str, Any],
) -> str:
    """Run hallucination analysis on final response and add warnings if needed."""
    try:
        repo_dir = str(pathlib.Path(os.environ.get("REPO_DIR", ".")))
        final_analysis = analyze_response(
            response_text=content,
            tool_calls=[],
            messages=messages,
            repo_dir=repo_dir,
        )
        if final_analysis.hallucination_detected:
            high_issues = [i for i in final_analysis.issues if i.severity == "high"]
            if high_issues:
                warning = "\n\n**Verification Warning:** This response may contain unverified claims:\n"
                for issue in high_issues[:3]:
                    warning += f"- {issue.description}\n"
                    if issue.suggestion:
                        warning += f"  -> {issue.suggestion}\n"
                content = content + warning
                log.warning(
                    "[HALLUCINATION] Final response flagged: %d issues, score=%.2f",
                    len(high_issues),
                    final_analysis.quality_score,
                )
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    return content


def _run_semantic_synthesis(content: str, files_changed: List[str] = None) -> Optional[str]:
    """Run semantic synthesis on final response if enabled."""
    if not USE_SEMANTIC_SYNTHESIS:
        return None

    try:
        from ouroboros.synthesis import synthesize_task

        task_text = content[:200] if content else ""

        if task_text:
            return synthesize_task(
                task=task_text,
                output=content or "",
                files_changed=files_changed or [],
                repo_dir=pathlib.Path(os.environ.get("REPO_DIR", ".")) if os.environ.get("REPO_DIR", ".") else None,
            )
    except Exception:
        log.debug("Semantic synthesis failed", exc_info=True)

    return None


def _run_task_evaluation(content: str, files_changed: List[str] = None) -> Optional[str]:
    """Run task evaluation on final response if enabled."""
    if not USE_TASK_EVALUATION:
        return None

    try:
        from ouroboros.eval import evaluate_task

        task_text = content[:200] if content else ""

        if task_text:
            repo_dir_str = os.environ.get("REPO_DIR")
            repo_dir = pathlib.Path(repo_dir_str) if repo_dir_str else None

            return evaluate_task(
                task=task_text,
                output=content or "",
                files_changed=files_changed or [],
                repo_dir=repo_dir,
            )
    except Exception:
        log.debug("Task evaluation failed", exc_info=True)

    return None


def _persist_ontology_tracker() -> None:
    """Persist ontology tracker at end of task."""
    try:
        from ouroboros.codebase_graph import save_ontology_tracker

        save_ontology_tracker()
    except Exception:
        log.debug("Failed to save ontology tracker", exc_info=True)


def _handle_text_response(
    content: Optional[str],
    llm_trace: Dict[str, Any],
    accumulated_usage: Dict[str, Any],
    messages: Optional[List[Dict[str, Any]]] = None,
    files_changed: List[str] = None,
) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
    """Handle LLM response without tool calls (final response)."""
    if content and content.strip():
        llm_trace["assistant_notes"].append(content.strip()[:320])

        # Run hallucination analysis on the FINAL response before returning it
        if messages:
            content = _run_hallucination_analysis(content, messages, llm_trace)

        # Semantic Synthesis Pass
        synthesis_summary = _run_semantic_synthesis(content, files_changed)
        if synthesis_summary:
            llm_trace["synthesis_summary"] = synthesis_summary

        # Task Evaluation
        eval_result = _run_task_evaluation(content, files_changed)
        if eval_result:
            llm_trace["eval_result"] = eval_result

        # Persist ontology tracker
        _persist_ontology_tracker()

        return content, accumulated_usage, llm_trace

    return "No response content", accumulated_usage, llm_trace
