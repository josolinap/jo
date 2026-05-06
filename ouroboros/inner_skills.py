"""
Inner Skills — cognitive operations that run inside the LLM loop.

Unlike task-facing skills (plan, review, ship), inner skills are lightweight
reasoning operations that execute BEFORE tool calls to improve decision quality.

Inspired by: Tree-of-Thought, Self-Refine, and deliberative AI patterns.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

log = logging.getLogger(__name__)


class InnerSkillType(Enum):
    DELIBERATE = "deliberate"
    CRITIQUE = "critique"
    ASSUMPTIONS = "assumptions"
    SYNTHESIZE = "synthesize"
    VALIDATE = "validate"
    REFLECT = "reflect"
    DECOMPOSE = "decompose"
    PRIORITIZE = "prioritize"


@dataclass
class InnerSkill:
    name: str
    skill_type: InnerSkillType
    description: str
    prompt_template: str
    cost_tier: str = "low"  # low/medium/high
    max_tokens: int = 500
    enabled: bool = True
    triggers: List[str] = field(default_factory=list)


@dataclass
class InnerSkillResult:
    skill_name: str
    output: str
    duration_ms: float = 0.0
    tokens_estimated: int = 0


# Core inner skill definitions
INNER_SKILLS: Dict[str, InnerSkill] = {
    "pros_cons": InnerSkill(
        name="pros_cons",
        skill_type=InnerSkillType.DELIBERATE,
        description="Analyze pros and cons of each approach before acting",
        prompt_template=(
            "Before proceeding, analyze the pros and cons of the approach:\n"
            "Task: {task}\n"
            "Proposed action: {action}\n\n"
            "List top 3 pros and top 3 cons. Be concise."
        ),
        cost_tier="low",
        max_tokens=300,
        triggers=["decide", "choose", "approach", "option", "strategy"],
    ),
    "assumption_check": InnerSkill(
        name="assumption_check",
        skill_type=InnerSkillType.ASSUMPTIONS,
        description="Surface hidden assumptions before execution",
        prompt_template=(
            "What assumptions am I making about: {topic}?\nList the top 3 assumptions and flag which could be wrong."
        ),
        cost_tier="low",
        max_tokens=250,
        triggers=["assume", "presume", "plan", "expect", "suppose"],
    ),
    "pre_mortem": InnerSkill(
        name="pre_mortem",
        skill_type=InnerSkillType.CRITIQUE,
        description="Imagine the plan failed — diagnose why before acting",
        prompt_template=(
            "Imagine this approach failed completely. What are the most likely reasons?\n"
            "Task: {task}\n"
            "Approach: {action}\n\n"
            "List top 3 failure modes and how to prevent each."
        ),
        cost_tier="medium",
        max_tokens=400,
        triggers=["risk", "danger", "critical", "important", "careful", "sensitive"],
    ),
    "multi_perspective": InnerSkill(
        name="multi_perspective",
        skill_type=InnerSkillType.DELIBERATE,
        description="Analyze from multiple expert perspectives",
        prompt_template=(
            "Analyze this from 4 perspectives:\n"
            "Task: {task}\n\n"
            "1. Engineer (implementation): \n"
            "2. Architect (design): \n"
            "3. Security (safety): \n"
            "4. User (experience): \n\n"
            "Be brief — one sentence each."
        ),
        cost_tier="medium",
        max_tokens=400,
        triggers=["complex", "design", "architecture", "system", "refactor"],
    ),
    "consensus_check": InnerSkill(
        name="consensus_check",
        skill_type=InnerSkillType.SYNTHESIZE,
        description="Find consensus between conflicting analyses",
        prompt_template=(
            "Given these viewpoints:\n{viewpoints}\n\nWhat do they agree on? What's the best path forward? Be concise."
        ),
        cost_tier="medium",
        max_tokens=350,
        triggers=["conflict", "disagree", "multiple", "options", "contradict"],
    ),
    "validate_plan": InnerSkill(
        name="validate_plan",
        skill_type=InnerSkillType.VALIDATE,
        description="Pre-execution validation of the planned approach",
        prompt_template=(
            "Validate this plan before execution:\n"
            "Task: {task}\n"
            "Plan: {action}\n\n"
            "Check: (1) Does it actually solve the task? (2) Are there simpler approaches? "
            "(3) What edge cases are missed? Be brief."
        ),
        cost_tier="low",
        max_tokens=300,
        triggers=["implement", "execute", "build", "create", "write"],
    ),
    "decompose_task": InnerSkill(
        name="decompose_task",
        skill_type=InnerSkillType.DECOMPOSE,
        description="Break complex task into ordered sub-steps",
        prompt_template=(
            "Break this task into ordered sub-steps:\n"
            "Task: {task}\n\n"
            "List each step with: (1) what to do, (2) what tool to use, (3) expected output. "
            "Maximum 6 steps."
        ),
        cost_tier="low",
        max_tokens=400,
        triggers=["complex", "large", "multiple", "several", "many"],
    ),
    "prioritize_actions": InnerSkill(
        name="prioritize_actions",
        skill_type=InnerSkillType.PRIORITIZE,
        description="Rank possible actions by value and risk",
        prompt_template=(
            "Rank these possible actions by value vs risk:\n"
            "Task: {task}\n"
            "Options: {action}\n\n"
            "Order from highest-value/lowest-risk to lowest-value/highest-risk. "
            "Recommend which to do first."
        ),
        cost_tier="low",
        max_tokens=300,
        triggers=["priority", "order", "sequence", "first", "best"],
    ),
}


def detect_inner_skills(task_text: str, tool_calls: Optional[List[Dict]] = None) -> List[InnerSkill]:
    """Detect which inner skills should activate based on task text and planned tool calls."""
    text_lower = task_text.lower()
    active = []

    for skill in INNER_SKILLS.values():
        if not skill.enabled:
            continue
        score = 0
        for trigger in skill.triggers:
            if trigger.lower() in text_lower:
                score += 10 if any(w.startswith(trigger.lower()) for w in text_lower.split()) else 1
        if score > 0:
            active.append(skill)

    # Cap at 3 inner skills per round to control cost
    active.sort(key=lambda s: sum(1 for t in s.triggers if t.lower() in text_lower), reverse=True)
    return active[:3]


def run_inner_skill(
    skill: InnerSkill,
    task_text: str,
    action_text: str = "",
    viewpoints: str = "",
    llm_chat_fn: Optional[Callable] = None,
) -> InnerSkillResult:
    """Execute a single inner skill. Returns result with output text."""
    start = time.time()

    # Build prompt from template
    prompt = skill.prompt_template.format(
        task=task_text[:500],
        action=action_text[:500],
        topic=task_text[:300],
        viewpoints=viewpoints[:1000],
    )

    if llm_chat_fn:
        try:
            response = llm_chat_fn(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=skill.max_tokens,
            )
            output = response.get("content", "") if response else ""
        except Exception as e:
            log.warning(f"[InnerSkill] {skill.name} failed: {e}")
            output = f"[Inner skill {skill.name} failed: {e}]"
    else:
        # Fallback: return prompt as output (will be visible to main LLM)
        output = f"[{skill.name.upper()}] Consider: {prompt}"

    duration_ms = (time.time() - start) * 1000
    tokens_est = len(output) // 4

    return InnerSkillResult(
        skill_name=skill.name,
        output=output,
        duration_ms=duration_ms,
        tokens_estimated=tokens_est,
    )


def execute_inner_skills_batch(
    task_text: str,
    tool_calls: Optional[List[Dict]] = None,
    action_text: str = "",
    llm_chat_fn: Optional[Callable] = None,
) -> List[InnerSkillResult]:
    """Detect and execute all relevant inner skills in a batch."""
    skills = detect_inner_skills(task_text, tool_calls)
    if not skills:
        return []

    results = []
    for skill in skills:
        result = run_inner_skill(skill, task_text, action_text, llm_chat_fn=llm_chat_fn)
        results.append(result)
        log.info(
            f"[InnerSkill] {skill.name} ({skill.skill_type.value}): "
            f"{result.duration_ms:.0f}ms, ~{result.tokens_estimated} tokens"
        )

    return results


def format_inner_skill_results(results: List[InnerSkillResult]) -> str:
    """Format inner skill results for injection into the LLM message stream."""
    if not results:
        return ""

    lines = ["[Inner Skills Analysis]"]
    for r in results:
        lines.append(f"\n--- {r.skill_name} ---")
        lines.append(r.output)

    return "\n".join(lines)
