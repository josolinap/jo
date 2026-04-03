"""
Jo — Magic Keyword Detection System.

Detects magic keywords in user prompts and activates corresponding skills/modes.
Inspired by oh-my-claudecode's keyword detection system.

Keywords trigger automatic behavior injection without explicit commands.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


@dataclass
class KeywordTrigger:
    """A magic keyword trigger definition."""

    name: str
    keywords: List[str]
    description: str
    mode: str  # The mode/skill to activate
    priority: int = 0  # Higher priority triggers first


# Default keyword triggers
DEFAULT_KEYWORD_TRIGGERS: List[KeywordTrigger] = [
    KeywordTrigger(
        name="autopilot",
        keywords=["autopilot", "build me", "i want a", "handle it all", "end to end", "e2e this"],
        description="Full autonomous execution pipeline",
        mode="autopilot",
        priority=10,
    ),
    KeywordTrigger(
        name="ralph",
        keywords=["ralph", "don't stop", "must complete", "until done", "persist"],
        description="Persistent mode - loop until verified complete",
        mode="ralph",
        priority=9,
    ),
    KeywordTrigger(
        name="ultrawork",
        keywords=["ultrawork", "ulw", "uw", "maximum parallel", "burst parallel"],
        description="Maximum parallelism - launch multiple agents simultaneously",
        mode="ultrawork",
        priority=8,
    ),
    KeywordTrigger(
        name="deep_interview",
        keywords=["deep interview", "socratic", "clarify requirements", "vague idea"],
        description="Socratic requirements clarification",
        mode="deep_interview",
        priority=7,
    ),
    KeywordTrigger(
        name="ralplan",
        keywords=["ralplan", "iterative planning", "planning consensus"],
        description="Iterative planning with consensus",
        mode="ralplan",
        priority=6,
    ),
    KeywordTrigger(
        name="ultrathink",
        keywords=["ultrathink", "think hard", "think deeply", "deep reasoning"],
        description="Deep reasoning mode",
        mode="ultrathink",
        priority=5,
    ),
    KeywordTrigger(
        name="deepsearch",
        keywords=["deepsearch", "search the codebase", "find in codebase"],
        description="Codebase-focused search routing",
        mode="deepsearch",
        priority=4,
    ),
    KeywordTrigger(
        name="code_review",
        keywords=["code review", "review code", "review this code"],
        description="Comprehensive code review mode",
        mode="code_review",
        priority=3,
    ),
    KeywordTrigger(
        name="security_review",
        keywords=["security review", "review security", "security audit"],
        description="Security-focused review mode",
        mode="security_review",
        priority=3,
    ),
    KeywordTrigger(
        name="tdd",
        keywords=["tdd", "test first", "red green"],
        description="TDD workflow",
        mode="tdd",
        priority=2,
    ),
    KeywordTrigger(
        name="deslop",
        keywords=["deslop", "anti-slop", "clean ai"],
        description="AI expression cleanup",
        mode="deslop",
        priority=1,
    ),
]


class KeywordDetector:
    """Detects magic keywords in user prompts and returns triggered modes."""

    def __init__(self, triggers: Optional[List[KeywordTrigger]] = None):
        self._triggers = triggers or DEFAULT_KEYWORD_TRIGGERS
        self._compiled_patterns: Dict[str, List[re.Pattern]] = {}
        self._compile_patterns()

    def _compile_patterns(self) -> None:
        """Compile regex patterns for all triggers."""
        for trigger in self._triggers:
            patterns = []
            for keyword in trigger.keywords:
                # Case-insensitive pattern with word boundaries
                pattern = re.compile(r"\b" + re.escape(keyword) + r"\b", re.IGNORECASE)
                patterns.append(pattern)
            self._compiled_patterns[trigger.name] = patterns

    def detect(self, prompt: str) -> List[Dict[str, Any]]:
        """Detect magic keywords in prompt and return triggered modes.

        Returns list of dicts with:
        - name: trigger name
        - mode: mode to activate
        - matched_keyword: the keyword that matched
        - description: trigger description
        - priority: trigger priority
        """
        if not prompt:
            return []

        triggered = []
        # Sort by priority (highest first)
        sorted_triggers = sorted(self._triggers, key=lambda t: t.priority, reverse=True)

        for trigger in sorted_triggers:
            patterns = self._compiled_patterns.get(trigger.name, [])
            for i, pattern in enumerate(patterns):
                match = pattern.search(prompt)
                if match:
                    triggered.append(
                        {
                            "name": trigger.name,
                            "mode": trigger.mode,
                            "matched_keyword": match.group(),
                            "description": trigger.description,
                            "priority": trigger.priority,
                        }
                    )
                    break  # Only one match per trigger

        return triggered

    def get_mode_instructions(self, mode: str) -> str:
        """Get instructions for a specific mode."""
        mode_instructions = {
            "autopilot": """
