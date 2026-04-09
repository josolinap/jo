"""
Skill Runtime for Jo (Memento-Skills).

Handles dynamic execution and tool registration of skills.
"""

from __future__ import annotations

import logging
import importlib.util
import sys
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolContext, ToolEntry
from ouroboros.skills.repository import get_skill_repository, Skill

log = logging.getLogger(__name__)

def load_skill_as_tool(skill: Skill) -> Optional[ToolEntry]:
    """Dynamically load a skill code and wrap it as a ToolEntry."""
    try:
        # Create a module from the code
        module_name = f"jo_skill_{skill.name}"
        spec = importlib.util.spec_from_loader(module_name, loader=None)
        if spec is None:
            return None
            
        module = importlib.util.module_from_spec(spec)
        # Execute the code in the module namespace
        exec(skill.code, module.__dict__)
        
        # We expect a function named 'execute' or similar
        execute_fn = getattr(module, "execute", None)
        if not execute_fn:
            # Fallback to a function named like the skill (snake_case)
            fn_name = skill.name.lower().replace(" ", "_")
            execute_fn = getattr(module, fn_name, None)
            
        if not execute_fn:
            log.warning("Skill %s has no executable entry point (execute or %s)", skill.name, fn_name)
            return None

        # Build parameters schema
        params = skill.parameters or {
            "type": "object",
            "properties": {
                "input": {"type": "string", "description": "Input for the skill"}
            },
            "required": ["input"]
        }

        return ToolEntry(
            name=skill.name,
            definition={
                "name": skill.name,
                "description": skill.description,
                "parameters": params
            },
            func=lambda ctx, **kwargs: execute_fn(**kwargs),
            is_code_tool=True
        )
    except Exception as e:
        log.error("Failed to load skill %s as tool: %s", skill.name, e)
        return None

def get_dynamic_skills(ctx: ToolContext) -> List[ToolEntry]:
    """Retrieve and load relevant skills for the current context."""
    repo = get_skill_repository(ctx.repo_dir)
    
    # In a full implementation, we would use ctx.last_query to search for relevant skills
    # For now, we load all registered skills to ensure they are available
    # Retrieval can be optimized later.
    
    entries = []
    with repo._store._lock:
        repo._store._ensure_loaded()
        for skill in repo._store._facts:
            entry = load_skill_as_tool(skill) # type: ignore
            if entry:
                entries.append(entry)
                
    return entries
