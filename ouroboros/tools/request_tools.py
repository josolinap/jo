"""Tool Request System - Jo's ability to request new capabilities.

This module allows Jo to dynamically request new tools or resources
when it encounters limitations. Jo can identify what it needs and ask.

Example use cases:
- Request API keys for new services
- Request new tools for specific tasks
- Request access to external services
- Request improvements to existing tools
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


TOOL_REQUESTS_LOG = "memory/tool_requests.md"


def _log_tool_request(ctx: ToolContext, request_type: str, details: str) -> None:
    """Log a tool request for tracking and review."""
    try:
        import datetime

        log_path = ctx.drive_path(TOOL_REQUESTS_LOG)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        entry = f"""
## Tool Request - {datetime.datetime.now().isoformat()}

**Type:** {request_type}
**Details:** {details}
**Status:** pending
"""
        if log_path.exists():
            existing = log_path.read_text(encoding="utf-8")
            log_path.write_text(existing + entry, encoding="utf-8")
        else:
            log_path.write_text(entry, encoding="utf-8")
    except Exception as e:
        log.warning(f"Failed to log tool request: {e}")


def _request_capability(ctx: ToolContext, capability: str, reason: str, priority: str = "medium") -> str:
    """Request a new capability or resource.

    Jo can use this to ask for things it needs:
    - API keys (e.g., "ANTHROPIC_API_KEY for Claude Code")
    - New tools (e.g., "GitHub PR creation tool")
    - External services
    - More permissions

    Args:
        capability: What is needed (e.g., "GitHub API access", "database connection")
        reason: Why it's needed (e.g., "To create GitHub PRs for code reviews")
        priority: low, medium, high, critical
    """
    log.info(f"Capability requested: {capability}")

    _log_tool_request(ctx, capability, f"Reason: {reason}\nPriority: {priority}")

    priority_emoji = {
        "low": "📋",
        "medium": "⚠️",
        "high": "🔥",
        "critical": "🚨",
    }.get(priority.lower(), "⚠️")

    lines = [
        f"{priority_emoji} **Capability Request**",
        "",
        f"**Requested:** {capability}",
        f"**Reason:** {reason}",
        f"**Priority:** {priority}",
        "",
        "This request has been logged for review.",
        "",
        "To fulfill this request:",
        "1. If it's an API key, add it to environment or secure storage",
        "2. If it's a new tool, it will be implemented based on priority",
        "3. Check memory/tool_requests.md for pending requests",
    ]

    return "\n".join(lines)


def _request_api_key(ctx: ToolContext, provider: str, purpose: str) -> str:
    """Request an API key for a specific service.

    Jo can ask for API keys it needs to function fully.

    Args:
        provider: The service provider (e.g., "anthropic", "openai", "github")
        purpose: What the key will be used for
    """
    log.info(f"API key requested: {provider}")

    capability = f"{provider.upper()}_API_KEY"
    reason = f"To {purpose}"

    _log_tool_request(ctx, "API_KEY", f"Provider: {provider}\nPurpose: {purpose}\nCapability: {capability}")

    provider_info = {
        "anthropic": {
            "name": "Anthropic",
            "url": "https://console.anthropic.com/settings/keys",
            "tools": "Claude Code CLI, claude_code_edit tool",
        },
        "openai": {
            "name": "OpenAI",
            "url": "https://platform.openai.com/api-keys",
            "tools": "GPT-4 code generation, web search",
        },
        "github": {
            "name": "GitHub",
            "url": "https://github.com/settings/tokens",
            "tools": "PR creation, repo management",
        },
        "serpapi": {
            "name": "SerpAPI",
            "url": "https://serpapi.com/dashboard",
            "tools": "Enhanced Google search",
        },
    }

    info = provider_info.get(provider.lower(), {"name": provider.title(), "url": "", "tools": "Unknown"})

    lines = [
        "## API Key Request",
        "",
        f"**Provider:** {info['name']}",
        f"**Purpose:** {purpose}",
        f"**Will Enable:** {info['tools']}",
        "",
        f"**Get Key:** {info['url']}",
        "",
        "To provide this key:",
        "1. Obtain API key from the provider",
        "2. Share securely via Telegram: `/apikey anthropic sk-...`",
        "3. Or add to environment configuration",
        "",
        "Request logged in memory/tool_requests.md",
    ]

    return "\n".join(lines)


def _list_tool_requests(ctx: ToolContext, status: str = "all") -> str:
    """List pending tool/capability requests."""
    log.info(f"Listing tool requests: {status}")

    log_path = ctx.drive_path(TOOL_REQUESTS_LOG)

    if not log_path.exists():
        return "No tool requests recorded yet."

    try:
        content = log_path.read_text(encoding="utf-8")

        requests = []
        current = {}

        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("## Tool Request - "):
                if current:
                    requests.append(current)
                current = {"date": line.replace("## Tool Request - ", "")}
            elif line.startswith("**Type:** "):
                current["type"] = line.replace("**Type:** ", "")
            elif line.startswith("**Details:** "):
                current["details"] = line.replace("**Details:** ", "")
            elif line.startswith("**Status:** "):
                current["status"] = line.replace("**Status:** ", "")

        if current:
            requests.append(current)

        if status != "all":
            requests = [r for r in requests if r.get("status", "").lower() == status.lower()]

        if not requests:
            return f"No {status} tool requests found."

        lines = [f"## Tool Requests ({len(requests)})", ""]

        for r in requests:
            lines.append(f"- **{r.get('type', 'Unknown')}**")
            lines.append(f"  - Date: {r.get('date', 'Unknown')}")
            if r.get("details"):
                lines.append(f"  - {r.get('details', '')[:100]}")

        return "\n".join(lines)

    except Exception as e:
        return f"Error reading requests: {e}"


def _check_capabilities(ctx: ToolContext) -> str:
    """Check what capabilities Jo has vs what's missing."""
    log.info("Checking capabilities")

    capabilities = {
        "OPENAI_API_KEY": {
            "name": "OpenRouter (via OpenAI compat)",
            "status": "unknown",
            "tools": ["ai_code_edit", "web search", "LLM calls"],
        },
        "ANTHROPIC_API_KEY": {"name": "Anthropic", "status": "missing", "tools": ["claude_code_edit (optional)"]},
        "GITHUB_TOKEN": {"name": "GitHub", "status": "missing", "tools": ["PR creation"]},
        "ddgr": {"name": "ddgr CLI", "status": "unknown", "tools": ["CLI web search (optional)"]},
    }

    lines = ["## Capability Status", ""]

    available = []
    missing = []

    for key, info in capabilities.items():
        import os

        is_set = bool(os.environ.get(key))
        if key == "OPENAI_API_KEY":
            is_set = True

        status = "✅ Available" if is_set else "❌ Missing"

        line = f"- **{info['name']}** ({key}): {status}"
        line += f"\n  Enables: {', '.join(info['tools'])}"

        if is_set:
            available.append(line)
        else:
            missing.append(line)

    lines.append("### Available")
    lines.extend(available or ["_None_"])

    lines.append("\n### Missing")
    lines.extend(missing or ["_None_"])

    lines.append("\n### To Request Missing Capabilities")
    lines.append("Use `request_api_key(provider='anthropic', purpose='Claude Code editing')`")

    return "\n".join(lines)


