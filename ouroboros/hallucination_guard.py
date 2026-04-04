"""
Ouroboros — Hallucination Guard.

Rejects responses that claim task completion but performed zero tool calls.
Inspired by GSD-2's hallucination guard pattern.

Prevents the LLM from producing fabricated summaries without actually doing work.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

COMPLETION_PATTERNS = [
    r"(?i)\b(task|work|implementation)\s+(is\s+)?(complete|done|finished|resolved)\b",
    r"(?i)\b(completed|finished|resolved|fixed)\s+(the|this)\s+(task|issue|bug|feature)\b",
    r"(?i)\bhas\s+been\s+(implemented|fixed|resolved|completed|addressed)\b",
    r"(?i)\ball\s+(requirements?|criteria|objectives?)\s+(met|satisfied|fulfilled)\b",
    r"(?i)\b(successfully)\s+(implemented|fixed|resolved|completed|deployed)\b",
    r"(?i)^✅\s",
    r"(?i)\bsummary\s*:\s*\n.*\b(complete|done|fixed|resolved)\b",
]

FALSE_POSITIVE_PATTERNS = [
    r"(?i)\bwill\s+be\s+(complete|done|finished)\b",
    r"(?i)\bshould\s+be\s+(complete|done|finished)\b",
    r"(?i)\bnot\s+yet\s+(complete|done|finished)\b",
    r"(?i)\bpartially\s+(complete|done|finished)\b",
    r"(?i)\bin\s+progress\b",
    r"(?i)\bnext\s+step\b",
]


@dataclass
class GuardResult:
    is_hallucinated: bool
    confidence: float  # 0.0 to 1.0
    reason: str
    tool_calls_made: int
    completion_claims: List[str] = field(default_factory=list)


class HallucinationGuard:
    """Detects and rejects hallucinated task completions."""

    def __init__(self):
        # Load configuration
        try:
            from ouroboros.config_manager import get_config_manager

            config = get_config_manager().as_dict()
            guard_config = config.get("hallucination_guard", {})
            self._enabled = guard_config.get("enabled", True)
            self._confidence_threshold = guard_config.get("confidence_threshold", 0.7)
        except Exception:
            self._enabled = True
            self._confidence_threshold = 0.7

        self._completion_re = [re.compile(p) for p in COMPLETION_PATTERNS]
        self._false_positive_re = [re.compile(p) for p in FALSE_POSITIVE_PATTERNS]
        self._stats = {"total_checked": 0, "hallucinations_detected": 0, "false_positives_avoided": 0}

    def check(self, response: str, tool_calls_made: int, task_type: str = "") -> GuardResult:
        self._stats["total_checked"] += 1

        if tool_calls_made > 0:
            return GuardResult(
                is_hallucinated=False,
                confidence=0.0,
                reason="Tool calls were made",
                tool_calls_made=tool_calls_made,
            )

        completion_claims = []
        for pattern in self._completion_re:
            matches = pattern.findall(response)
            if matches:
                completion_claims.extend(matches)

        if not completion_claims:
            return GuardResult(
                is_hallucinated=False,
                confidence=0.0,
                reason="No completion claims detected",
                tool_calls_made=0,
            )

        false_positive_count = 0
        for pattern in self._false_positive_re:
            if pattern.search(response):
                false_positive_count += 1

        if false_positive_count > 0:
            self._stats["false_positives_avoided"] += 1
            return GuardResult(
                is_hallucinated=False,
                confidence=0.3,
                reason=f"Completion claims found but {false_positive_count} false-positive indicators present",
                tool_calls_made=0,
                completion_claims=completion_claims,
            )

        confidence = min(1.0, len(completion_claims) * 0.3 + 0.4)

        if task_type in ("read", "search", "analyze"):
            confidence *= 0.5
            return GuardResult(
                is_hallucinated=False,
                confidence=confidence,
                reason=f"Task type '{task_type}' may legitimately complete without tool calls",
                tool_calls_made=0,
                completion_claims=completion_claims,
            )

        self._stats["hallucinations_detected"] += 1
        return GuardResult(
            is_hallucinated=True,
            confidence=confidence,
            reason=f"Claims completion ({len(completion_claims)} claims) but made 0 tool calls",
            tool_calls_made=0,
            completion_claims=completion_claims,
        )

    def get_rejection_message(self, result: GuardResult) -> str:
        return (
            "⚠️ HALLUCINATION GUARD: Response claims task completion but performed zero tool calls. "
            "This response has been rejected. You must actually execute tools to complete this task. "
            f"Claims detected: {'; '.join(str(c) for c in result.completion_claims[:3])}"
        )

    def stats(self) -> Dict[str, Any]:
        return self._stats.copy()


_guard: Optional[HallucinationGuard] = None


def get_guard() -> HallucinationGuard:
    global _guard
    if _guard is None:
        _guard = HallucinationGuard()
    return _guard


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def hallucination_check(ctx, response: str, tool_calls: int = 0, task_type: str = "") -> str:
        result = get_guard().check(response, tool_calls, task_type)
        if result.is_hallucinated:
            return f"❌ HALLUCINATED (confidence={result.confidence:.0%}): {result.reason}"
        return f"✅ Valid (confidence={result.confidence:.0%}): {result.reason}"

    def hallucination_stats(ctx) -> str:
        import json

        return json.dumps(get_guard().stats(), indent=2)

    return [
        ToolEntry(
            "hallucination_check",
            {
                "name": "hallucination_check",
                "description": "Check if a response is potentially hallucinated (claims completion without tool calls).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "response": {"type": "string", "description": "The response text to check"},
                        "tool_calls": {"type": "integer", "default": 0, "description": "Number of tool calls made"},
                        "task_type": {
                            "type": "string",
                            "default": "",
                            "description": "Task type (read/search/analyze)",
                        },
                    },
                    "required": ["response"],
                },
            },
            hallucination_check,
        ),
        ToolEntry(
            "hallucination_stats",
            {
                "name": "hallucination_stats",
                "description": "Get hallucination guard statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            hallucination_stats,
        ),
    ]
