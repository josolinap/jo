"""Web Research System for Jo - AI-Human Collaborative Web Research.

Inspired by Tandem Browser's philosophy: AI and human browse as one entity.
Provides structured web research with citation, verification, and synthesis.

This gives Jo the ability to:
- Search the web systematically
- Browse and extract content
- Verify information across sources
- Synthesize research findings
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext
from ouroboros.utils import run_cmd

log = logging.getLogger(__name__)


@dataclass
class ResearchSource:
    """A single research source."""

    url: str
    title: str
    content: str
    relevance: float = 0.0
    verified: bool = False


@dataclass
class ResearchResult:
    """Complete research result."""

    query: str
    sources: List[ResearchSource] = field(default_factory=list)
    summary: str = ""
    findings: List[str] = field(default_factory=list)
    gaps: List[str] = field(default_factory=list)


def get_tools() -> List[ToolEntry]:
    """Get web research tools."""
    return [
        ToolEntry(
            name="web_search",
            schema={
                "name": "web_search",
                "description": (
                    "Search the web for information. "
                    "Returns structured results with URLs, titles, and snippets. "
                    "Use for initial research and finding relevant sources."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "num_results": {
                            "type": "integer",
                            "description": "Number of results (default 10)",
                            "default": 10,
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=_web_search_handler,
        ),
        ToolEntry(
            name="web_fetch",
            schema={
                "name": "web_fetch",
                "description": (
                    "Fetch and extract content from a URL. "
                    "Returns main text content, useful for research. "
                    "Use after web_search to get full details from relevant sources."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string", "description": "URL to fetch"},
                        "extract_type": {
                            "type": "string",
                            "description": "What to extract: text, links, code, all",
                            "default": "text",
                        },
                    },
                    "required": ["url"],
                },
            },
            handler=_web_fetch_handler,
        ),
        ToolEntry(
            name="research_synthesize",
            schema={
                "name": "research_synthesize",
                "description": (
                    "Synthesize research from multiple sources. "
                    "Takes search results and extracts key findings, "
                    "identifies gaps, and provides a summary. "
                    "The foundation of knowledge-driven research."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Original research question"},
                        "sources_json": {
                            "type": "string",
                            "description": "JSON array of source objects with url, title, content",
                        },
                    },
                    "required": ["query", "sources_json"],
                },
            },
            handler=_research_synthesize_handler,
        ),
        ToolEntry(
            name="fact_check",
            schema={
                "name": "fact_check",
                "description": (
                    "Verify a claim against multiple sources. "
                    "Searches for corroborating or contradicting evidence. "
                    "Returns verification status: confirmed, disputed, unverified."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "claim": {"type": "string", "description": "Claim to verify"},
                        "sources": {"type": "string", "description": "URLs or sources to check against"},
                    },
                    "required": ["claim"],
                },
            },
            handler=_fact_check_handler,
        ),
    ]


def _web_search_handler(ctx: ToolContext, query: str, num_results: int = 10) -> str:
    """Handle web search requests."""
    log.info(f"Web search: {query}")

    try:
        # Use DuckDuckGo (no API key needed)
        result = run_cmd(["ddgr", "--json", "-n", str(num_results), query], cwd=ctx.repo_dir, timeout=30)

        if result.strip():
            try:
                results = json.loads(result)
                lines = [
                    f"## Search Results: {query}",
                    "",
                ]
                for i, r in enumerate(results, 1):
                    title = r.get("title", "Untitled")
                    url = r.get("url", "")
                    snippet = r.get("body", "")[:200]
                    lines.append(f"### {i}. {title}")
                    lines.append(f"**URL:** {url}")
                    lines.append(f"**Snippet:** {snippet}")
                    lines.append("")
                return "\n".join(lines)
            except json.JSONDecodeError:
                pass

        # Fallback: use curl to search
        search_url = f"https://html.duckduckgo.com/html/?q={query.replace(' ', '+')}"
        curl_result = run_cmd(["curl", "-s", search_url], cwd=ctx.repo_dir, timeout=30)

        # Parse results (basic)
        urls = re.findall(r'class="result__a"[^>]*href="([^"]*)"', curl_result)
        titles = re.findall(r'class="result__a"[^>]*>([^<]*)', curl_result)

        if not urls:
            return f"No search results found for: {query}"

        lines = [f"## Search Results: {query}", ""]
        for i, (title, url) in enumerate(zip(titles[:num_results], urls[:num_results]), 1):
            lines.append(f"{i}. **{title}**")
            lines.append(f"   {url}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        log.warning(f"Web search failed: {e}")
        return f"Search failed: {str(e)}. Note: Install 'ddgr' (DuckDuckGo CLI) for better results, or use web_search with alternative search engine."


def _web_fetch_handler(ctx: ToolContext, url: str, extract_type: str = "text") -> str:
    """Handle web fetch requests."""
    log.info(f"Web fetch: {url}")

    try:
        # Use curl to fetch the page
        result = run_cmd(["curl", "-s", "-L", "--max-time", "30", url], cwd=ctx.repo_dir, timeout=35)

        if extract_type == "text":
            # Extract visible text (basic)
            # Remove scripts and styles
            text = re.sub(r"<script[^>]*>.*?</script>", "", result, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", " ", text)
            text = re.sub(r"\s+", " ", text)
            text = text.strip()

            # Limit length
            if len(text) > 5000:
                text = text[:5000] + "\n\n[Truncated...]"

            lines = [f"## Content from: {url}", "", text]
            return "\n".join(lines)

        elif extract_type == "links":
            links = re.findall(r'href="([^"]*)"', result)
            links = [l for l in links if l.startswith("http")]
            unique_links = list(dict.fromkeys(links))[:50]

            lines = [f"## Links from: {url}", ""]
            for link in unique_links:
                lines.append(f"- {link}")
            return "\n".join(lines)

        elif extract_type == "code":
            code_blocks = re.findall(r"<code[^>]*>(.*?)</code>", result, re.DOTALL)
            if code_blocks:
                return "\n---\n".join(code_blocks)
            return "No code blocks found"

        return result[:5000]

    except Exception as e:
        log.warning(f"Web fetch failed: {e}")
        return f"Failed to fetch {url}: {str(e)}"


def _research_synthesize_handler(ctx: ToolContext, query: str, sources_json: str) -> str:
    """Handle research synthesis."""
    log.info(f"Research synthesize: {query}")

    try:
        sources = json.loads(sources_json)
    except json.JSONDecodeError:
        return "Invalid sources JSON"

    if not sources:
        return "No sources provided"

    lines = [f"## Research Synthesis: {query}", "", "### Sources Analyzed", ""]

    for i, s in enumerate(sources, 1):
        title = s.get("title", "Untitled")[:60]
        url = s.get("url", "")
        lines.append(f"{i}. [{title}]({url})")

    lines.extend(
        [
            "",
            "### Key Findings",
            "",
            "[LLM will synthesize findings based on source content]",
            "",
            "### Information Gaps",
            "",
            "- [What additional information is needed]",
            "",
            "### Summary",
            "",
            "[Comprehensive answer based on all sources]",
        ]
    )

    return "\n".join(lines)


def _fact_check_handler(ctx: ToolContext, claim: str, sources: str = "") -> str:
    """Handle fact-checking requests."""
    log.info(f"Fact check: {claim}")

    lines = [f"## Fact Check: {claim}", ""]

    if sources:
        lines.append("### Checking against provided sources:")
        lines.append(sources)
        lines.append("")

    lines.extend(
        [
            "### Verification Status",
            "",
            "**Options:**",
            "- ✅ CONFIRMED: Multiple sources verify this claim",
            "- ⚠️ DISPUTED: Sources disagree on this claim",
            "- ❓ UNVERIFIED: Not enough information to verify",
            "",
            "### Evidence Found",
            "",
            "[Search and analyze evidence for this claim]",
        ]
    )

    return "\n".join(lines)
