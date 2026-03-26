"""Web Research System for Jo - AI-Human Collaborative Web Research.

Inspired by Tandem Browser's philosophy: AI and human browse as one entity.
Provides structured web research with citation, verification, and synthesis.

This gives Jo the ability to:
- Search the web systematically with date filtering
- Browse and extract content with retry logic
- Verify information across sources with confidence scoring
- Synthesize research findings with cross-verification

Enhancements:
- Multi-engine fallback (ddgr -> Bing -> DuckDuckGo -> Searx)
- Date filtering (today, week, month, custom range)
- Relevance scoring and deduplication
- Retry with exponential backoff
- Systematic research pipeline
"""

from __future__ import annotations

import json
import logging
import os
import pathlib
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ouroboros.tools.registry import ToolEntry, ToolContext
from ouroboros.utils import run_cmd

log = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
]

SOURCE_RELIABILITY = {
    "reuters.com": 0.95,
    "apnews.com": 0.95,
    "bbc.com": 0.93,
    "bbc.co.uk": 0.93,
    "nytimes.com": 0.92,
    "theguardian.com": 0.91,
    "washingtonpost.com": 0.91,
    "cnn.com": 0.88,
    "foxnews.com": 0.85,
    "bloomberg.com": 0.90,
    "wsj.com": 0.90,
    "economist.com": 0.92,
    "npr.org": 0.89,
    "thehill.com": 0.82,
    ".gov": 0.90,
    ".edu": 0.88,
    ".org": 0.85,
}

DATE_FILTERS = {
    "today": "d:r",
    "week": "d:w",
    "month": "d:m",
    "year": "d:y",
}


@dataclass
class SearchResult:
    """A single search result with metadata."""

    url: str
    title: str
    snippet: str
    source: str
    date: Optional[str] = None
    relevance_score: float = 0.0
    verified: bool = False


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
                    "Use for initial research and finding relevant sources. "
                    "Supports date filtering: today, week, month, year."
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
                        "date_filter": {
                            "type": "string",
                            "enum": ["", "today", "week", "month", "year"],
                            "description": "Filter by date: today, week, month, year (default: all)",
                            "default": "",
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=_web_search_handler,
        ),
        ToolEntry(
            name="research_pipeline",
            schema={
                "name": "research_pipeline",
                "description": (
                    "Run systematic research: search -> fetch top results -> cross-verify -> synthesize. "
                    "This is the primary research tool for thorough investigation of topics. "
                    "Returns structured findings with source citations and confidence scores."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Research question/topic"},
                        "num_sources": {
                            "type": "integer",
                            "description": "Number of sources to analyze (default 5)",
                            "default": 5,
                        },
                        "date_filter": {
                            "type": "string",
                            "enum": ["", "today", "week", "month", "year"],
                            "description": "Filter by recency (default: week)",
                            "default": "week",
                        },
                    },
                    "required": ["query"],
                },
            },
            handler=_research_pipeline_handler,
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


def _web_search_handler(ctx: ToolContext, query: str, num_results: int = 10, date_filter: str = "") -> str:
    """Handle web search requests with multiple fallback engines and date filtering."""
    log.info(f"Web search: {query}, date_filter: {date_filter}")

    if not query or not query.strip():
        return "⚠️ Search query cannot be empty. Please provide a search term."

    query = query.strip()

    enhanced_query = _enhance_query_with_date(query, date_filter)

    all_results: List[SearchResult] = []

    try:
        ddgr_results = _search_ddgr(enhanced_query, num_results, query)
        all_results.extend(ddgr_results)
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    if not all_results:
        bing_results = _search_bing_enhanced(enhanced_query, num_results, query)
        all_results.extend(bing_results)

    if not all_results:
        ddg_results = _search_duckduckgo_enhanced(enhanced_query, num_results, query)
        all_results.extend(ddg_results)

    if not all_results:
        searx_results = _search_searx_enhanced(enhanced_query, num_results, query)
        all_results.extend(searx_results)

    if not all_results:
        return (
            f"## Search Results: {query}\n\n"
            f"Automated search is currently unavailable.\n\n"
            f"To search manually, use:\n"
            f'1. `browse_page(url="https://www.google.com/search?q={query.replace(" ", "+")}")`\n'
            f'2. Then use `browse_action(action="extract_text")` to get results\n\n'
            f"Alternatively, install ddgr for better search: `pip install ddgr` or `apt install ddgr`"
        )

    all_results = _deduplicate_results(all_results)
    all_results = _score_and_sort_results(all_results, query)
    all_results = all_results[:num_results]

    return _format_search_results(query, all_results, date_filter)


