"""
Ouroboros — Ideation with Reflection.

Generates ideas through multiple reflection steps.
Inspired by AI-Scientist-v2's ideation pattern.

Each idea is refined through reflection before selection.
Generates N approaches, evaluates each, picks best.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Idea:
    idea_id: str
    title: str
    description: str
    approach: str
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reflection_rounds: int = 0
    created_at: str = ""


@dataclass
class ReflectionResult:
    original_idea: Idea
    refined_idea: Idea
    changes: List[str] = field(default_factory=list)
    score_before: float = 0.0
    score_after: float = 0.0


class IdeationEngine:
    """Generates and refines ideas through reflection."""

    def __init__(self):
        self._ideas: Dict[str, Idea] = {}
        self._reflections: List[ReflectionResult] = []

    def generate_idea(
        self,
        idea_id: str,
        title: str,
        description: str,
        approach: str,
        pros: Optional[List[str]] = None,
        cons: Optional[List[str]] = None,
    ) -> Idea:
        idea = Idea(
            idea_id=idea_id,
            title=title,
            description=description,
            approach=approach,
            pros=pros or [],
            cons=cons or [],
            confidence=self._calculate_confidence(pros or [], cons or []),
            created_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._ideas[idea_id] = idea
        return idea

    def reflect(
        self,
        idea_id: str,
        additional_pros: Optional[List[str]] = None,
        additional_cons: Optional[List[str]] = None,
        revised_approach: str = "",
    ) -> ReflectionResult:
        if idea_id not in self._ideas:
            raise ValueError(f"Idea '{idea_id}' not found")

        original = self._ideas[idea_id]
        score_before = original.confidence

        refined = Idea(
            idea_id=original.idea_id,
            title=original.title,
            description=original.description,
            approach=revised_approach or original.approach,
            pros=original.pros + (additional_pros or []),
            cons=original.cons + (additional_cons or []),
            confidence=0.0,
            reflection_rounds=original.reflection_rounds + 1,
            created_at=original.created_at,
        )
        refined.confidence = self._calculate_confidence(refined.pros, refined.cons)

        changes = []
        if revised_approach and revised_approach != original.approach:
            changes.append("Approach revised")
        if additional_pros:
            changes.append(f"Added {len(additional_pros)} pros")
        if additional_cons:
            changes.append(f"Added {len(additional_cons)} cons")

        result = ReflectionResult(
            original_idea=original,
            refined_idea=refined,
            changes=changes,
            score_before=score_before,
            score_after=refined.confidence,
        )

        self._ideas[idea_id] = refined
        self._reflections.append(result)
        return result

    def _calculate_confidence(self, pros: List[str], cons: List[str]) -> float:
        if not pros and not cons:
            return 0.5
        total = len(pros) + len(cons)
        return min(1.0, len(pros) / total + 0.3) if total > 0 else 0.5

    def get_best_idea(self) -> Optional[Idea]:
        if not self._ideas:
            return None
        return max(self._ideas.values(), key=lambda i: i.confidence)

    def compare_ideas(self, idea_ids: List[str]) -> str:
        ideas = [self._ideas[iid] for iid in idea_ids if iid in self._ideas]
        if not ideas:
            return "No ideas found"
        ideas.sort(key=lambda i: -i.confidence)
        lines = ["## Idea Comparison"]
        for i, idea in enumerate(ideas):
            lines.append(f"\n### {i + 1}. {idea.title} (confidence={idea.confidence:.0%})")
            lines.append(f"- **Approach**: {idea.approach[:100]}")
            lines.append(f"- **Reflections**: {idea.reflection_rounds}")
            if idea.pros:
                lines.append(f"- **Pros**: {', '.join(idea.pros[:3])}")
            if idea.cons:
                lines.append(f"- **Cons**: {', '.join(idea.cons[:3])}")
        return "\n".join(lines)

    def summary(self) -> str:
        if not self._ideas:
            return "No ideas generated yet."
        best = self.get_best_idea()
        lines = [
            f"## Ideation Summary ({len(self._ideas)} ideas)",
            f"- **Best**: {best.title} ({best.confidence:.0%})" if best else "",
            f"- **Reflections**: {len(self._reflections)}",
            f"- **Avg confidence**: {sum(i.confidence for i in self._ideas.values()) / len(self._ideas):.0%}",
        ]
        return "\n".join(lines)


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _engines: Dict[str, IdeationEngine] = {}

    def _get_engine(repo_dir) -> IdeationEngine:
        key = str(repo_dir)
        if key not in _engines:
            _engines[key] = IdeationEngine()
        return _engines[key]

    def ideation_generate(
        ctx, idea_id: str, title: str, description: str, approach: str, pros: str = "", cons: str = ""
    ) -> str:
        engine = _get_engine(ctx.repo_dir)
        pros_list = [p.strip() for p in pros.split(",") if p.strip()] if pros else []
        cons_list = [c.strip() for c in cons.split(",") if c.strip()] if cons else []
        idea = engine.generate_idea(idea_id, title, description, approach, pros_list, cons_list)
        return f"Generated idea '{idea_id}': {title} (confidence={idea.confidence:.0%})"

    def ideation_reflect(
        ctx, idea_id: str, additional_pros: str = "", additional_cons: str = "", revised_approach: str = ""
    ) -> str:
        engine = _get_engine(ctx.repo_dir)
        pros_list = [p.strip() for p in additional_pros.split(",") if p.strip()] if additional_pros else []
        cons_list = [c.strip() for c in additional_cons.split(",") if c.strip()] if additional_cons else []
        result = engine.reflect(idea_id, pros_list, cons_list, revised_approach)
        return f"Reflected on '{idea_id}': {', '.join(result.changes)} (confidence: {result.score_before:.0%} → {result.score_after:.0%})"

    def ideation_best(ctx) -> str:
        engine = _get_engine(ctx.repo_dir)
        best = engine.get_best_idea()
        if not best:
            return "No ideas generated yet."
        return f"Best idea: '{best.title}' (confidence={best.confidence:.0%}, reflections={best.reflection_rounds})\nApproach: {best.approach}"

    def ideation_compare(ctx, idea_ids: str) -> str:
        ids = [i.strip() for i in idea_ids.split(",") if i.strip()]
        return _get_engine(ctx.repo_dir).compare_ideas(ids)

    def ideation_summary(ctx) -> str:
        return _get_engine(ctx.repo_dir).summary()

    return [
        ToolEntry(
            "ideation_generate",
            {
                "name": "ideation_generate",
                "description": "Generate a new idea with title, description, and approach.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idea_id": {"type": "string", "description": "Unique idea ID"},
                        "title": {"type": "string", "description": "Idea title"},
                        "description": {"type": "string", "description": "Idea description"},
                        "approach": {"type": "string", "description": "Proposed approach"},
                        "pros": {"type": "string", "default": "", "description": "Comma-separated pros"},
                        "cons": {"type": "string", "default": "", "description": "Comma-separated cons"},
                    },
                    "required": ["idea_id", "title", "description", "approach"],
                },
            },
            ideation_generate,
        ),
        ToolEntry(
            "ideation_reflect",
            {
                "name": "ideation_reflect",
                "description": "Reflect on an idea to refine it. Add pros/cons or revise approach.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idea_id": {"type": "string", "description": "Idea ID to reflect on"},
                        "additional_pros": {
                            "type": "string",
                            "default": "",
                            "description": "Additional pros discovered",
                        },
                        "additional_cons": {
                            "type": "string",
                            "default": "",
                            "description": "Additional cons discovered",
                        },
                        "revised_approach": {"type": "string", "default": "", "description": "Revised approach if any"},
                    },
                    "required": ["idea_id"],
                },
            },
            ideation_reflect,
        ),
        ToolEntry(
            "ideation_best",
            {
                "name": "ideation_best",
                "description": "Get the best idea based on confidence score.",
                "parameters": {"type": "object", "properties": {}},
            },
            ideation_best,
        ),
        ToolEntry(
            "ideation_compare",
            {
                "name": "ideation_compare",
                "description": "Compare multiple ideas side by side.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "idea_ids": {"type": "string", "description": "Comma-separated idea IDs to compare"},
                    },
                    "required": ["idea_ids"],
                },
            },
            ideation_compare,
        ),
        ToolEntry(
            "ideation_summary",
            {
                "name": "ideation_summary",
                "description": "Get summary of all generated ideas.",
                "parameters": {"type": "object", "properties": {}},
            },
            ideation_summary,
        ),
    ]
