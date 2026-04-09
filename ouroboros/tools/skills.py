"""
Jo — Skills & Memento Proxy.

Integrates the legacy skill system with the new Memento-Skills architecture in one unified facade.
"""

from __future__ import annotations

import logging
import json
import subprocess
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolContext, ToolEntry

# --- Legacy Skill System Re-exports ---
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
    get_tools as legacy_get_tools,
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

# --- Memento-Skills Integration ---
from ouroboros.skills.repository import get_skill_repository, Skill as MementoSkill
from ouroboros.skills.runtime import load_skill_as_tool, get_dynamic_skills
from ouroboros.hybrid_memory import _hash_to_vector

log = logging.getLogger(__name__)

def _synthesize_and_test_skill(ctx: ToolContext, name: str, description: str, code: str, unit_tests: str, parameters: Optional[Dict[str, Any]] = None) -> str:
    """Synthesize a new skill, run its unit tests, and store if successful."""
    repo = get_skill_repository(ctx.repo_dir)
    
    test_dir = ctx.repo_dir / ".jo_skills" / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    
    skill_temp_path = test_dir / f"{name}_temp.py"
    test_path = test_dir / f"test_{name}.py"
    
    try:
        skill_temp_path.write_text(code, encoding="utf-8")
        test_path.write_text(unit_tests, encoding="utf-8")
        
        res = subprocess.run(
            ["pytest", str(test_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=str(ctx.repo_dir)
        )
        
        output = res.stdout + (f"\n--- STDERR ---\n{res.stderr}" if res.stderr else "")
        if res.returncode == 0:
            new_skill = MementoSkill(
                name=name,
                description=description,
                code=code,
                unit_tests=unit_tests,
                parameters=parameters or {}
            )
            if repo.add_skill(new_skill):
                return f"✅ SUCCESS: Skill '{name}' synthesized, tested, and stored.\nOutput:\n{output}"
            else:
                return f"❌ ERROR: Skill tests passed but failed to store in repository."
        else:
            return f"❌ FAILURE: Skill tests failed. Reflection required.\nOutput:\n{output}"

    except Exception as e:
        return f"⚠️ ERROR during synthesis: {e}"
    finally:
        if skill_temp_path.exists(): skill_temp_path.unlink()
        if test_path.exists(): test_path.unlink()

def _search_skills(ctx: ToolContext, query: str) -> str:
    """Search for skills in the Memento repository based on semantic similarity."""
    repo = get_skill_repository(ctx.repo_dir)
    query_vec = _hash_to_vector(query)
    results = repo.search_skills(query_vec)
    
    if not results:
        return "No matching skills found in Memento repository."
        
    lines = ["## Matching Memento Skills Found:"]
    for skill_info, score in results:
        lines.append(f"- **{skill_info.name}** (Relevance: {score:.2f})")
        lines.append(f"  Description: {skill_info.description}")
        lines.append(f"  Parameters: {json.dumps(skill_info.parameters)}")
        lines.append("")
        
    return "\n".join(lines)


def get_tools() -> List[ToolEntry]:
    """Expose both legacy and Memento tools to the registry."""
    memento_tools = [
        ToolEntry(
            "synthesize_and_test_skill",
            {
                "name": "synthesize_and_test_skill",
                "description": "Create a new executable skill. Generates code, runs unit tests, and saves if successful (Reflect-and-Write loop).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Unique name for the skill (PascalCase)"},
                        "description": {"type": "string", "description": "What the skill does and when to use it"},
                        "code": {"type": "string", "description": "Python code for the skill. Must contain an 'execute' function or a function named after the skill."},
                        "unit_tests": {"type": "string", "description": "Pytest code to verify the skill. Must be a complete test file content."},
                        "parameters": {"type": "object", "description": "JSON schema for the skill's parameters."}
                    },
                    "required": ["name", "description", "code", "unit_tests"]
                }
            },
            _synthesize_and_test_skill,
            is_code_tool=True
        ),
        ToolEntry(
            "search_skills",
            {
                "name": "search_skills",
                "description": "Search for persistent executable skills in the Memento repository.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query describing the capability needed"}
                    },
                    "required": ["query"]
                }
            },
            _search_skills
        )
    ]
    return legacy_get_tools() + memento_tools