def get_tools() -> List[ToolEntry]:
    """Get tool request tools."""
    return [
        ToolEntry(
            name="request_capability",
            schema={
                "name": "request_capability",
                "description": (
                    "Request a new capability or resource. "
                    "Use when you encounter a limitation and need something to overcome it. "
                    "Requests are logged for review and fulfillment."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "capability": {
                            "type": "string",
                            "description": "What is needed (e.g., 'GitHub API access', 'database connection')",
                        },
                        "reason": {
                            "type": "string",
                            "description": "Why it's needed",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["low", "medium", "high", "critical"],
                            "default": "medium",
                        },
                    },
                    "required": ["capability", "reason"],
                },
            },
            handler=_request_capability,
            timeout_sec=10,
        ),
        ToolEntry(
            name="request_api_key",
            schema={
                "name": "request_api_key",
                "description": (
                    "Request an API key for a specific service. "
                    "Use when you need API access to perform a task. "
                    "Supports: anthropic, openai, github, serpapi"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "provider": {
                            "type": "string",
                            "description": "Service provider (anthropic, openai, github, serpapi)",
                        },
                        "purpose": {
                            "type": "string",
                            "description": "What the key will be used for",
                        },
                    },
                    "required": ["provider", "purpose"],
                },
            },
            handler=_request_api_key,
            timeout_sec=10,
        ),
        ToolEntry(
            name="list_tool_requests",
            schema={
                "name": "list_tool_requests",
                "description": "List pending tool or capability requests.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {
                            "type": "string",
                            "enum": ["all", "pending", "fulfilled", "rejected"],
                            "default": "all",
                        },
                    },
                },
            },
            handler=_list_tool_requests,
            timeout_sec=10,
        ),
        ToolEntry(
            name="check_capabilities",
            schema={
                "name": "check_capabilities",
                "description": (
                    "Check what capabilities are available vs missing. "
                    "Shows current API keys, tools, and what's not configured."
                ),
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_check_capabilities,
            timeout_sec=10,
        ),
    ]
