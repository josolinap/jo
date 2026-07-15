"""
Repo Pack tool — exposes ouroboros.repo_pack as a Jo tool.

Jo can call `repo_pack` to pack the entire codebase (or a subset) into
a single LLM-friendly file. This is useful for:
- Giving the LLM a complete view of the codebase in one context
- Generating documentation or architecture overviews
- Security auditing (detect secrets before they leak)
- Token budget management (know exactly how many tokens a codebase costs)
"""

from __future__ import annotations

import json
import logging
import pathlib
from typing import Any, Dict, List

from ouroboros.repo_pack import pack_repository, PackResult
from ouroboros.tools.registry import ToolContext, ToolEntry

log = logging.getLogger(__name__)


def _repo_pack(
    ctx: ToolContext,
    format: str = "xml",
    compress: bool = False,
    include: str = "",
    ignore: str = "",
    include_vault: bool = False,
    max_files: int = 500,
    max_tokens: int = 0,
    security_check: bool = True,
    output_file: str = "",
) -> str:
    """Pack the repository into a single LLM-friendly file.

    Args:
        format: Output format — "xml", "markdown", "json", or "plain"
        compress: If True, compress Python files (signatures only, ~90% token reduction)
        include: Comma-separated glob patterns to include (e.g. "ouroboros/**/*.py")
        ignore: Comma-separated glob patterns to ignore
        include_vault: If True, include vault/ markdown files
        max_files: Maximum files to pack (default 500)
        max_tokens: Token budget limit (0 = no limit)
        security_check: If True, scan for secrets and flag files
        output_file: If set, write output to this file instead of returning it

    Returns:
        Summary string with stats, or the packed output if output_file is empty
    """
    repo_dir = ctx.repo_dir

    include_patterns = [p.strip() for p in include.split(",") if p.strip()] if include else None
    ignore_patterns = [p.strip() for p in ignore.split(",") if p.strip()] if ignore else None

    result = pack_repository(
        root=repo_dir,
        output_format=format,
        compress=compress,
        include_patterns=include_patterns,
        ignore_patterns=ignore_patterns,
        include_vault=include_vault,
        max_files=max_files,
        max_tokens=max_tokens if max_tokens > 0 else None,
        security_check=security_check,
    )

    # If output_file specified, write to it and return summary
    if output_file:
        out_path = pathlib.Path(output_file)
        if not out_path.is_absolute():
            out_path = repo_dir / output_file
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(result.output, encoding="utf-8")
        return _format_summary(result, str(out_path))

    # If output is small enough, return it directly
    if result.total_tokens < 50000:
        return result.output

    # Otherwise, return summary with stats
    return _format_summary(result, None) + "\n\n(Output too large to return directly. Use output_file parameter to save to disk.)"


def _format_summary(result: PackResult, output_path: str | None) -> str:
    """Format a summary of the pack result."""
    lines = ["## Repository Pack Summary"]
    lines.append("")
    lines.append(f"- **Format**: {result.format}")
    lines.append(f"- **Total files**: {result.total_files}")
    lines.append(f"- **Total tokens**: {result.total_tokens:,}")
    lines.append(f"- **Total lines**: {result.total_lines:,}")
    lines.append(f"- **Total size**: {result.total_size:,} bytes")
    lines.append(f"- **Compressed files**: {sum(1 for f in result.files if f.is_compressed)}")
    lines.append(f"- **Binary files**: {sum(1 for f in result.files if f.is_binary)}")

    if result.security_warnings:
        lines.append(f"- **⚠️ Security warnings**: {len(result.security_warnings)}")
        for w in result.security_warnings[:5]:
            lines.append(f"  - {w}")
    else:
        lines.append("- **Security**: ✓ No secrets detected")

    if output_path:
        lines.append(f"- **Output written to**: `{output_path}`")

    lines.append("")
    lines.append("### Top Files by Tokens")
    for tf in result.top_files[:10]:
        lines.append(f"- `{tf['tokens']:>6}` tokens | `{tf['lines']:>6}` lines | {tf['path']}")

    lines.append("")
    lines.append("### Directory Structure")
    lines.append("```")
    lines.append(result.directory_tree[:2000])  # Truncate very large trees
    if len(result.directory_tree) > 2000:
        lines.append("... (truncated)")
    lines.append("```")

    return "\n".join(lines)


def get_tools() -> List[ToolEntry]:
    """Register repo_pack tool."""
    return [
        ToolEntry(
            name="repo_pack",
            schema={
                "name": "repo_pack",
                "description": (
                    "Pack the repository into a single LLM-friendly file. "
                    "Gives a complete view of the codebase in one structured document. "
                    "Supports XML, Markdown, JSON, and plain text formats. "
                    "Python files can be compressed (AST signatures only) for ~90% token reduction. "
                    "Includes secret detection to prevent leaking API keys. "
                    "Use this when you need to understand the whole codebase, "
                    "generate documentation, or audit for secrets."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "format": {
                            "type": "string",
                            "enum": ["xml", "markdown", "json", "plain"],
                            "default": "xml",
                            "description": "Output format",
                        },
                        "compress": {
                            "type": "boolean",
                            "default": False,
                            "description": "Compress Python files (signatures only, ~90% token reduction)",
                        },
                        "include": {
                            "type": "string",
                            "description": "Comma-separated glob patterns to include (e.g. 'ouroboros/**/*.py')",
                        },
                        "ignore": {
                            "type": "string",
                            "description": "Comma-separated glob patterns to ignore",
                        },
                        "include_vault": {
                            "type": "boolean",
                            "default": False,
                            "description": "Include vault/ markdown files",
                        },
                        "max_files": {
                            "type": "integer",
                            "default": 500,
                            "description": "Maximum files to pack",
                        },
                        "max_tokens": {
                            "type": "integer",
                            "default": 0,
                            "description": "Token budget limit (0 = no limit)",
                        },
                        "security_check": {
                            "type": "boolean",
                            "default": True,
                            "description": "Scan for secrets and flag files",
                        },
                        "output_file": {
                            "type": "string",
                            "description": "If set, write output to this file instead of returning it",
                        },
                    },
                },
            },
            handler=_repo_pack,
        ),
    ]
