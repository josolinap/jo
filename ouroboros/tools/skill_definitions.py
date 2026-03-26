"""Skill definitions — core classes and constants for the skills system.

Extracted from skills.py to reduce module size (Principle 5: Minimalism).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

# Skill activation log path (can be overridden by environment)
SKILL_LOG_PATH = os.environ.get("SKILL_LOG_PATH", "~/.jo_data/skills_log.json")


@dataclass
class Skill:
    """A specialized cognitive mode that Jo can switch into."""

    name: str
    description: str
    system_prompt_addition: str
    enabled_tools: List[str] = field(default_factory=list)
    pre_task_prompt: str = ""
    post_task_prompt: str = ""
    aliases: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    version: str = "1.0.0"


# Global skill registries
SKILLS: Dict[str, Skill] = {}
TRIGGERS: Dict[str, str] = {}
_SKILL_LOADERS: Dict[str, Any] = {}
_LOADED_SKILLS: Set[str] = set()


@dataclass
class SkillRelevance:
    """How relevant is a skill to the current task state."""

    skill: Optional[Skill]
    score: float  # 0.0 to 1.0
    reason: str
    should_switch: bool


# Keywords that suggest skill evolution
SKILL_EVOLUTION_SIGNALS: Dict[str, List[str]] = {
    "plan": ["architecture", "design", "rethink", "strategy", "product", "vision", "roadmap"],
    "review": ["bug", "error", "fix", "issue", "problem", "security", "performance"],
    "ship": ["ready", "deploy", "release", "push", "merge", "done", "complete"],
    "qa": ["test", "click", "browse", "verify", "check", "ui", "interface"],
    "retro": ["metrics", "velocity", "trend", "stats", "improve", "retrospective"],
    "evolve": ["improve", "refactor", "enhance", "evolution", "grow", "learn"],
}
