"""Decision tracer — track WHY decisions were made.

Inspired by Lazarus's introspection/logit_lens pattern.
Records the full decision flow: context → reasoning → action → outcome.

This lets Jo answer:
- What context influenced this decision?
- What alternatives were considered?
- What was the confidence level?
- What was the outcome?
- What should change next time?

Traces are stored in JSONL for trend analysis.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

TRACE_PATH = "~/.jo_data/logs/decision_traces.jsonl"


@dataclass
class DecisionTrace:
    """A single decision trace."""

    trace_id: str
    timestamp: str
    decision_type: str  # tool_use, evolution, consciousness, skill_activation
    context_summary: str  # What context was available
    action_taken: str  # What was done
    confidence: float  # 0.0-1.0
    reasoning: str  # Why this action was chosen
    alternatives: List[str] = field(default_factory=list)  # What else was considered
    outcome: Optional[str] = None  # pass/fail/partial
    outcome_detail: str = ""
    duration_sec: float = 0.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "ts": self.timestamp,
            "type": self.decision_type,
            "context": self.context_summary[:500],
            "action": self.action_taken,
            "confidence": round(self.confidence, 3),
            "reasoning": self.reasoning[:500],
            "alternatives": self.alternatives[:5],
            "outcome": self.outcome,
            "outcome_detail": self.outcome_detail[:200],
            "duration": round(self.duration_sec, 2),
            "tags": self.tags,
        }


class DecisionTracer:
    """Track and analyze decision-making patterns."""

    def __init__(self, trace_path: Optional[str] = None):
        self._path = pathlib.Path(str(pathlib.Path(trace_path or TRACE_PATH).expanduser()))
        self._active_traces: Dict[str, DecisionTrace] = {}

    def start_trace(
        self,
        decision_type: str,
        context_summary: str,
        action_taken: str,
        confidence: float = 0.5,
        reasoning: str = "",
        alternatives: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> str:
        """Start a new decision trace. Returns trace_id for later completion."""
        trace_id = f"tr_{int(time.time() * 1000)}"
        trace = DecisionTrace(
            trace_id=trace_id,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            decision_type=decision_type,
            context_summary=context_summary,
            action_taken=action_taken,
            confidence=confidence,
            reasoning=reasoning,
            alternatives=alternatives or [],
            tags=tags or [],
        )
        self._active_traces[trace_id] = trace
        return trace_id

    def complete_trace(
        self,
        trace_id: str,
        outcome: str,
        outcome_detail: str = "",
    ) -> None:
        """Complete a trace with outcome."""
        if trace_id not in self._active_traces:
            log.warning("Trace %s not found", trace_id)
            return

        trace = self._active_traces.pop(trace_id)
        trace.outcome = outcome  # pass/fail/partial
        trace.outcome_detail = outcome_detail
        trace.duration_sec = time.time() - self._trace_start_time(trace_id)

        self._write_trace(trace)

    def quick_trace(
        self,
        decision_type: str,
        action: str,
        outcome: str,
        confidence: float = 0.5,
        reasoning: str = "",
    ) -> None:
        """Quick trace for simple decisions (start + complete in one call)."""
        trace = DecisionTrace(
            trace_id=f"tr_{int(time.time() * 1000)}",
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
            decision_type=decision_type,
            context_summary="",
            action_taken=action,
            confidence=confidence,
            reasoning=reasoning,
            outcome=outcome,
        )
        self._write_trace(trace)

    def get_decision_report(self, last_n: int = 20) -> str:
        """Generate a decision analysis report."""
        traces = self._load_traces(last_n)
        if not traces:
            return "No decision traces recorded yet."

        total = len(traces)
        passed = sum(1 for t in traces if t.get("outcome") == "pass")
        failed = sum(1 for t in traces if t.get("outcome") == "fail")
        pass_rate = passed / total if total > 0 else 0

        lines = [
            "## Decision Trace Report",
            "",
            f"**Last {total} decisions:** {passed} passed, {failed} failed ({pass_rate:.0%} success)",
        ]

        # By type
        by_type: Dict[str, Dict[str, int]] = {}
        for t in traces:
            dtype = t.get("type", "unknown")
            if dtype not in by_type:
                by_type[dtype] = {"total": 0, "pass": 0, "fail": 0}
            by_type[dtype]["total"] += 1
            outcome = t.get("outcome")
            if outcome in ("pass", "fail"):
                by_type[dtype][outcome] += 1

        if by_type:
            lines.append("\n### By Decision Type")
            for dtype, stats in sorted(by_type.items(), key=lambda x: -x[1]["total"]):
                rate = stats["pass"] / stats["total"] if stats["total"] > 0 else 0
                lines.append(f"- {dtype}: {rate:.0%} success ({stats['total']} decisions)")

        # Low confidence decisions
        low_conf = [t for t in traces if t.get("confidence", 1) < 0.5]
        if low_conf:
            lines.append(f"\n### Low Confidence Decisions ({len(low_conf)})")
            for t in low_conf[:5]:
                lines.append(f"- [{t.get('confidence', 0):.2f}] {t.get('action', '?')} → {t.get('outcome', '?')}")

        # Failed decisions
        failed_traces = [t for t in traces if t.get("outcome") == "fail"]
        if failed_traces:
            lines.append(f"\n### Recent Failures ({len(failed_traces)})")
            for t in failed_traces[:5]:
                lines.append(f"- {t.get('action', '?')}: {t.get('outcome_detail', 'no detail')[:80]}")

        return "\n".join(lines)

    def _write_trace(self, trace: DecisionTrace) -> None:
        """Write trace to JSONL."""
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace.to_dict()) + "\n")
        except Exception as e:
            log.warning("Failed to write trace: %s", e)

    def _load_traces(self, last_n: int = 50) -> List[Dict[str, Any]]:
        """Load recent traces."""
        if not self._path.exists():
            return []
        try:
            lines = self._path.read_text(encoding="utf-8").splitlines()
            traces = []
            for line in lines[-last_n:]:
                if line.strip():
                    traces.append(json.loads(line))
            return traces
        except Exception:
            return []

    @staticmethod
    def _trace_start_time(trace_id: str) -> float:
        """Extract start time from trace_id."""
        try:
            ts_ms = int(trace_id.split("_")[1])
            return ts_ms / 1000
        except Exception:
            return time.time()
