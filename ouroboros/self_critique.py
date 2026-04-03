"""
Jo — Self-Critique Evaluator Loop.

Inspired by CriticGPT and the awesome-agentic-patterns catalogue.
Jo evaluates its own work before committing, catching errors early.

Problem: Agents commit changes without self-evaluation, leading to
bugs, regressions, and wasted iterations.

Solution: A structured self-critique loop that evaluates work across
multiple dimensions before committing:
1. Correctness: Does it solve the problem?
2. Completeness: Are all requirements met?
3. Safety: Are there security or stability risks?
4. Quality: Does it meet code standards?
5. Efficiency: Is it performant and maintainable?

The critique produces a structured report with scores and recommendations.
If the score is below threshold, Jo revises before committing.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class CritiqueDimension:
    """A single dimension of critique."""

    name: str
    score: float  # 0.0-1.0
    issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class SelfCritique:
    """A complete self-critique evaluation."""

    id: str
    task_description: str
    dimensions: List[CritiqueDimension] = field(default_factory=list)
    overall_score: float = 0.0
    passed: bool = False
    threshold: float = 0.7  # Minimum score to pass
    created_at: str = ""
    recommendations: List[str] = field(default_factory=list)


class SelfCritiqueEvaluator:
    """Evaluates Jo's own work before committing."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.state_dir = repo_dir / ".jo_state" / "self_critique"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._critiques: List[SelfCritique] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load critique history."""
        for critique_file in self.state_dir.glob("critique_*.json"):
            try:
                data = json.loads(critique_file.read_text(encoding="utf-8"))
                critique = SelfCritique(**data)
                self._critiques.append(critique)
            except Exception:
                pass

    def _save_critique(self, critique: SelfCritique) -> None:
        """Save a critique to disk."""
        critique_file = self.state_dir / f"critique_{critique.id}.json"
        critique_file.write_text(
            json.dumps(
                {
                    "id": critique.id,
                    "task_description": critique.task_description,
                    "dimensions": [
                        {
                            "name": d.name,
                            "score": d.score,
                            "issues": d.issues,
                            "recommendations": d.recommendations,
                        }
                        for d in critique.dimensions
                    ],
                    "overall_score": critique.overall_score,
                    "passed": critique.passed,
                    "threshold": critique.threshold,
                    "created_at": critique.created_at,
                    "recommendations": critique.recommendations,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    def evaluate(
        self, task_description: str, work_summary: str, changed_files: List[str], threshold: float = 0.7
    ) -> SelfCritique:
        """Evaluate work across multiple dimensions.

        This is a self-evaluation framework. The actual scoring is done
        by the LLM when prompted with the critique template.
        """
        critique_id = f"critique-{int(time.time())}"
        now = datetime.now().isoformat()

        # Create dimensions with placeholder scores
        # The LLM will fill in actual scores when prompted
        dimensions = [
            CritiqueDimension(name="correctness", score=0.0),
            CritiqueDimension(name="completeness", score=0.0),
            CritiqueDimension(name="safety", score=0.0),
            CritiqueDimension(name="quality", score=0.0),
            CritiqueDimension(name="efficiency", score=0.0),
        ]

        critique = SelfCritique(
            id=critique_id,
            task_description=task_description,
            dimensions=dimensions,
            threshold=threshold,
            created_at=now,
        )
        self._critiques.append(critique)
        self._save_critique(critique)

        log.info("[SelfCritique] Created evaluation for: %s", task_description[:100])
        return critique

    def update_dimension(
        self,
        critique_id: str,
        dimension_name: str,
        score: float,
        issues: List[str] = None,
        recommendations: List[str] = None,
    ) -> bool:
        """Update a critique dimension with actual scores."""
        critique = next((c for c in self._critiques if c.id == critique_id), None)
        if not critique:
            return False

        for dim in critique.dimensions:
            if dim.name == dimension_name:
                dim.score = score
                if issues:
                    dim.issues = issues
                if recommendations:
                    dim.recommendations = recommendations
                break

        # Calculate overall score
        if critique.dimensions:
            critique.overall_score = sum(d.score for d in critique.dimensions) / len(critique.dimensions)
            critique.passed = critique.overall_score >= critique.threshold

            # Collect all recommendations
            critique.recommendations = []
            for dim in critique.dimensions:
                critique.recommendations.extend(dim.recommendations)

        self._save_critique(critique)
        return True

    def get_critique_prompt(self, critique_id: str) -> str:
        """Get a prompt for the LLM to fill in critique scores."""
        critique = next((c for c in self._critiques if c.id == critique_id), None)
        if not critique:
            return "Critique not found."

        return f"""You are evaluating your own work. Be honest and critical.

## Task
{critique.task_description}

## Evaluation Dimensions

For each dimension, provide:
1. **Score** (0.0-1.0): How well does the work meet this criterion?
2. **Issues**: List any problems found (empty if none)
3. **Recommendations**: Suggest improvements (empty if none)

### Dimensions to Evaluate:

1. **Correctness**: Does the solution actually solve the problem?
   - Are there logic errors?
   - Does it handle edge cases?
   - Are there off-by-one errors or boundary issues?

2. **Completeness**: Are all requirements met?
   - Are there missing features?
   - Are all test cases covered?
   - Is error handling complete?

3. **Safety**: Are there security or stability risks?
   - Any injection vulnerabilities?
   - Are there data exposure risks?
   - Could this cause system instability?

4. **Quality**: Does it meet code standards?
   - Is the code readable and maintainable?
   - Are there code smells or anti-patterns?
   - Does it follow project conventions?

5. **Efficiency**: Is it performant and maintainable?
   - Are there performance bottlenecks?
   - Is the algorithm optimal?
   - Could it be simplified?

## Threshold
Overall score must be >= {critique.threshold} to pass.

Provide your evaluation as structured JSON:
```json
{{
  "correctness": {{"score": 0.0, "issues": [], "recommendations": []}},
  "completeness": {{"score": 0.0, "issues": [], "recommendations": []}},
  "safety": {{"score": 0.0, "issues": [], "recommendations": []}},
  "quality": {{"score": 0.0, "issues": [], "recommendations": []}},
  "efficiency": {{"score": 0.0, "issues": [], "recommendations": []}}
}}
```
"""

    def get_stats(self) -> Dict[str, Any]:
        """Get self-critique statistics."""
        if not self._critiques:
            return {"total_critiques": 0, "passed": 0, "failed": 0, "avg_score": 0.0}

        total = len(self._critiques)
        passed = sum(1 for c in self._critiques if c.passed)
        failed = total - passed
        avg_score = sum(c.overall_score for c in self._critiques) / total if total > 0 else 0.0

        return {
            "total_critiques": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total * 100, 1) if total > 0 else 0.0,
            "avg_score": round(avg_score, 2),
            "recent_critiques": [
                {
                    "id": c.id,
                    "task": c.task_description[:100],
                    "score": c.overall_score,
                    "passed": c.passed,
                    "created_at": c.created_at,
                }
                for c in self._critiques[-5:]
            ],
        }


# Global evaluator instance
_evaluator: Optional[SelfCritiqueEvaluator] = None


def get_self_critique_evaluator(repo_dir: Optional[pathlib.Path] = None) -> SelfCritiqueEvaluator:
    """Get or create the global self-critique evaluator."""
    global _evaluator
    if _evaluator is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _evaluator = SelfCritiqueEvaluator(repo_dir)
    return _evaluator
