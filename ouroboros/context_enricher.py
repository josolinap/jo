"""Context enricher for Jo - pre-fetches relevant context before LLM calls."""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class ContextEnricher:
    """Pre-fetches and enriches context before LLM calls for better responses."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = Path(repo_dir)
        self._cache: Dict[str, Any] = {}
        self._enabled = os.environ.get("OUROBOROS_ENRICH_CONTEXT", "1") == "1"
        self._use_vault = os.environ.get("OUROBOROS_USE_VAULT_ENRICH", "0") == "1"
        self._max_files = int(os.environ.get("OUROBOROS_MAX_ENRICH_FILES", "10"))
        self._max_chars_per_file = int(os.environ.get("OUROBOROS_MAX_ENRICH_CHARS", "8000"))
        self._max_vault_notes = int(os.environ.get("OUROBOROS_MAX_VAULT_NOTES", "3"))

    def is_enabled(self) -> bool:
        return self._enabled

    def enrich_for_task(self, task: str, task_type: str = "general") -> Dict[str, Any]:
        """Build enriched context for a task."""
        if not self._enabled:
            return {"enabled": False}

        cache_key = f"{task_type}:{hash(task)}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        enriched = {
            "enabled": True,
            "task": task,
            "task_type": task_type,
            "relevant_files": self._find_relevant_files(task),
            "recent_changes": self._get_recent_changes(),
            "related_context": self._get_related_context(task),
            "code_patterns": self._extract_code_patterns(task),
            "file_contents": {},
        }

        if self._use_vault:
            vault_context = self._get_vault_context(task)
            if vault_context:
                enriched["vault_context"] = vault_context

        if enriched["relevant_files"]:
            enriched["file_contents"] = self._prefetch_file_contents(enriched["relevant_files"])

        self._cache[cache_key] = enriched
        return enriched

    def build_enrichment_text(self, enriched: Dict[str, Any]) -> str:
        """Convert enrichment data to formatted text for LLM."""
        if not enriched or not enriched.get("enabled"):
            return ""

        parts = ["## Pre-fetched Context\n"]

        if enriched.get("relevant_files"):
            parts.append("### Relevant Files")
            for f in enriched["relevant_files"][:5]:
                parts.append(f"- `{f}`")
            parts.append("")

        if enriched.get("recent_changes"):
            parts.append("### Recent Changes")
            parts.append("```")
            parts.append(enriched["recent_changes"][:500])
            if len(enriched["recent_changes"]) > 500:
                parts.append("... (truncated)")
            parts.append("```")
            parts.append("")

        if enriched.get("code_patterns"):
            parts.append("### Detected Patterns")
            for pattern in enriched["code_patterns"][:5]:
                parts.append(f"- {pattern}")
            parts.append("")

        if enriched.get("related_context"):
            parts.append("### Related Context")
            parts.append(enriched["related_context"][:300])
            parts.append("")

        if enriched.get("vault_context"):
            parts.append("### Vault Knowledge")
            parts.append(enriched["vault_context"])
            parts.append("")

        return "\n".join(parts)

    def _find_relevant_files(self, task: str) -> List[str]:
        """Find files likely relevant to the task."""
        keywords = self._extract_keywords(task)
        if not keywords:
            return []

        relevant: List[tuple[str, int]] = []
        patterns = ["*.py", "*.js", "*.ts", "*.yaml", "*.yml", "*.json", "*.md"]

        for pattern in patterns:
            for f in self.repo_dir.rglob(pattern):
                if self._is_relevant_file(f, keywords):
                    score = self._calculate_relevance_score(f, keywords)
                    relevant.append((str(f.relative_to(self.repo_dir)), score))

        relevant.sort(key=lambda x: x[1], reverse=True)
        return [f for f, _ in relevant[: self._max_files]]

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract meaningful keywords from task text."""
        text = text.lower()

        words = re.findall(r"[a-z][a-z0-9_]{2,}", text)

        stop_words = {
            "the",
            "this",
            "that",
            "with",
            "from",
            "have",
            "has",
            "was",
            "were",
            "been",
            "being",
            "will",
            "would",
            "could",
            "should",
            "make",
            "file",
            "files",
            "code",
            "need",
            "want",
            "just",
            "like",
            "some",
            "any",
            "all",
            "each",
            "every",
            "both",
            "what",
            "when",
            "where",
            "which",
            "their",
            "there",
            "these",
            "those",
            "into",
            "also",
            "only",
            "then",
            "than",
            "very",
        }

        keywords = [w for w in words if w not in stop_words and len(w) > 2]

        return list(set(keywords))[:10]

    def _is_relevant_file(self, path: Path, keywords: List[str]) -> bool:
        """Check if file is likely relevant based on keywords."""
        name_lower = path.name.lower()

        for keyword in keywords:
            if keyword in name_lower:
                return True

        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(2000)
                content_lower = content.lower()

                matches = sum(1 for kw in keywords if kw in content_lower)
                if matches >= 2:
                    return True
        except Exception:
            log.debug("Unexpected error", exc_info=True)

        return False

    def _calculate_relevance_score(self, path: Path, keywords: List[str]) -> int:
        """Calculate relevance score for a file."""
        score = 0
        name_lower = path.name.lower()

        for keyword in keywords:
            if keyword in name_lower:
                score += 10

            if path.suffix in (".py", ".js", ".ts"):
                try:
                    with open(path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read(5000)
                        content_lower = content.lower()
                        score += content_lower.count(keyword)
                except Exception:
                    log.debug("Unexpected error", exc_info=True)

        return score

    def _prefetch_file_contents(self, files: List[str]) -> Dict[str, str]:
        """Pre-fetch contents of relevant files."""
        contents: Dict[str, str] = {}

        for f in files:
            path = self.repo_dir / f
            if not path.exists():
                continue

            try:
                size = path.stat().st_size
                if size > self._max_chars_per_file * 2:
                    content = self._read_with_limit(path, self._max_chars_per_file)
                    content += f"\n[... file truncated ({size:,} bytes) ...]"
                else:
                    content = path.read_text(encoding="utf-8", errors="ignore")

                contents[f] = content
            except Exception as e:
                log.debug(f"Failed to read {f}: {e}")

        return contents

    def _read_with_limit(self, path: Path, limit: int) -> str:
        """Read file with character limit."""
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read(limit)
        except Exception:
            return ""

    def _get_recent_changes(self) -> str:
        """Get summary of recent git changes."""
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-10", "--stat"],
                capture_output=True,
                text=True,
                cwd=self.repo_dir,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            log.debug(f"Failed to get git log: {e}")

        return ""

    def _get_related_context(self, task: str) -> str:
        """Get related context from memory/knowledge."""
        context_parts = []

        scratchpad = self.repo_dir / "memory" / "scratchpad.md"
        if scratchpad.exists():
            try:
                content = scratchpad.read_text(encoding="utf-8")
                if len(content) > 500:
                    context_parts.append(f"### Scratchpad (recent)\n{content[-500:]}")
                else:
                    context_parts.append(f"### Scratchpad\n{content}")
            except Exception:
                log.debug("Unexpected error", exc_info=True)

        return "\n\n".join(context_parts[:2])

    def _get_vault_context(self, task: str) -> str:
        """Get relevant knowledge from vault."""
        try:
            from ouroboros.vault import vault_search
            
            results = vault_search(
                query=task,
                field="content",
                max_results=self._max_vault_notes
            )
            
            if not results:
                return ""
            
            context_parts = []
            for result in results:
                note = result.get("note", {})
                title = note.get("title", "Untitled")
                content = note.get("content", "")
                preview = content[:500] + ("..." if len(content) > 500 else "")
                context_parts.append(f"#### {title}\n{preview}")
            
            return "\n\n".join(context_parts)
        except Exception as e:
            log.debug(f"Failed to search vault: {e}")
            return ""

    def _extract_code_patterns(self, task: str) -> List[str]:
        """Extract code patterns mentioned in task."""
        patterns: List[str] = []

        pattern_map = {
            r"test[s]?": "Testing patterns",
            r"class[\s\n]+\w+": "Class definitions",
            r"def\s+\w+": "Function definitions",
            r"import\s+\w+": "Import statements",
            r"async\s+def": "Async functions",
            r"@\w+": "Decorators",
            r"for\s+\w+\s+in": "For loops",
            r"if\s+\w+": "Conditional checks",
            r"try:": "Try-except blocks",
            r"with\s+open": "Context managers",
        }

        task_lower = task.lower()
        for pattern, description in pattern_map.items():
            if re.search(pattern, task, re.IGNORECASE):
                patterns.append(description)

        return patterns[:5]


def enrich_messages(
    messages: List[Dict[str, Any]],
    task: str,
    task_type: str,
    repo_dir: Path,
) -> List[Dict[str, Any]]:
    """Add enriched context to messages if enabled."""
    enricher = ContextEnricher(repo_dir)

    if not enricher.is_enabled():
        return messages

    enriched = enricher.enrich_for_task(task, task_type)
    enrichment_text = enricher.build_enrichment_text(enriched)

    if not enrichment_text:
        return messages

    for i, msg in enumerate(messages):
        if msg.get("role") == "system":
            continue

        if msg.get("role") == "user":
            messages.insert(
                i,
                {
                    "role": "system",
                    "content": enrichment_text,
                    "_enrichment": True,
                },
            )
            break

    return messages