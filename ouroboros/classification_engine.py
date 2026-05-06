"""
Classification Engine — LLM-driven multi-label task classification.

Replaces the stub classification/skill.py with a real classification system
that drives parallel reasoning, skill selection, and tool routing.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ClassificationResult:
    task_type: str
    complexity: str  # low/medium/high
    confidence: float
    labels: List[str]  # Multi-label: e.g., ["debug", "refactor", "security"]
    suggested_skills: List[str]
    suggested_perspectives: int  # How many parallel paths to use
    estimated_cost_tier: str  # low/medium/high
    metadata: Dict[str, Any] = field(default_factory=dict)


# Task type definitions
TASK_TYPES = {
    "debug": {
        "keywords": ["bug", "fix", "error", "crash", "issue", "broken", "fail", "exception", "traceback"],
        "perspectives": 12,
        "cost_tier": "medium",
    },
    "refactor": {
        "keywords": ["refactor", "restructure", "reorganize", "clean", "improve", "simplify", "modularize"],
        "perspectives": 12,
        "cost_tier": "medium",
    },
    "implement": {
        "keywords": ["implement", "create", "build", "add", "new", "feature", "develop", "write"],
        "perspectives": 12,
        "cost_tier": "medium",
    },
    "review": {
        "keywords": ["review", "audit", "check", "inspect", "analyze", "evaluate", "assess"],
        "perspectives": 12,
        "cost_tier": "low",
    },
    "evolve": {
        "keywords": ["evolve", "evolution", "grow", "learn", "improve", "enhance", "upgrade"],
        "perspectives": 12,
        "cost_tier": "high",
    },
    "test": {
        "keywords": ["test", "coverage", "pytest", "unit test", "integration", "e2e"],
        "perspectives": 6,
        "cost_tier": "low",
    },
    "document": {
        "keywords": ["document", "doc", "readme", "comment", "explain", "describe"],
        "perspectives": 4,
        "cost_tier": "low",
    },
    "deploy": {
        "keywords": ["deploy", "release", "ship", "publish", "push", "production"],
        "perspectives": 8,
        "cost_tier": "medium",
    },
    "general": {
        "keywords": [],
        "perspectives": 4,
        "cost_tier": "low",
    },
}


class ClassificationEngine:
    """Classifies tasks using keyword matching + optional LLM verification."""

    def __init__(self, llm_chat_fn: Optional[Callable] = None):
        self.llm_chat_fn = llm_chat_fn
        self._cache: Dict[str, Tuple[ClassificationResult, float]] = {}
        self._cache_ttl = 300  # 5 minutes

    def classify(
        self,
        task_text: str,
        use_llm: bool = False,
    ) -> ClassificationResult:
        """Classify a task. Uses keyword matching by default, LLM if requested."""
        # Check cache
        cache_key = hash(task_text[:500])
        if cache_key in self._cache:
            result, ts = self._cache[cache_key]
            if time.time() - ts < self._cache_ttl:
                return result

        # Keyword-based classification (fast, deterministic)
        result = self._classify_keywords(task_text)

        # Optional LLM verification for high-complexity tasks
        if use_llm and self.llm_chat_fn and result.complexity == "high":
            result = self._verify_with_llm(task_text, result)

        self._cache[cache_key] = (result, time.time())
        return result

    def _classify_keywords(self, task_text: str) -> ClassificationResult:
        """Fast keyword-based classification."""
        text_lower = task_text.lower()
        words = set(text_lower.split())

        type_scores: List[Tuple[str, int]] = []
        all_labels = []

        for task_type, config in TASK_TYPES.items():
            if task_type == "general":
                continue
            score = 0
            for kw in config["keywords"]:
                if kw in text_lower:
                    score += 10 if kw in words else 5
            if score > 0:
                type_scores.append((task_type, score))
                all_labels.append(task_type)

        # Sort by score
        type_scores.sort(key=lambda x: x[1], reverse=True)

        if not type_scores:
            return ClassificationResult(
                task_type="general",
                complexity=self._estimate_complexity(task_text),
                confidence=0.5,
                labels=["general"],
                suggested_skills=[],
                suggested_perspectives=4,
                estimated_cost_tier="low",
            )

        primary_type = type_scores[0][0]
        primary_score = type_scores[0][1]
        config = TASK_TYPES[primary_type]

        # Confidence based on score strength
        confidence = min(1.0, primary_score / 30.0)

        # Suggested skills based on task type
        suggested_skills = self._get_suggested_skills(primary_type, all_labels)

        return ClassificationResult(
            task_type=primary_type,
            complexity=self._estimate_complexity(task_text),
            confidence=confidence,
            labels=all_labels[:5],  # Top 5 labels
            suggested_skills=suggested_skills,
            suggested_perspectives=config["perspectives"],
            estimated_cost_tier=config["cost_tier"],
            metadata={"keyword_scores": {t: s for t, s in type_scores[:3]}},
        )

    def _verify_with_llm(
        self,
        task_text: str,
        keyword_result: ClassificationResult,
    ) -> ClassificationResult:
        """Verify classification with LLM for high-complexity tasks."""
        prompt = (
            f"Classify this task into ONE primary type and list relevant labels.\n\n"
            f"Task: {task_text[:500]}\n\n"
            f"Available types: {', '.join(t for t in TASK_TYPES if t != 'general')}\n\n"
            f"Respond as JSON:\n"
            f'{{"primary_type": "...", "labels": ["...", "..."], "complexity": "low|medium|high"}}'
        )

        try:
            response = self.llm_chat_fn(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200,
                temperature=0.1,
            )
            content = response.get("content", "") if response else ""

            # Parse JSON response
            for line in content.split("\n"):
                line = line.strip()
                if line.startswith("{"):
                    parsed = json.loads(line)
                    primary = parsed.get("primary_type", keyword_result.task_type)
                    if primary in TASK_TYPES:
                        config = TASK_TYPES[primary]
                        return ClassificationResult(
                            task_type=primary,
                            complexity=parsed.get("complexity", keyword_result.complexity),
                            confidence=0.8,  # LLM-verified
                            labels=parsed.get("labels", keyword_result.labels),
                            suggested_skills=self._get_suggested_skills(primary, parsed.get("labels", [])),
                            suggested_perspectives=config["perspectives"],
                            estimated_cost_tier=config["cost_tier"],
                            metadata={"llm_verified": True},
                        )
        except Exception as e:
            log.warning(f"[Classification] LLM verification failed: {e}")

        return keyword_result

    def _estimate_complexity(self, task_text: str) -> str:
        """Estimate task complexity from text length and keywords."""
        words = len(task_text.split())
        complexity_keywords = ["complex", "difficult", "challenging", "large", "multiple", "system", "architecture"]

        score = 0
        if words > 100:
            score += 2
        elif words > 30:
            score += 1

        text_lower = task_text.lower()
        for kw in complexity_keywords:
            if kw in text_lower:
                score += 1

        if score >= 3:
            return "high"
        elif score >= 1:
            return "medium"
        return "low"

    def _get_suggested_skills(self, primary_type: str, labels: List[str]) -> List[str]:
        """Map task types to suggested skills."""
        skill_map = {
            "debug": ["debug", "review"],
            "refactor": ["plan-eng", "review"],
            "implement": ["plan", "plan-eng"],
            "review": ["review", "security"],
            "evolve": ["plan", "retro"],
            "test": ["qa"],
            "document": ["plan"],
            "deploy": ["ship"],
            "general": [],
        }
        return skill_map.get(primary_type, [])


# Singleton
_engine: Optional[ClassificationEngine] = None


def get_classification_engine(llm_chat_fn: Optional[Callable] = None) -> ClassificationEngine:
    """Get or create the singleton classification engine."""
    global _engine
    if _engine is None:
        _engine = ClassificationEngine(llm_chat_fn)
    return _engine


def reset_classification_engine() -> None:
    """Reset the singleton."""
    global _engine
    _engine = None