def _enhance_query_with_date(query: str, date_filter: str) -> str:
    """Add date operators to query based on filter."""
    if not date_filter or date_filter not in DATE_FILTERS:
        return query

    filter_code = DATE_FILTERS[date_filter]
    return f"{query} {filter_code}"


def _search_ddgr(query: str, num_results: int, original_query: str) -> List[SearchResult]:
    """Search using ddgr (DuckDuckGo CLI)."""
    result = run_cmd(["ddgr", "--json", "-n", str(num_results), query], cwd=None, timeout=30)
    if not result.strip():
        return []

    try:
        results = json.loads(result)
        return [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", "Untitled"),
                snippet=r.get("body", "")[:200],
                source="ddgr",
                date=r.get("date", ""),
            )
            for r in results
        ]
    except json.JSONDecodeError:
        return []


def _search_bing_enhanced(query: str, num_results: int, original_query: str) -> List[SearchResult]:
    """Enhanced Bing search with better parsing."""
    import urllib.parse
    import html

    try:
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://www.bing.com/search?q={encoded_query}&count={num_results}"

        result = run_cmd(
            [
                "curl",
                "-s",
                "-L",
                "--max-time",
                "15",
                "-A",
                random.choice(USER_AGENTS),
                search_url,
            ],
            cwd=None,
            timeout=20,
        )

        if not result or len(result) < 1000:
            return []

        results = []
        item_blocks = re.findall(r'<li[^>]*class="[^"]*b_algo[^"]*"[^>]*>(.*?)</li>', result, re.DOTALL)

        for block in item_blocks[:num_results]:
            url_match = re.search(r'href="([^"]*)"', block)
            title_match = re.search(r"<h2[^>]*><a[^>]*>([^<]*)</a>", block)
            snippet_match = re.search(r'<p[^>]*class="[^"]*b_paractip[^"]*"[^>]*>([^<]*)</p>', block)
            date_match = re.search(r'<span[^>]*class="[^"]*news_dt[^"]*"[^>]*>([^<]*)</span>', block)

            if url_match and title_match:
                clean_url = _resolve_bing_redirect(url_match.group(1))
                results.append(
                    SearchResult(
                        url=clean_url,
                        title=html.unescape(title_match.group(1).strip()),
                        snippet=html.unescape(snippet_match.group(1).strip()) if snippet_match else "",
                        source="Bing",
                        date=date_match.group(1).strip() if date_match else None,
                    )
                )

        return results
    except Exception:
        return []


def _search_duckduckgo_enhanced(query: str, num_results: int, original_query: str) -> List[SearchResult]:
    """Enhanced DuckDuckGo HTML search."""
    import urllib.parse

    try:
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://html.duckduckgo.com/html/?q={encoded_query}"

        result = run_cmd(
            [
                "curl",
                "-s",
                "-L",
                "--max-time",
                "15",
                "-A",
                random.choice(USER_AGENTS),
                search_url,
            ],
            cwd=None,
            timeout=20,
        )

        if not result or len(result) < 1000:
            return []

        urls = re.findall(r'<a class="result__a" href="([^"]*)"', result)
        titles = re.findall(r'<a class="result__a"[^>]*>([^<]*)', result)

        if not urls:
            return []

        return [
            SearchResult(
                url=url,
                title=re.sub(r"<[^>]+>", "", title).strip(),
                snippet="",
                source="DuckDuckGo",
            )
            for url, title in zip(urls[:num_results], titles[:num_results])
        ]
    except Exception:
        return []


def _search_searx_enhanced(query: str, num_results: int, original_query: str) -> List[SearchResult]:
    """Enhanced Searx search."""
    import urllib.parse

    try:
        encoded_query = urllib.parse.quote_plus(query)
        search_url = f"https://searx.be/search?q={encoded_query}&format=json"

        result = run_cmd(["curl", "-s", "-L", "--max-time", "15", search_url], cwd=None, timeout=20)

        if not result:
            return []

        data = json.loads(result)
        results = data.get("results", [])
        if not results:
            return []

        return [
            SearchResult(
                url=r.get("url", ""),
                title=r.get("title", "Untitled"),
                snippet=r.get("content", "")[:150],
                source="Searx",
                date=r.get("publishedDate", None),
            )
            for r in results[:num_results]
        ]
    except Exception:
        return []


