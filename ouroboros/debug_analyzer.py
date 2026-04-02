"""
Ouroboros — Debug Analyzer.

Structured retry with debug analysis instead of blind retry.
Inspired by AI-Scientist-v2's debug loop pattern.

Attempts to debug failing code up to max_debug_depth times.
Each attempt analyzes the failure pattern before retrying.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class FailureType(Enum):
    SYNTAX = "syntax"
    IMPORT = "import"
    RUNTIME = "runtime"
    TIMEOUT = "timeout"
    LOGIC = "logic"
    RESOURCE = "resource"
    UNKNOWN = "unknown"


@dataclass
class FailureAnalysis:
    failure_type: FailureType
    error_message: str
    root_cause: str
    suggested_fix: str
    confidence: float
    file_path: str = ""
    line_number: int = 0
    attempt: int = 0
    timestamp: str = ""


@dataclass
class DebugSession:
    session_id: str
    task_description: str
    max_depth: int
    current_attempt: int = 0
    failures: List[FailureAnalysis] = field(default_factory=list)
    resolved: bool = False
    final_error: Optional[str] = None
    started_at: str = ""
    ended_at: str = ""


class DebugAnalyzer:
    """Analyzes failures and attempts structured debugging."""

    def __init__(self, max_depth: int = 3, debug_prob: float = 0.8):
        self.max_depth = max_depth
        self.debug_prob = debug_prob
        self._sessions: Dict[str, DebugSession] = {}
        self._patterns: Dict[str, List[str]] = {
            "syntax": [r"SyntaxError", r"invalid syntax", r"unexpected EOF"],
            "import": [r"ImportError", r"ModuleNotFoundError", r"No module named"],
            "runtime": [r"RuntimeError", r"TypeError", r"ValueError", r"KeyError", r"AttributeError"],
            "timeout": [r"TimeoutError", r"timed out", r"deadline exceeded"],
            "resource": [r"MemoryError", r"OSError", r"disk", r"space"],
        }

    def start_session(self, session_id: str, task_description: str) -> DebugSession:
        session = DebugSession(
            session_id=session_id,
            task_description=task_description,
            max_depth=self.max_depth,
            started_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._sessions[session_id] = session
        return session

    def analyze_failure(
        self, session_id: str, error_message: str, file_path: str = "", line_number: int = 0
    ) -> FailureAnalysis:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found")

        session.current_attempt += 1
        failure_type = self._classify_error(error_message)
        root_cause = self._identify_root_cause(error_message, failure_type)
        suggested_fix = self._suggest_fix(error_message, failure_type, root_cause)

        analysis = FailureAnalysis(
            failure_type=failure_type,
            error_message=error_message[:500],
            root_cause=root_cause,
            suggested_fix=suggested_fix,
            confidence=self._calculate_confidence(failure_type, session.failures),
            file_path=file_path,
            line_number=line_number,
            attempt=session.current_attempt,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        session.failures.append(analysis)

        if session.current_attempt >= session.max_depth:
            session.ended_at = time.strftime("%Y-%m-%dT%H:%M:%S")
            session.final_error = error_message

        return analysis

    def should_retry(self, session_id: str) -> bool:
        session = self._sessions.get(session_id)
        if not session:
            return False
        if session.current_attempt >= session.max_depth:
            return False
        if session.resolved:
            return False
        import random

        return random.random() < self.debug_prob

    def mark_resolved(self, session_id: str) -> str:
        session = self._sessions.get(session_id)
        if not session:
            return f"Session '{session_id}' not found"
        session.resolved = True
        session.ended_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        return f"Session '{session_id}' resolved after {session.current_attempt} attempts"

    def _classify_error(self, error_message: str) -> FailureType:
        error_lower = error_message.lower()
        for ftype_name, patterns in self._patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_message, re.IGNORECASE):
                    return FailureType(ftype_name)
        return FailureType.UNKNOWN

    def _identify_root_cause(self, error_message: str, failure_type: FailureType) -> str:
        if failure_type == FailureType.SYNTAX:
            if "unexpected EOF" in error_message.lower():
                return "Incomplete code - missing closing bracket/quote/indentation"
            return "Syntax error in code structure"
        elif failure_type == FailureType.IMPORT:
            if "no module named" in error_message.lower():
                match = re.search(r"No module named '(\w+)'", error_message)
                if match:
                    return f"Missing dependency: {match.group(1)}"
            return "Import path or dependency issue"
        elif failure_type == FailureType.RUNTIME:
            if "NoneType" in error_message:
                return "Null/None reference - object not initialized"
            if "index" in error_message.lower() or "range" in error_message.lower():
                return "Index out of bounds - collection access issue"
            return "Runtime logic error"
        elif failure_type == FailureType.TIMEOUT:
            return "Operation exceeded time limit"
        elif failure_type == FailureType.RESOURCE:
            return "System resource constraint"
        return "Unknown failure cause"

    def _suggest_fix(self, error_message: str, failure_type: FailureType, root_cause: str) -> str:
        if failure_type == FailureType.SYNTAX:
            return "Check brackets, quotes, and indentation. Ensure all blocks are properly closed."
        elif failure_type == FailureType.IMPORT:
            if "Missing dependency" in root_cause:
                dep = root_cause.split(": ")[-1] if ": " in root_cause else "unknown"
                return f"Install dependency: pip install {dep}"
            return "Verify import path and module existence"
        elif failure_type == FailureType.RUNTIME:
            if "NoneType" in root_cause:
                return "Add null check or initialize object before use"
            return "Add error handling and validate inputs"
        elif failure_type == FailureType.TIMEOUT:
            return "Optimize algorithm or increase timeout limit"
        elif failure_type == FailureType.RESOURCE:
            return "Free resources or increase system limits"
        return "Review error context and add logging"

    def _calculate_confidence(self, failure_type: FailureType, previous_failures: List[FailureAnalysis]) -> float:
        base = 0.7 if failure_type != FailureType.UNKNOWN else 0.3
        if previous_failures:
            same_type_count = sum(1 for f in previous_failures if f.failure_type == failure_type)
            if same_type_count > 1:
                base *= 0.8
        return min(1.0, base)

    def session_summary(self, session_id: str) -> str:
        session = self._sessions.get(session_id)
        if not session:
            return f"Session '{session_id}' not found"
        lines = [
            f"## Debug Session: {session_id}",
            f"- **Task**: {session.task_description[:80]}",
            f"- **Attempts**: {session.current_attempt}/{session.max_depth}",
            f"- **Status**: {'✅ Resolved' if session.resolved else '❌ Unresolved'}",
        ]
        if session.failures:
            lines.append("\n### Failure History")
            for f in session.failures:
                lines.append(f"- Attempt {f.attempt}: [{f.failure_type.value}] {f.root_cause}")
                lines.append(f"  Suggestion: {f.suggested_fix}")
        return "\n".join(lines)

    def global_stats(self) -> Dict[str, Any]:
        total_sessions = len(self._sessions)
        resolved = sum(1 for s in self._sessions.values() if s.resolved)
        by_type = {}
        for s in self._sessions.values():
            for f in s.failures:
                by_type[f.failure_type.value] = by_type.get(f.failure_type.value, 0) + 1
        return {
            "total_sessions": total_sessions,
            "resolved": resolved,
            "resolution_rate": resolved / total_sessions if total_sessions > 0 else 0,
            "failures_by_type": by_type,
            "max_depth": self.max_depth,
            "debug_prob": self.debug_prob,
        }


_analyzer: Optional[DebugAnalyzer] = None


def get_analyzer() -> DebugAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = DebugAnalyzer()
    return _analyzer


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def debug_start(ctx, session_id: str, task: str) -> str:
        analyzer = get_analyzer()
        session = analyzer.start_session(session_id, task)
        return f"Started debug session '{session_id}' (max_depth={session.max_depth})"

    def debug_analyze(ctx, session_id: str, error: str, file_path: str = "") -> str:
        analyzer = get_analyzer()
        analysis = analyzer.analyze_failure(session_id, error, file_path)
        should_retry = analyzer.should_retry(session_id)
        return (
            f"## Failure Analysis (attempt {analysis.attempt})\n"
            f"- **Type**: {analysis.failure_type.value}\n"
            f"- **Root cause**: {analysis.root_cause}\n"
            f"- **Suggested fix**: {analysis.suggested_fix}\n"
            f"- **Confidence**: {analysis.confidence:.0%}\n"
            f"- **Should retry**: {should_retry}"
        )

    def debug_resolved(ctx, session_id: str) -> str:
        return get_analyzer().mark_resolved(session_id)

    def debug_summary(ctx, session_id: str) -> str:
        return get_analyzer().session_summary(session_id)

    def debug_stats(ctx) -> str:
        return json.dumps(get_analyzer().global_stats(), indent=2)

    return [
        ToolEntry(
            "debug_start",
            {
                "name": "debug_start",
                "description": "Start a debug session for structured failure analysis.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Unique session ID"},
                        "task": {"type": "string", "description": "Task being debugged"},
                    },
                    "required": ["session_id", "task"],
                },
            },
            debug_start,
        ),
        ToolEntry(
            "debug_analyze",
            {
                "name": "debug_analyze",
                "description": "Analyze a failure and get suggested fix. Use before retrying.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Debug session ID"},
                        "error": {"type": "string", "description": "Error message"},
                        "file_path": {"type": "string", "default": "", "description": "File where error occurred"},
                    },
                    "required": ["session_id", "error"],
                },
            },
            debug_analyze,
        ),
        ToolEntry(
            "debug_resolved",
            {
                "name": "debug_resolved",
                "description": "Mark a debug session as resolved.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session ID to resolve"},
                    },
                    "required": ["session_id"],
                },
            },
            debug_resolved,
        ),
        ToolEntry(
            "debug_summary",
            {
                "name": "debug_summary",
                "description": "Get summary of a debug session.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "session_id": {"type": "string", "description": "Session ID"},
                    },
                    "required": ["session_id"],
                },
            },
            debug_summary,
        ),
        ToolEntry(
            "debug_stats",
            {
                "name": "debug_stats",
                "description": "Get global debug statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            debug_stats,
        ),
    ]
