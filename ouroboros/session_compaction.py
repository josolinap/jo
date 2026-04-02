"""
Ouroboros — Session Compaction.

Reduces token usage by summarizing older conversation rounds.
Inspired by claw-code's session compaction pattern.

Strategies:
- summarize_old: summarize rounds older than N
- keep_recent: keep only last N rounds verbatim
- extract_decisions: extract decisions from compacted rounds
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


@dataclass
class ConversationRound:
    round_id: int
    role: str  # "user" or "assistant"
    content: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: str = ""
    token_estimate: int = 0
    compacted: bool = False
    summary: Optional[str] = None


@dataclass
class CompactionResult:
    original_rounds: int
    compacted_rounds: int
    tokens_saved: int
    summary: str
    extracted_decisions: List[str] = field(default_factory=list)


class SessionCompactor:
    """Compacts conversation history to reduce token usage."""

    def __init__(self, keep_recent: int = 5, summarize_threshold: int = 10):
        self.keep_recent = keep_recent
        self.summarize_threshold = summarize_threshold

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) * 0.25)

    def compact(self, rounds: List[ConversationRound]) -> CompactionResult:
        if len(rounds) <= self.keep_recent:
            return CompactionResult(
                original_rounds=len(rounds),
                compacted_rounds=len(rounds),
                tokens_saved=0,
                summary="No compaction needed",
            )

        to_compact = rounds[: -self.keep_recent]
        to_keep = rounds[-self.keep_recent :]

        original_tokens = sum(r.token_estimate or self.estimate_tokens(r.content) for r in rounds)

        summary_parts = []
        decisions = []
        tools_used = []

        for r in to_compact:
            if r.summary:
                summary_parts.append(r.summary)
            else:
                brief = r.content[:150].replace("\n", " ")
                summary_parts.append(f"[Round {r.round_id}] {brief}")

            if r.tool_calls:
                for tc in r.tool_calls:
                    tool_name = tc.get("tool_name", "unknown")
                    if tool_name not in tools_used:
                        tools_used.append(tool_name)

            content_lower = r.content.lower()
            if any(kw in content_lower for kw in ["decided", "chose", "going with", "approach is"]):
                decisions.append(r.content[:100])

        compacted_tokens = sum(r.token_estimate or self.estimate_tokens(r.content) for r in to_keep)
        summary_tokens = self.estimate_tokens("\n".join(summary_parts))
        total_compacted = compacted_tokens + summary_tokens

        summary = (
            f"## Session History (compacted {len(to_compact)} rounds)\n"
            f"### Summary\n" + "\n".join(f"- {s}" for s in summary_parts[:20]) + "\n"
        )
        if tools_used:
            summary += f"\n### Tools Used\n- " + "\n- ".join(tools_used[:15]) + "\n"
        if decisions:
            summary += f"\n### Decisions Made\n- " + "\n- ".join(decisions[:10]) + "\n"

        return CompactionResult(
            original_rounds=len(rounds),
            compacted_rounds=len(to_keep),
            tokens_saved=max(0, original_tokens - total_compacted),
            summary=summary,
            extracted_decisions=decisions,
        )

    def compact_from_jsonl(self, jsonl_path: pathlib.Path) -> CompactionResult:
        rounds = []
        if not jsonl_path.exists():
            return CompactionResult(0, 0, 0, "No history file found")

        try:
            with open(jsonl_path, encoding="utf-8") as f:
                for i, line in enumerate(f):
                    if not line.strip():
                        continue
                    data = json.loads(line)
                    rounds.append(
                        ConversationRound(
                            round_id=i,
                            role=data.get("role", "unknown"),
                            content=data.get("content", ""),
                            tool_calls=data.get("tool_calls", []),
                            timestamp=data.get("timestamp", ""),
                            token_estimate=data.get("token_estimate", 0),
                        )
                    )
        except Exception as e:
            return CompactionResult(0, 0, 0, f"Failed to read history: {e}")

        return self.compact(rounds)

    def suggest_compaction(self, round_count: int, total_tokens: int) -> str:
        if round_count <= self.keep_recent:
            return f"✅ Session is lean ({round_count} rounds, ~{total_tokens:,} tokens). No compaction needed."

        estimated_savings = int(total_tokens * 0.6)
        return (
            f"⚠️ Session has {round_count} rounds (~{total_tokens:,} tokens).\n"
            f"Compacting would keep last {self.keep_recent} rounds and summarize the rest.\n"
            f"Estimated savings: ~{estimated_savings:,} tokens."
        )


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def session_compact_suggest(ctx, round_count: int, total_tokens: int) -> str:
        compactor = SessionCompactor()
        return compactor.suggest_compaction(round_count, total_tokens)

    def session_compact_history(ctx, history_file: str = "") -> str:
        compactor = SessionCompactor()
        if history_file:
            path = ctx.repo_path(history_file)
        else:
            path = ctx.drive_path("chat_history.jsonl")
        result = compactor.compact_from_jsonl(path)
        return (
            f"## Compaction Result\n"
            f"- Original rounds: {result.original_rounds}\n"
            f"- Compacted rounds: {result.compacted_rounds}\n"
            f"- Tokens saved: ~{result.tokens_saved:,}\n"
            f"\n{result.summary}"
        )

    return [
        ToolEntry(
            "session_compact_suggest",
            {
                "name": "session_compact_suggest",
                "description": "Check if session compaction would help reduce token usage.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "round_count": {"type": "integer", "description": "Number of conversation rounds"},
                        "total_tokens": {"type": "integer", "description": "Total estimated tokens"},
                    },
                    "required": ["round_count", "total_tokens"],
                },
            },
            session_compact_suggest,
        ),
        ToolEntry(
            "session_compact_history",
            {
                "name": "session_compact_history",
                "description": "Compact chat history file by summarizing older rounds.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "history_file": {
                            "type": "string",
                            "default": "",
                            "description": "Path to history file (default: chat_history.jsonl)",
                        },
                    },
                },
            },
            session_compact_history,
        ),
    ]
