"""GStack-style skills system for Jo.

Decomposed into focused modules (Principle 5: Minimalism):
- skill_definitions.py: Skill/SkillRelevance classes, constants, global registries
- skill_logging.py: Activation/outcome tracking, vault export
- skill_selection.py: Detection, evaluation, relevance scoring
- skill_registry.py: Loading, registration, tool handlers, built-in skills

This module re-exports everything for backwards compatibility.
"""

from __future__ import annotations

from ouroboros.tools.skill_definitions import (  # noqa: F401
    SKILLS,
    SKILL_EVOLUTION_SIGNALS,
    SKILL_LOG_PATH,
    TRIGGERS,
    Skill,
    SkillRelevance,
)
from ouroboros.tools.skill_logging import (  # noqa: F401
    _get_skill_log_path,
    export_skill_outcomes_to_vault,
    get_skill_stats,
    get_skill_success_rates,
    log_skill_activation,
    log_skill_outcome,
)
from ouroboros.tools.skill_registry import (  # noqa: F401
    _activate_skill_handler,
    _list_skills_handler,
    ensure_skill_loaded,
    get_all_skills,
    get_loaded_skill_count,
    get_skill,
    get_tools,
    register_skill,
    register_skill_loader,
)
from ouroboros.tools.skill_selection import (  # noqa: F401
    detect_skill_from_text,
    detect_skill_with_triggers,
    evaluate_skill_relevance,
    extract_task_from_skill_text,
    get_best_skill_for_task,
    get_skill_switch_hint,
    score_skill_relevance,
    should_reevaluate,
)
