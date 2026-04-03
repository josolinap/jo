"""
Jo — Skills Package.

Advanced skill system inspired by oh-my-claudecode.

Components:
- keyword_detector: Magic keyword detection in user prompts
- skill_manager: Skill loading, matching, and injection
- agent_system: 19 specialized agents with model routing
- state_manager: Advanced state management (notepad, project memory, etc.)
- verification: Multi-stage verification protocol with evidence
"""

from ouroboros.skills.keyword_detector import KeywordDetector, get_detector
from ouroboros.skills.skill_manager import SkillManager, get_skill_manager
from ouroboros.skills.agent_system import AgentRouter, get_agent_router, SPECIALIZED_AGENTS
from ouroboros.skills.state_manager import StateManager, get_state_manager
from ouroboros.skills.verification import VerificationProtocol, get_verifier

__all__ = [
    "KeywordDetector",
    "get_detector",
    "SkillManager",
    "get_skill_manager",
    "AgentRouter",
    "get_agent_router",
    "SPECIALIZED_AGENTS",
    "StateManager",
    "get_state_manager",
    "VerificationProtocol",
    "get_verifier",
]
