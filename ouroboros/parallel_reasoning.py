"""
Parallel Reasoning — concurrent reasoning paths with deliberation.

For complex tasks, spawns multiple reasoning perspectives concurrently,
then deliberates to merge results into a unified conclusion.

Supports up to 12 concurrent works with per-work checkpointing.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ReasoningPath:
    id: str
    perspective: str
    prompt: str
    result: Optional[str] = None
    confidence: float = 0.0
    error: Optional[str] = None
    duration_ms: float = 0.0
    tokens_estimated: int = 0


@dataclass
class DeliberationResult:
    consensus: str
    disagreements: List[str]
    recommended_path: str
    recommended_action: str
    confidence: float
    all_results: List[ReasoningPath]
    duration_ms: float = 0.0


# Perspective sets for different task types
PERSPECTIVE_SETS: Dict[str, List[str]] = {
    "coding": [
        "Senior Engineer",
        "Code Reviewer",
        "Security Auditor",
        "Performance Engineer",
        "DevOps Engineer",
        "QA Engineer",
        "API Designer",
        "Database Expert",
        "Frontend Specialist",
        "Backend Architect",
        "Testing Expert",
        "Documentation Writer",
    ],
    "architecture": [
        "System Architect",
        "Security Expert",
        "Performance Engineer",
        "Scalability Expert",
        "Reliability Engineer",
        "Cost Optimizer",
        "Developer Experience",
        "Data Engineer",
        "ML Engineer",
        "Platform Engineer",
        "SRE",
        "Product Manager",
    ],
    "debug": [
        "Debugger",
        "Log Analyst",
        "Performance Profiler",
        "Memory Expert",
        "Network Specialist",
        "Database DBA",
        "OS Expert",
        "Compiler Engineer",
        "Runtime Specialist",
        "Error Handling Expert",
        "Testing Expert",
        "Root Cause Analyst",
    ],
    "refactor": [
        "Clean Code Expert",
        "Architecture Reviewer",
        "Performance Analyst",
        "Security Auditor",
        "Maintainability Expert",
        "API Designer",
        "Testing Strategist",
        "Documentation Specialist",
        "Migration Planner",
        "Dependency Analyst",
        "Pattern Expert",
        "Tech Debt Assessor",
    ],
    "review": [
        "Code Reviewer",
        "Security Auditor",
        "Performance Analyst",
        "Style Guide Enforcer",
        "Best Practice Checker",
        "Test Coverage Analyst",
        "Documentation Reviewer",
        "Architecture Validator",
        "Dependency Checker",
        "Error Handling Reviewer",
        "Maintainability Assessor",
        "Compliance Auditor",
    ],
    "evolution": [
        "Innovation Strategist",
        "Technical Visionary",
        "Risk Assessor",
        "Growth Architect",
        "Quality Guardian",
        "Efficiency Expert",
        "Scalability Planner",
        "Security Forward-Thinker",
        "User Experience Designer",
        "Platform Evolutionist",
        "Automation Specialist",
        "Learning System Designer",
    ],
}

# Default perspectives for unknown task types
DEFAULT_PERSPECTIVES = [
    "Engineer",
    "Architect",
    "Security Expert",
    "QA Engineer",
    "Performance Analyst",
    "User Advocate",
    "DevOps Engineer",
    "Data Specialist",
    "Documentation Writer",
    "Testing Expert",
    "Product Manager",
    "SRE",
]


class ParallelReasoner:
    """Runs multiple reasoning paths concurrently and deliberates."""

    MAX_PARALLEL_PATHS = 12
    DELIBERATION_TIMEOUT = 120  # seconds

    def __init__(self, llm_chat_fn: Callable):
        self.llm_chat_fn = llm_chat_fn
        self.executor = ThreadPoolExecutor(
            max_workers=self.MAX_PARALLEL_PATHS,
            thread_name_prefix="parallel-reasoning",
        )

    def reason_in_parallel(
        self,
        task: str,
        task_type: str = "general",
        base_prompt: str = "",
        max_paths: int = 12,
        checkpoint_fn: Optional[Callable] = None,
    ) -> DeliberationResult:
        """Run multiple reasoning paths in parallel and deliberate."""
        start = time.time()

        perspectives = PERSPECTIVE_SETS.get(task_type, DEFAULT_PERSPECTIVES)
        perspectives = perspectives[: min(max_paths, self.MAX_PARALLEL_PATHS)]

        # Create reasoning paths
        paths = []
        for i, perspective in enumerate(perspectives):
            path_prompt = self._build_path_prompt(task, perspective, base_prompt)
            path = ReasoningPath(
                id=f"work_{uuid.uuid4().hex[:8]}",
                perspective=perspective,
                prompt=path_prompt,
            )
            paths.append(path)

            # Create checkpoint for this work
            if checkpoint_fn:
                checkpoint_fn(path.id, perspective, "pending")

        log.info(f"[ParallelReasoning] Starting {len(paths)} reasoning paths for task type: {task_type}")

        # Execute all paths concurrently
        futures = {}
        for path in paths:
            future = self.executor.submit(self._run_single_path, path, checkpoint_fn)
            futures[future] = path

        # Collect results
        completed = 0
        for future in as_completed(futures, timeout=self.DELIBERATION_TIMEOUT):
            path = futures[future]
            try:
                path.result, path.confidence, path.duration_ms, path.tokens_estimated = future.result()
                completed += 1

                if checkpoint_fn:
                    checkpoint_fn(path.id, path.perspective, "done", progress=1.0, result=path.result)

                log.info(
                    f"[ParallelReasoning] Path {path.perspective} completed "
                    f"({completed}/{len(paths)}, confidence={path.confidence:.2f})"
                )
            except Exception as e:
                path.error = str(e)
                path.confidence = 0.0

                if checkpoint_fn:
                    checkpoint_fn(path.id, path.perspective, "failed", error=str(e))

                log.warning(f"[ParallelReasoning] Path {path.perspective} failed: {e}")

        # Deliberate: merge all results
        result = self._deliberate(task, paths)
        result.duration_ms = (time.time() - start) * 1000

        log.info(
            f"[ParallelReasoning] Deliberation complete: "
            f"confidence={result.confidence:.2f}, "
            f"consensus_len={len(result.consensus)}"
        )

        return result

    def _run_single_path(
        self,
        path: ReasoningPath,
        checkpoint_fn: Optional[Callable] = None,
    ) -> Tuple[str, float, float, int]:
        """Run a single reasoning path through the LLM."""
        start = time.time()

        # Update checkpoint to running
        if checkpoint_fn:
            checkpoint_fn(path.id, path.perspective, "running", progress=0.5)

        try:
            response = self.llm_chat_fn(
                messages=[{"role": "user", "content": path.prompt}],
                temperature=0.7,  # Higher temp for diverse reasoning
                max_tokens=2000,
            )
            content = response.get("content", "") if response else ""
            duration_ms = (time.time() - start) * 1000
            tokens_est = len(content) // 4

            # Estimate confidence based on response quality
            confidence = self._estimate_confidence(content)

            return content, confidence, duration_ms, tokens_est

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            raise

    def _build_path_prompt(self, task: str, perspective: str, base_prompt: str) -> str:
        """Build the prompt for a single reasoning path."""
        return (
            f"You are analyzing this task from the perspective of a {perspective}.\n\n"
            f"Task: {task}\n\n"
            f"Provide your analysis focusing on your area of expertise. "
            f"Be specific, actionable, and concise.\n\n"
            f"Structure your response as:\n"
            f"1. KEY OBSERVATIONS: What stands out to you?\n"
            f"2. RECOMMENDATIONS: What should be done?\n"
            f"3. RISKS: What could go wrong?\n"
            f"4. CONFIDENCE: How confident are you (0.0-1.0)?\n\n"
            f"{base_prompt}"
        )

    def _deliberate(self, task: str, paths: List[ReasoningPath]) -> DeliberationResult:
        """Merge multiple reasoning paths into a deliberated conclusion."""
        successful = [p for p in paths if p.result and not p.error]

        if not successful:
            return DeliberationResult(
                consensus="All reasoning paths failed to produce results.",
                disagreements=[],
                recommended_path="",
                recommended_action="Proceed with caution — no parallel analysis available.",
                confidence=0.0,
                all_results=paths,
            )

        # Build viewpoints summary
        viewpoints = "\n\n".join(
            f"--- {p.perspective} (confidence: {p.confidence:.2f}) ---\n{p.result}" for p in successful
        )

        deliberation_prompt = (
            f"Task: {task}\n\n"
            f"Multiple expert perspectives analyzed this task:\n\n"
            f"{viewpoints}\n\n"
            f"Deliberate and produce a unified conclusion:\n\n"
            f"CONSENSUS: What do all/most perspectives agree on? (2-3 sentences)\n"
            f"DISAGREEMENTS: Where do they differ? (bullet points)\n"
            f"RECOMMENDED PATH: Which perspective's approach should we follow and why?\n"
            f"RECOMMENDED ACTION: What specific steps should we take next?\n"
            f"CONFIDENCE: Overall confidence (0.0-1.0)\n\n"
            f"Format your response with these exact headers."
        )

        try:
            response = self.llm_chat_fn(
                messages=[{"role": "user", "content": deliberation_prompt}],
                temperature=0.3,  # Lower temp for focused deliberation
                max_tokens=2000,
            )
            content = response.get("content", "") if response else ""
        except Exception as e:
            log.warning(f"[ParallelReasoning] Deliberation LLM call failed: {e}")
            content = ""

        return self._parse_deliberation(content, paths)

    def _parse_deliberation(self, content: str, paths: List[ReasoningPath]) -> DeliberationResult:
        """Parse deliberation output into structured result."""
        consensus = ""
        disagreements = []
        recommended_path = ""
        recommended_action = ""
        confidence = 0.5

        if content:
            # Parse sections
            sections = content.split("\n")
            current_section = ""

            for line in sections:
                line_stripped = line.strip()
                if line_stripped.startswith("CONSENSUS:"):
                    current_section = "consensus"
                    consensus = line_stripped[len("CONSENSUS:") :].strip()
                elif line_stripped.startswith("DISAGREEMENTS:"):
                    current_section = "disagreements"
                    text = line_stripped[len("DISAGREEMENTS:") :].strip()
                    if text:
                        disagreements.append(text)
                elif line_stripped.startswith("RECOMMENDED PATH:"):
                    current_section = "recommended_path"
                    recommended_path = line_stripped[len("RECOMMENDED PATH:") :].strip()
                elif line_stripped.startswith("RECOMMENDED ACTION:"):
                    current_section = "recommended_action"
                    recommended_action = line_stripped[len("RECOMMENDED ACTION:") :].strip()
                elif line_stripped.startswith("CONFIDENCE:"):
                    try:
                        conf_str = line_stripped[len("CONFIDENCE:") :].strip()
                        confidence = float(conf_str)
                    except (ValueError, TypeError):
                        confidence = 0.5
                elif current_section == "disagreements" and line_stripped.startswith("-"):
                    disagreements.append(line_stripped[1:].strip())
                elif current_section == "consensus":
                    consensus += " " + line_stripped
                elif current_section == "recommended_path":
                    recommended_path += " " + line_stripped
                elif current_section == "recommended_action":
                    recommended_action += " " + line_stripped

        # Fallback: pick highest confidence path
        if not recommended_path and paths:
            best = max(paths, key=lambda p: p.confidence)
            recommended_path = f"Follow {best.perspective} approach (confidence: {best.confidence:.2f})"

        return DeliberationResult(
            consensus=consensus or "No clear consensus reached.",
            disagreements=disagreements,
            recommended_path=recommended_path,
            recommended_action=recommended_action or "Proceed with the highest-confidence approach.",
            confidence=confidence,
            all_results=paths,
        )

    def _estimate_confidence(self, content: str) -> float:
        """Estimate confidence based on response quality heuristics."""
        if not content or len(content) < 50:
            return 0.3

        score = 0.5

        # Longer responses tend to be more thorough
        if len(content) > 200:
            score += 0.1
        if len(content) > 500:
            score += 0.1

        # Structured responses are better
        if any(kw in content.lower() for kw in ["observation", "recommend", "risk", "key"]):
            score += 0.1

        # Specific details increase confidence
        if any(kw in content.lower() for kw in ["specifically", "because", "therefore", "however"]):
            score += 0.1

        return min(1.0, score)

    def shutdown(self, wait: bool = True) -> None:
        """Shutdown the thread pool executor."""
        self.executor.shutdown(wait=wait)


# Singleton instance
_reasoner: Optional[ParallelReasoner] = None


def get_parallel_reasoner(llm_chat_fn: Optional[Callable] = None) -> ParallelReasoner:
    """Get or create the singleton parallel reasoner."""
    global _reasoner
    if _reasoner is None:
        if llm_chat_fn is None:
            raise ValueError("llm_chat_fn required for first initialization")
        _reasoner = ParallelReasoner(llm_chat_fn)
    return _reasoner


def reset_parallel_reasoner() -> None:
    """Reset the singleton (for testing or reconfiguration)."""
    global _reasoner
    if _reasoner:
        _reasoner.shutdown()
    _reasoner = None