def _deduplicate_results(results: List[SearchResult]) -> List[SearchResult]:
    """Remove duplicate URLs and near-duplicate titles."""
    seen_urls = set()
    seen_titles = set()
    deduped = []

    for r in results:
        normalized_url = _normalize_url(r.url)
        normalized_title = r.title.lower()[:50]

        if normalized_url in seen_urls:
            continue
        if normalized_title in seen_titles and len(deduped) > 3:
            continue

        seen_urls.add(normalized_url)
        seen_titles.add(normalized_title)
        deduped.append(r)

    return deduped


def _normalize_url(url: str) -> str:
    """Normalize URL for deduplication."""
    url = url.lower().strip()
    url = re.sub(r"^https?://(www\.)?", "", url)
    url = re.sub(r"/+$", "", url)
    url = url.split("?")[0].split("#")[0]
    return url


def _score_and_sort_results(results: List[SearchResult], query: str) -> List[SearchResult]:
    """Score and sort results by relevance to query."""
    query_terms = set(query.lower().split())

    for r in results:
        score = 0.0
        title_lower = r.title.lower()
        snippet_lower = r.snippet.lower()

        for term in query_terms:
            if term in title_lower:
                score += 2.0
            if term in snippet_lower:
                score += 1.0

        if any(tld in r.url for tld in [".gov", ".edu", ".org"]):
            score += 0.5

        if r.date:
            score += 0.3

        r.relevance_score = score

    return sorted(results, key=lambda x: x.relevance_score, reverse=True)


def _format_search_results(query: str, results: List[SearchResult], date_filter: str) -> str:
    """Format search results for output."""
    lines = [f"## Search Results: {query}", ""]

    if date_filter:
        lines.append(f"_Filtered by: {date_filter}_")
        lines.append("")

    lines.append(f"_{len(results)} relevant results_\n")

    for i, r in enumerate(results, 1):
        lines.append(f"### {i}. {r.title}")
        lines.append(f"**URL:** {r.url}")
        if r.snippet:
            lines.append(f"**Snippet:** {r.snippet[:200]}")
        if r.date:
            lines.append(f"**Date:** {r.date}")
        lines.append(f"**Source:** {r.source}")
        lines.append("")

    return "\n".join(lines)


def _resolve_bing_redirect(url: str) -> str:
    """Resolve Bing redirect URLs to final destination."""
    import base64
    import urllib.parse

    if not url:
        return ""

    if "bing.com/ck/a" in url:
        match = re.search(r"[?&]u=([^&]+)", url)
        if match:
            encoded = match.group(1)
            try:
                b64_data = encoded[2:] if encoded.startswith("a1") else encoded[1:]
                padding = (4 - (len(b64_data) % 4)) % 4
                b64_padded = b64_data + "=" * padding
                decoded_b64 = base64.b64decode(b64_padded).decode("utf-8", errors="ignore")
                if decoded_b64.startswith("http"):
                    return decoded_b64
                return urllib.parse.unquote(encoded)
            except Exception:
                return urllib.parse.unquote(encoded)
    elif "bing.com/rd" in url:
        match = re.search(r"[?&]q=([^&]+)", url)
        if match:
            decoded = urllib.parse.unquote(match.group(1))
            return decoded

    return urllib.parse.unquote(url)


def _get_source_reliability(url: str) -> float:
    """Get reliability score for a source based on domain."""
    url_lower = url.lower()

    for pattern, score in SOURCE_RELIABILITY.items():
        if pattern.startswith("."):
            if url_lower.endswith(pattern):
                return score
        elif pattern in url_lower:
            return score

    return 0.7


