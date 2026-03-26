"""Skill selection — detection, evaluation, and relevance scoring.

Extracted from skills.py to reduce module size (Principle 5: Minimalism).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from ouroboros.tools.skill_definitions import (
    SKILLS,
    SKILL_EVOLUTION_SIGNALS,
    TRIGGERS,
    Skill,
    SkillRelevance,
)
from ouroboros.tools.skill_logging import get_skill_success_rates

log = logging.getLogger(__name__)


def get_best_skill_for_task(task: str, available_skills: Optional[List[str]] = None) -> Optional[str]:
    """Find the best skill for a task based on historical success (VikaasLoop-inspired)."""
    if not task:
        return None

    task_lower = task.lower()
    success_rates = get_skill_success_rates()
    skill_scores: Dict[str, float] = {}

    for skill_name, skill in SKILLS.items():
        if available_skills and skill_name not in available_skills:
            continue

        keyword_score = 0
        if skill.triggers:
            for trigger in skill.triggers:
                if trigger.lower() in task_lower:
                    if any(word.startswith(trigger.lower()) for word in task_lower.split()):
                        keyword_score += 10
                    else:
                        keyword_score += 1

        if keyword_score == 0:
            continue

        history_bonus = 0
        if skill_name in success_rates:
            rate = success_rates[skill_name]
            history_bonus = rate["success_rate"] * 50
            if rate["total_uses"] >= 5:
                history_bonus += 10
            if rate["total_uses"] >= 10:
                history_bonus += 10

        skill_scores[skill_name] = keyword_score + history_bonus

    if not skill_scores:
        return None

    best_skill = max(skill_scores.items(), key=lambda x: x[1])[0]
    log.info(f"Selected skill '{best_skill}' (score: {skill_scores[best_skill]:.1f}) for task: {task[:50]}...")
    return best_skill


def detect_skill_from_text(text: str) -> Optional[Skill]:
    """Detect if text contains a skill command like /plan, /review, /ship, etc."""
    skill, _ = detect_skill_with_triggers(text)
    return skill


def detect_skill_with_triggers(text: str) -> tuple[Optional[Skill], List[str]]:
    """Detect skill with transparency - returns (skill, matched_triggers)."""
    text_lower = text.lower().strip()

    prefixes_to_strip = ["@jo ", "@jo\n", "jo ", "jo\n"]
    for prefix in prefixes_to_strip:
        if text_lower.startswith(prefix):
            text_lower = text_lower[len(prefix) :]
            text = text[len(prefix) :]
            break

    for trigger, skill_name in TRIGGERS.items():
        trigger_lower = trigger.lower()
        if text_lower.startswith(trigger_lower + " ") or text_lower.startswith(trigger_lower + "\n"):
            skill = SKILLS.get(skill_name)
            if skill:
                return skill, [trigger]
        if text_lower == trigger_lower:
            skill = SKILLS.get(skill_name)
            if skill:
                return skill, [trigger]

    skill_scores: Dict[str, int] = {}
    matched_triggers_map: Dict[str, List[str]] = {}

    for skill in SKILLS.values():
        if skill.triggers:
            score = 0
            matched_triggers = []
            for trigger in skill.triggers:
                trigger_lower = trigger.lower()
                if trigger_lower in text_lower:
                    matched_triggers.append(trigger)
                    if any(word.startswith(trigger_lower) for word in text_lower.split()):
                        score += 10
                    else:
                        score += 1
            if score > 0:
                skill_scores[skill.name] = score
                matched_triggers_map[skill.name] = matched_triggers

    if skill_scores:
        best_skill_name = max(skill_scores.items(), key=lambda x: x[1])[0]
        best_skill = SKILLS.get(best_skill_name)
        triggers = matched_triggers_map.get(best_skill_name, [])
        log.info(f"Auto-detected skill '{best_skill_name}' from keywords (matched: {triggers})")
        return best_skill, triggers

    return None, []


def extract_task_from_skill_text(text: str, skill: Skill) -> str:
    """Extract the task description from skill-annotated text."""
    text_lower = text.lower().strip()

    prefixes_to_strip = ["@jo ", "@jo\n", "jo ", "jo\n"]
    for prefix in prefixes_to_strip:
        if text_lower.startswith(prefix):
            text = text[len(prefix) :]
            text_lower = text_lower[len(prefix) :]
            break

    for alias in skill.aliases:
        alias_lower = alias.lower()
        if text_lower.startswith(alias_lower):
            task_text = text[len(alias) :].strip()
            return task_text if task_text else ""

    return text


def score_skill_relevance(skill: Skill, context: Dict[str, Any]) -> float:
    """Score how relevant a skill is to the current context."""
    score = 0.0
    signals = SKILL_EVOLUTION_SIGNALS.get(skill.name, [])

    if not signals:
        return 0.5

    task_text = context.get("task_text", "").lower()
    response_text = context.get("recent_responses", [])
    if isinstance(response_text, list):
        response_text = " ".join(response_text).lower()
    else:
        response_text = str(response_text).lower()

    combined = task_text + " " + response_text

    signal_matches = sum(1 for signal in signals if signal in combined)
    max_signals = len(signals)
    score = signal_matches / max_signals if max_signals > 0 else 0.0

    strong_keywords = {
        "plan": ["architecture", "design", "rethink"],
        "review": ["bug", "error", "crash"],
        "ship": ["ready", "deploy", "done"],
        "qa": ["test", "verify", "click"],
        "retro": ["metrics", "velocity", "stats"],
        "evolve": ["refactor", "improve", "enhance"],
    }

    strong_matches = strong_keywords.get(skill.name, [])
    if any(kw in combined for kw in strong_matches):
        score = min(1.0, score + 0.2)

    conflicting_skills = {
        "plan": ["fix", "bug", "error", "test", "deploy"],
        "review": ["design", "architecture", "strategy"],
        "ship": ["design", "architecture", "plan"],
        "qa": ["architecture", "design", "strategy"],
    }

    conflicts = conflicting_skills.get(skill.name, [])
    conflict_matches = sum(1 for c in conflicts if c in combined)
    score -= conflict_matches * 0.1

    return max(0.0, min(1.0, score))


def evaluate_skill_relevance(
    current_skill: Optional[Skill],
    context: Dict[str, Any],
    reevaluation_threshold: float = 0.3,
) -> SkillRelevance:
    """Evaluate if current skill is still relevant or if we should switch."""
    if current_skill is None:
        best_skill = None
        best_score = 0.0

        for skill in SKILLS.values():
            score = score_skill_relevance(skill, context)
            if score > best_score:
                best_score = score
                best_skill = skill

        if best_skill and best_score > 0.4:
            return SkillRelevance(
                skill=best_skill,
                score=best_score,
                reason=f"Auto-detected skill '{best_skill.name}' (score: {best_score:.2f})",
                should_switch=True,
            )
        return SkillRelevance(
            skill=None,
            score=0.0,
            reason="No skill relevant",
            should_switch=False,
        )

    current_score = score_skill_relevance(current_skill, context)

    if current_score >= 0.5:
        return SkillRelevance(
            skill=current_skill,
            score=current_score,
            reason=f"Current skill '{current_skill.name}' still relevant ({current_score:.2f})",
            should_switch=False,
        )

    best_alternative = None
    best_alternative_score = 0.0

    for skill in SKILLS.values():
        if skill.name == current_skill.name:
            continue
        score = score_skill_relevance(skill, context)
        if score > best_alternative_score:
            best_alternative_score = score
            best_alternative = skill

    if best_alternative and (best_alternative_score - current_score) >= reevaluation_threshold:
        return SkillRelevance(
            skill=best_alternative,
            score=best_alternative_score,
            reason=f"Switch from '{current_skill.name}' ({current_score:.2f}) to '{best_alternative.name}' ({best_alternative_score:.2f})",
            should_switch=True,
        )

    return SkillRelevance(
        skill=current_skill,
        score=current_score,
        reason=f"Current skill '{current_skill.name}' declining ({current_score:.2f}) but no better alternative",
        should_switch=False,
    )


def should_reevaluate(round_idx: int, tool_call_count: int, last_reevaluation: int) -> bool:
    """Determine if we should re-evaluate the current skill."""
    if round_idx - last_reevaluation >= 5:
        return True
    if tool_call_count % 10 == 0 and tool_call_count > 0:
        return True
    return False


def get_skill_switch_hint(relevance: SkillRelevance) -> str:
    """Generate a system message hint for skill switching."""
    if not relevance.should_switch or relevance.skill is None:
        return ""

    return f"""[SKILL RE-EVALUATION] Task focus appears to have evolved.

Current skill context no longer optimal.
Suggested skill: {relevance.skill.name.upper()}

Reason: {relevance.reason}

To activate: Use this context with {relevance.skill.name} approach."""