## Autopilot Mode Activated

You are now in full autonomous execution mode. This means:
1. Take complete ownership of the task from start to finish
2. Plan, implement, test, and verify without asking for permission
3. Use all available tools to complete the work
4. Do not stop until the task is fully complete and verified
5. Report progress at key milestones
""",
            "ralph": """
## Ralph Mode Activated (Persistent)

You are now in persistent mode. This means:
1. You CANNOT stop until the work is verified complete
2. If you attempt to stop, you must continue working
3. Use the verifier agent/tool to confirm completion
4. Only exit when all requirements are met and verified
5. The boulder never stops rolling until the job is done
""",
            "ultrawork": """
## Ultrawork Mode Activated (Maximum Parallelism)

You are now in maximum parallelism mode. This means:
1. Launch multiple agents/tasks simultaneously where possible
2. Break work into independent subtasks and run them in parallel
3. Use task_create for parallel execution
4. Aggregate results when all parallel tasks complete
5. Maximize throughput through parallelization
""",
            "deep_interview": """
## Deep Interview Mode Activated

You are now in Socratic requirements clarification mode. This means:
1. Ask probing questions to clarify the user's vague idea
2. Expose hidden assumptions and unstated requirements
3. Measure clarity across multiple dimensions
4. Help the user crystallize their thinking before execution
5. Do NOT start building until requirements are clear
""",
            "ralplan": """
## Ralplan Mode Activated (Iterative Planning)

You are now in iterative planning consensus mode. This means:
1. Create an initial plan
2. Review it from multiple perspectives (architect, critic, etc.)
3. Iterate until all reviewers approve
4. Only execute after consensus is reached
5. Document decisions and rationale
""",
            "ultrathink": """
## Ultrathink Mode Activated (Deep Reasoning)

You are now in deep reasoning mode. This means:
1. Think through the problem thoroughly before acting
2. Consider multiple approaches and their trade-offs
3. Analyze risks and edge cases
4. Document your reasoning process
5. Only act after thorough analysis
""",
            "deepsearch": """
## Deepsearch Mode Activated (Codebase Search)

You are now in codebase-focused search mode. This means:
1. Thoroughly search the codebase for relevant code
2. Use anatomy_scan, anatomy_search, and repo_read extensively
3. Map out the relevant code structure
4. Understand dependencies and relationships
5. Build a complete picture before proceeding
""",
            "code_review": """
## Code Review Mode Activated

You are now in comprehensive code review mode. This means:
1. Review code for correctness, style, and best practices
2. Check for security vulnerabilities
3. Look for performance issues
4. Suggest improvements and refactoring opportunities
5. Provide detailed feedback with examples
""",
            "security_review": """
## Security Review Mode Activated

You are now in security-focused review mode. This means:
1. Check for common vulnerabilities (OWASP Top 10)
2. Review authentication and authorization logic
3. Check for data exposure risks
4. Look for injection vulnerabilities
5. Review error handling and logging for security issues
""",
            "tdd": """
## TDD Mode Activated (Test-Driven Development)

You are now in TDD workflow mode. This means:
1. Write tests FIRST before implementation
2. Run tests to see them fail (Red)
3. Implement minimal code to pass tests (Green)
4. Refactor while keeping tests passing (Refactor)
5. Repeat for each feature/requirement
""",
            "deslop": """
## Deslop Mode Activated (AI Expression Cleanup)

You are now in AI expression cleanup mode. This means:
1. Remove AI-isms like "I'd be happy to", "Let me", "Great question"
2. Use direct, concise language
3. Avoid filler phrases and unnecessary apologies
4. Get straight to the point
5. Write like a human expert, not an AI assistant
""",
        }
        return mode_instructions.get(mode, f"## {mode.title()} Mode Activated\n\n")

    def build_context_injection(self, prompt: str) -> str:
        """Build context injection string for detected keywords."""
        triggered = self.detect(prompt)
        if not triggered:
            return ""

        parts = ["## Magic Keywords Detected\n"]
        for t in triggered:
            parts.append(f"- **{t['name']}**: {t['description']} (matched: '{t['matched_keyword']}')")
            parts.append(self.get_mode_instructions(t["mode"]))

        return "\n".join(parts)


# Global detector instance
_detector: Optional[KeywordDetector] = None


def get_detector() -> KeywordDetector:
    """Get or create the global keyword detector."""
    global _detector
    if _detector is None:
        _detector = KeywordDetector()
    return _detector
