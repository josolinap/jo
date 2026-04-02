"""
Ouroboros — Memory Extractor.

Extracts reusable knowledge from session transcripts and tool call logs.
Inspired by GSD-2's memory-extractor pattern.

Scans transcripts for:
- Decisions made
- Patterns discovered
- Mistakes encountered
- Preferences expressed
- Codebase insights
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class ExtractedMemory:
    content: str
    category: str  # "decision", "pattern", "mistake", "preference", "insight"
    confidence: float
    source: str
    tags: List[str] = field(default_factory=list)
    extracted_at: str = ""


DECISION_PATTERNS = [
    re.compile(r"(?i)(decided|chose|selected|going with|opted for|using)\s+(to\s+)?(.{10,100})"),
    re.compile(r"(?i)(the\s+)?(approach|strategy|decision)\s+(is|was)\s+(.{10,100})"),
]

MISTAKE_PATTERNS = [
    re.compile(r"(?i)(don'?t|never|avoid|shouldn'?t)\s+(.{10,100})"),
    re.compile(r"(?i)(mistake|error|wrong|bug|issue)\s+(was|is)\s+(.{10,100})"),
    re.compile(r"(?i)(learned|discovered|found)\s+(that\s+)?(.{10,100})"),
]

PATTERN_PATTERNS = [
    re.compile(r"(?i)(pattern|convention|standard|practice)\s+(is|should be)\s+(.{10,100})"),
    re.compile(r"(?i)(always|consistently|typically)\s+(.{10,100})"),
]

INSIGHT_PATTERNS = [
    re.compile(r"(?i)(interesting|notable|key)\s+(finding|insight|observation)\s*[:]\s*(.{10,100})"),
    re.compile(r"(?i)(this\s+)?(means|implies|suggests)\s+(that\s+)?(.{10,100})"),
]


class MemoryExtractor:
    """Extracts reusable knowledge from session data."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir

    def extract_from_text(self, text: str, source: str = "") -> List[ExtractedMemory]:
        memories = []
        lines = text.splitlines()

        for line in lines:
            line = line.strip()
            if len(line) < 20:
                continue

            for pattern in DECISION_PATTERNS:
                m = pattern.search(line)
                if m:
                    content = m.group(0)[:150]
                    memories.append(
                        ExtractedMemory(
                            content=content,
                            category="decision",
                            confidence=0.7,
                            source=source,
                            tags=self._extract_tags(content),
                            extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        )
                    )
                    break

            for pattern in MISTAKE_PATTERNS:
                m = pattern.search(line)
                if m:
                    content = m.group(0)[:150]
                    memories.append(
                        ExtractedMemory(
                            content=content,
                            category="mistake",
                            confidence=0.8,
                            source=source,
                            tags=self._extract_tags(content),
                            extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        )
                    )
                    break

            for pattern in PATTERN_PATTERNS:
                m = pattern.search(line)
                if m:
                    content = m.group(0)[:150]
                    memories.append(
                        ExtractedMemory(
                            content=content,
                            category="pattern",
                            confidence=0.6,
                            source=source,
                            tags=self._extract_tags(content),
                            extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        )
                    )
                    break

            for pattern in INSIGHT_PATTERNS:
                m = pattern.search(line)
                if m:
                    content = m.group(0)[:150]
                    memories.append(
                        ExtractedMemory(
                            content=content,
                            category="insight",
                            confidence=0.5,
                            source=source,
                            tags=self._extract_tags(content),
                            extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                        )
                    )
                    break

        return memories

    def extract_from_tool_calls(self, tool_calls: List[Dict[str, Any]], source: str = "") -> List[ExtractedMemory]:
        memories = []
        for tc in tool_calls:
            tool_name = tc.get("tool_name", "")
            args = tc.get("args", {})
            result = tc.get("result", "")

            if tool_name == "cerebrum_add":
                memories.append(
                    ExtractedMemory(
                        content=args.get("content", ""),
                        category=args.get("category", "learning"),
                        confidence=0.9,
                        source=f"tool:{tool_name}",
                        tags=args.get("tags", "").split(",") if isinstance(args.get("tags"), str) else [],
                        extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    )
                )

            if tool_name == "buglog_log":
                memories.append(
                    ExtractedMemory(
                        content=f"Bug: {args.get('error_message', '')} → Fix: {args.get('fix_description', '')}",
                        category="mistake",
                        confidence=0.9,
                        source=f"tool:{tool_name}",
                        tags=args.get("tags", "").split(",") if isinstance(args.get("tags"), str) else [],
                        extracted_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
                    )
                )

        return memories

    def _extract_tags(self, text: str) -> List[str]:
        tags = []
        tech_terms = re.findall(
            r"(?i)\b(python|javascript|typescript|react|node|git|api|sql|json|html|css|docker|aws|gcp|azure)\b", text
        )
        tags.extend(t.lower() for t in tech_terms)
        return list(set(tags))[:5]

    def deduplicate(self, memories: List[ExtractedMemory]) -> List[ExtractedMemory]:
        seen = set()
        unique = []
        for m in memories:
            key = (m.category, m.content[:50].lower())
            if key not in seen:
                seen.add(key)
                unique.append(m)
        return unique

    def format_for_cerebrum(self, memories: List[ExtractedMemory]) -> str:
        by_category: Dict[str, List[ExtractedMemory]] = {}
        for m in memories:
            by_category.setdefault(m.category, []).append(m)

        lines = ["## Extracted Memories"]
        for cat, items in sorted(by_category.items()):
            lines.append(f"\n### {cat.title()} ({len(items)})")
            for item in items[:10]:
                lines.append(f"- {item.content[:100]} (confidence={item.confidence:.0%})")
        return "\n".join(lines)

    def save_to_cerebrum(self, memories: List[ExtractedMemory]) -> str:
        cerebrum_path = self.repo_dir / "memory" / "cerebrum.json"
        try:
            from ouroboros.cerebrum import CerebrumManager

            mgr = CerebrumManager(self.repo_dir)
            saved = 0
            for m in memories:
                if m.confidence >= 0.6:
                    if m.category == "mistake":
                        mgr.add_do_not_repeat(m.content, m.tags, m.source)
                    elif m.category == "preference":
                        mgr.add_preference(m.content, m.tags, m.source)
                    else:
                        mgr.add_learning(m.content, m.tags, m.source)
                    saved += 1
            return f"Saved {saved}/{len(memories)} memories to cerebrum"
        except Exception as e:
            return f"Failed to save to cerebrum: {e}"

    def extract_from_buglog(self, limit: int = 50) -> List[ExtractedMemory]:
        """Extract memories from buglog entries."""
        memories = []
        try:
            from ouroboros.buglog import BugLog

            buglog = BugLog(self.repo_dir)
            entries = buglog._load()

            for entry in entries[-limit:]:
                # Extract as mistake memory
                memories.append(
                    ExtractedMemory(
                        content=f"{entry.error_message}: {entry.root_cause}",
                        category="mistake",
                        confidence=0.8,
                        source=f"buglog:{entry.bug_id}",
                        tags=entry.tags + ["buglog", "error-pattern"],
                        extracted_at=entry.fixed_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
                    )
                )

                # Extract fix pattern as learning
                memories.append(
                    ExtractedMemory(
                        content=f"Fix: {entry.fix_description}",
                        category="pattern",
                        confidence=0.7,
                        source=f"buglog:{entry.bug_id}",
                        tags=entry.tags + ["buglog", "fix-pattern"],
                        extracted_at=entry.fixed_at or time.strftime("%Y-%m-%dT%H:%M:%S"),
                    )
                )
        except Exception:
            log.debug("Failed to extract from buglog", exc_info=True)

        return memories


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    _extractors: Dict[str, MemoryExtractor] = {}

    def _get_extractor(repo_dir: pathlib.Path) -> MemoryExtractor:
        key = str(repo_dir)
        if key not in _extractors:
            _extractors[key] = MemoryExtractor(repo_dir)
        return _extractors[key]

    def memory_extract(ctx, text: str, source: str = "") -> str:
        extractor = _get_extractor(ctx.repo_dir)
        memories = extractor.extract_from_text(text, source)
        memories = extractor.deduplicate(memories)
        return extractor.format_for_cerebrum(memories)

    def memory_extract_save(ctx, text: str, source: str = "") -> str:
        extractor = _get_extractor(ctx.repo_dir)
        memories = extractor.extract_from_text(text, source)
        memories = extractor.deduplicate(memories)
        return extractor.save_to_cerebrum(memories)

    def memory_extract_buglog(ctx, limit: int = 50) -> str:
        extractor = _get_extractor(ctx.repo_dir)
        memories = extractor.extract_from_buglog(limit)
        memories = extractor.deduplicate(memories)
        return extractor.format_for_cerebrum(memories)

    def memory_extract_buglog_save(ctx, limit: int = 50) -> str:
        extractor = _get_extractor(ctx.repo_dir)
        memories = extractor.extract_from_buglog(limit)
        memories = extractor.deduplicate(memories)
        return extractor.save_to_cerebrum(memories)

    return [
        ToolEntry(
            "memory_extract",
            {
                "name": "memory_extract",
                "description": "Extract reusable memories (decisions, patterns, mistakes) from text. Use on session transcripts.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to extract memories from"},
                        "source": {"type": "string", "default": "", "description": "Source of the text"},
                    },
                    "required": ["text"],
                },
            },
            memory_extract,
        ),
        ToolEntry(
            "memory_extract_save",
            {
                "name": "memory_extract_save",
                "description": "Extract memories and automatically save them to the cerebrum.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string", "description": "Text to extract memories from"},
                        "source": {"type": "string", "default": "", "description": "Source of the text"},
                    },
                    "required": ["text"],
                },
            },
            memory_extract_save,
        ),
        ToolEntry(
            "memory_extract_buglog",
            {
                "name": "memory_extract_buglog",
                "description": "Extract memories from buglog entries (error patterns and fix patterns).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50, "description": "Max entries to process"},
                    },
                },
            },
            memory_extract_buglog,
        ),
        ToolEntry(
            "memory_extract_buglog_save",
            {
                "name": "memory_extract_buglog_save",
                "description": "Extract memories from buglog and save them to cerebrum.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "default": 50, "description": "Max entries to process"},
                    },
                },
            },
            memory_extract_buglog_save,
        ),
    ]
