"""
Jo — Skills Package.

Advanced skill system inspired by oh-my-claudecode and Claude Code leak analysis.

Components:
- keyword_detector: Magic keyword detection in user prompts
- skill_manager: Skill loading, matching, and injection
- agent_system: 19 specialized agents with model routing
- state_manager: Advanced state management (notepad, project memory, etc.)
- verification: Multi-stage verification protocol with evidence
- dream_system: Background memory consolidation (Claude Code's autoDream)
- coordinator: Multi-agent orchestration (Claude Code's coordinator mode)
- permission_system: Risk classification and permission management
"""

from ouroboros.skills.keyword_detector import KeywordDetector, get_detector
from ouroboros.skills.skill_manager import SkillManager, get_skill_manager
from ouroboros.skills.agent_system import AgentRouter, get_agent_router, SPECIALIZED_AGENTS
from ouroboros.skills.state_manager import StateManager, get_state_manager
from ouroboros.skills.verification import VerificationProtocol, get_verifier
from ouroboros.skills.dream_system import DreamSystem, get_dream_system
from ouroboros.skills.coordinator import CoordinatorMode, get_coordinator
from ouroboros.skills.permission_system import PermissionSystem, get_permission_system

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
    "DreamSystem",
    "get_dream_system",
    "CoordinatorMode",
    "get_coordinator",
    "PermissionSystem",
    "get_permission_system",
]