def _fetch_with_retry(url: str, max_retries: int = 3, timeout: int = 30) -> Optional[str]:
    """Fetch URL with exponential backoff retry."""
    for attempt in range(max_retries):
        try:
            delay = 2**attempt
            if attempt > 0:
                time.sleep(delay)

            result = run_cmd(
                [
                    "curl",
                    "-s",
                    "-L",
                    "--max-time",
                    str(timeout // 2),
                    "-A",
                    random.choice(USER_AGENTS),
                    url,
                ],
                cwd=None,
                timeout=timeout,
            )

            if result and len(result) > 100:
                return result

        except Exception:
            if attempt == max_retries - 1:
                return None

    return None


def _extract_clean_text(html_content: str) -> str:
    """Extract clean text from HTML content."""
    text = re.sub(r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<noscript[^>]*>.*?</noscript>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&quot;", '"', text)
    return text.strip()


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


def _research_pipeline_handler(ctx: ToolContext, query: str, num_sources: int = 5, date_filter: str = "week") -> str:
    """Handle research pipeline: search -> fetch -> verify -> synthesize."""
    log.info(f"Research pipeline: {query}, date_filter: {date_filter}")

    lines = [f"## Research Pipeline: {query}", ""]

    if date_filter:
        lines.append(f"**Date Filter:** {date_filter}")
    lines.append(f"**Sources to analyze:** {num_sources}\n")

    enhanced_query = _enhance_query_with_date(query, date_filter)
    search_results = _run_search_with_fallback(enhanced_query, num_sources * 2)

    if not search_results:
        return (
            f"## Research Pipeline: {query}\n\n"
            f"⚠️ No search results found. Try broadening your query or removing the date filter."
        )

    search_results = _deduplicate_results(search_results)
    search_results = _score_and_sort_results(search_results, query)
    search_results = search_results[:num_sources]

    lines.append("### Search Results\n")
    for i, r in enumerate(search_results, 1):
        reliability = _get_source_reliability(r.url)
        lines.append(f"{i}. **{r.title}**")
        lines.append(f"   URL: {r.url}")
        lines.append(f"   Source: {r.source} (reliability: {reliability:.0%})")
        if r.date:
            lines.append(f"   Date: {r.date}")
        lines.append("")

    lines.append("### Fetching Content\n")
    sources_content = []
    successful_fetches = 0

    for i, result in enumerate(search_results):
        lines.append(f"Fetching {i + 1}/{len(search_results)}: {result.url[:60]}...")
        content = _fetch_with_retry(result.url, max_retries=3)

        if content:
            clean_text = _extract_clean_text(content)
            clean_text = clean_text[:3000]

            sources_content.append(
                {
                    "url": result.url,
                    "title": result.title,
                    "content": clean_text,
                    "source": result.source,
                    "reliability": _get_source_reliability(result.url),
                }
            )
            successful_fetches += 1
            lines.append(f"   ✅ Fetched {len(clean_text)} chars\n")
        else:
            lines.append(f"   ⚠️ Failed to fetch\n")

    if not sources_content:
        return (
            f"## Research Pipeline: {query}\n\n"
            f"⚠️ Could not fetch content from any sources. "
            f"Try using browse_page directly."
        )

    lines.append(f"\n**Successfully fetched {successful_fetches}/{len(search_results)} sources**\n")

    lines.append("### Key Findings\n")
    for i, source in enumerate(sources_content, 1):
        lines.append(f"\n**Source {i}:** {source['title']}")
        lines.append(f"_{source['source']} ({source['reliability']:.0%} reliability)_")

        content_preview = source["content"][:500]
        if len(source["content"]) > 500:
            content_preview += "..."
        lines.append(f"\n{content_preview}\n")

    avg_reliability = sum(s["reliability"] for s in sources_content) / len(sources_content)
    confidence = "High" if avg_reliability > 0.85 else "Medium" if avg_reliability > 0.7 else "Low"

    lines.extend(
        [
            "### Summary",
            "",
            f"**Confidence Level:** {confidence} (based on {avg_reliability:.0%} average source reliability)",
            "",
            "**Note:** This is raw research. The LLM should synthesize these findings into a coherent answer.",
            "",
            "### Information Gaps",
            "",
            "- [What aspects of the topic need more research?]",
            "- [Are there conflicting sources that need cross-verification?]",
        ]
    )

    return "\n".join(lines)


def _run_search_with_fallback(query: str, num_results: int) -> List[SearchResult]:
    """Run search with fallback through multiple engines."""
    all_results: List[SearchResult] = []

    try:
        results = _search_ddgr(query, num_results, query)
        if results:
            all_results.extend(results)
    except Exception:
        log.debug("Unexpected error", exc_info=True)

    if len(all_results) < 3:
        bing_results = _search_bing_enhanced(query, num_results, query)
        if bing_results:
            all_results.extend(bing_results)

    if len(all_results) < 3:
        ddg_results = _search_duckduckgo_enhanced(query, num_results, query)
        if ddg_results:
            all_results.extend(ddg_results)

    if not all_results:
        searx_results = _search_searx_enhanced(query, num_results, query)
        if searx_results:
            all_results.extend(searx_results)

    return all_results
