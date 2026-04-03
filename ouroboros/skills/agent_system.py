"""
Jo — Specialized Agent System.

19 specialized agents organized into 4 lanes, inspired by oh-my-claudecode.
Each agent has a clear role, default model tier, and specific capabilities.

Lanes:
1. Build/Analysis: explore, analyst, planner, architect, debugger, executor, verifier, tracer
2. Review: security-reviewer, code-reviewer
3. Domain: test-engineer, designer, writer, qa-tester, scientist, git-master, document-specialist, code-simplifier
4. Coordination: critic (gap analysis)

Model routing:
- FAST: Quick lookups and simple tasks
- BALANCED: Code implementation, debugging, testing
- DEEP: Architecture, strategic analysis, review
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ModelTier(Enum):
    """Model tier for agent routing."""

    FAST = "fast"  # Quick, inexpensive tasks
    BALANCED = "balanced"  # General purpose
    DEEP = "deep"  # Complex reasoning


class AgentLane(Enum):
    """Agent lane categorization."""

    BUILD_ANALYSIS = "build_analysis"
    REVIEW = "review"
    DOMAIN = "domain"
    COORDINATION = "coordination"


@dataclass
class JoAgent:
    """A specialized agent definition."""

    name: str
    role: str
    description: str
    lane: AgentLane
    model_tier: ModelTier
    capabilities: List[str] = field(default_factory=list)
    does_not: List[str] = field(default_factory=list)  # What this agent does NOT do


# Define all 19 specialized agents
SPECIALIZED_AGENTS: List[JoAgent] = [
    # Build/Analysis Lane
    JoAgent(
        name="explore",
        role="Codebase Discovery",
        description="Fast codebase exploration, file/symbol mapping, and structure analysis",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.FAST,
        capabilities=["file discovery", "symbol mapping", "code navigation", "structure analysis"],
        does_not=["requirements gathering", "planning"],
    ),
    JoAgent(
        name="analyst",
        role="Requirements Analysis",
        description="Deep requirements analysis, hidden constraint discovery, and gap identification",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.DEEP,
        capabilities=["requirements analysis", "constraint discovery", "gap identification", "stakeholder analysis"],
        does_not=["code analysis", "planning"],
    ),
    JoAgent(
        name="planner",
        role="Task Sequencing",
        description="Create execution plans, task sequencing, and dependency mapping",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.DEEP,
        capabilities=["task planning", "dependency mapping", "execution sequencing", "risk assessment"],
        does_not=["requirements analysis", "plan review"],
    ),
    JoAgent(
        name="architect",
        role="System Design",
        description="System architecture, interface definition, and trade-off analysis",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.DEEP,
        capabilities=[
            "system design",
            "interface definition",
            "trade-off analysis",
            "code analysis",
            "debugging",
            "verification",
        ],
        does_not=["requirements gathering", "planning"],
    ),
    JoAgent(
        name="debugger",
        role="Root Cause Analysis",
        description="Debugging, root-cause analysis, and build error resolution",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.BALANCED,
        capabilities=["root cause analysis", "error resolution", "debugging", "hypothesis testing"],
        does_not=["requirements analysis", "planning"],
    ),
    JoAgent(
        name="executor",
        role="Code Implementation",
        description="Code implementation, refactoring, and feature development",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.BALANCED,
        capabilities=["code implementation", "refactoring", "feature development", "bug fixes"],
        does_not=["requirements analysis", "architecture design"],
    ),
    JoAgent(
        name="verifier",
        role="Completion Verification",
        description="Verify task completion, test adequacy, and quality confirmation",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.BALANCED,
        capabilities=["completion verification", "test validation", "quality confirmation", "evidence gathering"],
        does_not=["code implementation", "planning"],
    ),
    JoAgent(
        name="tracer",
        role="Causal Tracing",
        description="Evidence-driven causal tracing and competing hypothesis analysis",
        lane=AgentLane.BUILD_ANALYSIS,
        model_tier=ModelTier.BALANCED,
        capabilities=["causal analysis", "hypothesis testing", "evidence gathering", "root cause tracing"],
        does_not=["code implementation", "planning"],
    ),
    # Review Lane
    JoAgent(
        name="security_reviewer",
        role="Security Review",
        description="Security vulnerability analysis, trust boundary review, and authn/authz audit",
        lane=AgentLane.REVIEW,
        model_tier=ModelTier.BALANCED,
        capabilities=["security analysis", "vulnerability detection", "auth review", "trust boundary analysis"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="code_reviewer",
        role="Code Review",
        description="Comprehensive code review, API contract validation, and backward compatibility check",
        lane=AgentLane.REVIEW,
        model_tier=ModelTier.DEEP,
        capabilities=["code review", "API contract validation", "backward compatibility", "best practices"],
        does_not=["code implementation", "requirements analysis"],
    ),
    # Domain Lane
    JoAgent(
        name="test_engineer",
        role="Test Strategy",
        description="Test strategy development, coverage analysis, and flaky-test hardening",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["test strategy", "coverage analysis", "test generation", "flaky test detection"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="designer",
        role="UI/UX Architecture",
        description="UI/UX architecture, interaction design, and visual consistency",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["UI design", "UX architecture", "interaction design", "visual consistency"],
        does_not=["backend implementation", "requirements analysis"],
    ),
    JoAgent(
        name="writer",
        role="Documentation",
        description="Documentation writing, migration notes, and user guides",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.FAST,
        capabilities=["documentation", "migration notes", "user guides", "API docs"],
        does_not=["code implementation", "architecture design"],
    ),
    JoAgent(
        name="qa_tester",
        role="Runtime Validation",
        description="Interactive CLI/service runtime validation and end-to-end testing",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["runtime validation", "E2E testing", "CLI testing", "service testing"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="scientist",
        role="Data Analysis",
        description="Data analysis, statistical research, and experimental validation",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["data analysis", "statistical research", "experiment design", "result interpretation"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="git_master",
        role="Git Operations",
        description="Git operations, commits, rebase, branch management, and history cleanup",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["git operations", "commits", "rebase", "branch management", "history cleanup"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="document_specialist",
        role="External Documentation",
        description="External documentation research, API/SDK reference lookup, and knowledge synthesis",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.BALANCED,
        capabilities=["documentation research", "API lookup", "SDK reference", "knowledge synthesis"],
        does_not=["code implementation", "requirements analysis"],
    ),
    JoAgent(
        name="code_simplifier",
        role="Code Clarity",
        description="Code simplification, clarity improvement, and maintainability enhancement",
        lane=AgentLane.DOMAIN,
        model_tier=ModelTier.DEEP,
        capabilities=["code simplification", "clarity improvement", "maintainability", "refactoring"],
        does_not=["code implementation", "requirements analysis"],
    ),
    # Coordination Lane
    JoAgent(
        name="critic",
        role="Gap Analysis",
        description="Challenge plans and designs, multi-angle review, and gap identification",
        lane=AgentLane.COORDINATION,
        model_tier=ModelTier.DEEP,
        capabilities=["gap analysis", "plan review", "design critique", "multi-angle review"],
        does_not=["requirements analysis", "code analysis", "code implementation"],
    ),
]


class AgentRouter:
    """Routes tasks to appropriate specialized agents."""

    def __init__(self):
        self._agents = {a.name: a for a in SPECIALIZED_AGENTS}
        self._keyword_map = self._build_keyword_map()

    def _build_keyword_map(self) -> Dict[str, str]:
        """Build a mapping from keywords to agent names."""
        keyword_map = {}

        # Build/Analysis keywords
        keyword_map.update(
            {
                "explore": "explore",
                "discover": "explore",
                "find": "explore",
                "search": "explore",
                "analyze": "analyst",
                "requirements": "analyst",
                "constraint": "analyst",
                "plan": "planner",
                "sequence": "planner",
                "dependency": "planner",
                "architect": "architect",
                "design": "architect",
                "system": "architect",
                "debug": "debugger",
                "error": "debugger",
                "root cause": "debugger",
                "implement": "executor",
                "refactor": "executor",
                "feature": "executor",
                "verify": "verifier",
                "confirm": "verifier",
                "completion": "verifier",
                "trace": "tracer",
                "causal": "tracer",
                "hypothesis": "tracer",
            }
        )

        # Review keywords
        keyword_map.update(
            {
                "security": "security_reviewer",
                "vulnerability": "security_reviewer",
                "auth": "security_reviewer",
                "review": "code_reviewer",
                "code review": "code_reviewer",
                "api contract": "code_reviewer",
                "backward compat": "code_reviewer",
            }
        )

        # Domain keywords
        keyword_map.update(
            {
                "test": "test_engineer",
                "coverage": "test_engineer",
                "flaky": "test_engineer",
                "ui": "designer",
                "ux": "designer",
                "design": "designer",
                "document": "writer",
                "doc": "writer",
                "migration": "writer",
                "qa": "qa_tester",
                "runtime": "qa_tester",
                "e2e": "qa_tester",
                "data": "scientist",
                "statistic": "scientist",
                "experiment": "scientist",
                "git": "git_master",
                "commit": "git_master",
                "rebase": "git_master",
                "branch": "git_master",
                "external": "document_specialist",
                "api reference": "document_specialist",
                "sdk": "document_specialist",
                "simplify": "code_simplifier",
                "clarity": "code_simplifier",
                "maintain": "code_simplifier",
            }
        )

        # Coordination keywords
        keyword_map.update(
            {
                "critic": "critic",
                "gap": "critic",
                "challenge": "critic",
                "review plan": "critic",
            }
        )

        return keyword_map

    def route(self, task_description: str) -> List[JoAgent]:
        """Route a task to appropriate agents based on description."""
        task_lower = task_description.lower()
        matched_agents = []
        matched_keywords = []

        # Check for keyword matches
        for keyword, agent_name in self._keyword_map.items():
            if keyword in task_lower:
                agent = self._agents.get(agent_name)
                if agent and agent not in matched_agents:
                    matched_agents.append(agent)
                    matched_keywords.append(keyword)

        # If no keyword matches, return general executor
        if not matched_agents:
            return [self._agents["executor"]]

        # Sort by relevance (more keyword matches first)
        return matched_agents

    def get_agent(self, name: str) -> Optional[JoAgent]:
        """Get a specific agent by name."""
        return self._agents.get(name)

    def list_agents(self) -> List[Dict[str, Any]]:
        """List all available agents."""
        return [
            {
                "name": a.name,
                "role": a.role,
                "description": a.description,
                "lane": a.lane.value,
                "model_tier": a.model_tier.value,
                "capabilities": a.capabilities,
            }
            for a in SPECIALIZED_AGENTS
        ]

    def get_typical_workflow(self) -> List[str]:
        """Get the typical agent workflow sequence."""
        return [
            "explore (discover)",
            "analyst (analyze)",
            "planner (sequence)",
            "critic (review)",
            "executor (implement)",
            "verifier (confirm)",
        ]


# Global router instance
_router: Optional[AgentRouter] = None


def get_agent_router() -> AgentRouter:
    """Get or create the global agent router."""
    global _router
    if _router is None:
        _router = AgentRouter()
    return _router
