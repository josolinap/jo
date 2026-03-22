"""
Pi Prompts - Integration of .pi/prompts/ templates into Jo's skill system.

Loads prompt templates from .pi/prompts/ and registers them as skills
for specialized task execution.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, Optional

log = logging.getLogger(__name__)

# Pi prompts directory
PI_PROMPTS_DIR = Path(__file__).parent.parent / ".pi" / "prompts"

# Cache for loaded prompts
_prompt_cache: Dict[str, str] = {}


def load_pi_prompt(name: str) -> Optional[str]:
    """Load a prompt template from .pi/prompts/ directory.

    Args:
        name: Prompt file name (without .md extension)

    Returns:
        Prompt content or None if not found
    """
    if name in _prompt_cache:
        return _prompt_cache[name]

    prompt_path = PI_PROMPTS_DIR / f"{name}.md"

    if not prompt_path.exists():
        log.warning(f"Pi prompt not found: {prompt_path}")
        return None

    try:
        content = prompt_path.read_text(encoding="utf-8")
        _prompt_cache[name] = content
        log.info(f"Loaded pi prompt: {name}")
        return content
    except Exception as e:
        log.error(f"Failed to load pi prompt {name}: {e}")
        return None


def extract_prompt_content(raw_content: str) -> str:
    """Extract the actual prompt content, removing frontmatter.

    Args:
        raw_content: Raw markdown content with optional YAML frontmatter

    Returns:
        Prompt content without frontmatter
    """
    if not raw_content:
        return ""

    lines = raw_content.split("\n")

    # Check for frontmatter (starts with ---)
    if lines and lines[0].strip() == "---":
        # Find closing ---
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                # Return content after frontmatter
                return "\n".join(lines[i + 1 :]).strip()

    # No frontmatter, return as-is
    return raw_content.strip()


def extract_frontmatter(raw_content: str) -> Dict[str, str]:
    """Extract YAML frontmatter from prompt content.

    Args:
        raw_content: Raw markdown content

    Returns:
        Dictionary of frontmatter key-value pairs
    """
    frontmatter = {}

    if not raw_content:
        return frontmatter

    lines = raw_content.split("\n")

    if not lines or lines[0].strip() != "---":
        return frontmatter

    # Parse frontmatter
    in_frontmatter = True
    for i in range(1, len(lines)):
        line = lines[i].strip()

        if line == "---":
            # End of frontmatter
            break

        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter


def get_pr_review_prompt() -> Optional[str]:
    """Get the PR review prompt template."""
    content = load_pi_prompt("pr")
    return extract_prompt_content(content) if content else None


def get_changelog_prompt() -> Optional[str]:
    """Get the changelog generation prompt template."""
    content = load_pi_prompt("changelog")
    return extract_prompt_content(content) if content else None


def get_issue_prompt() -> Optional[str]:
    """Get the issue analysis prompt template."""
    content = load_pi_prompt("issue")
    return extract_prompt_content(content) if content else None


def get_audit_prompt() -> Optional[str]:
    """Get the self-audit prompt template."""
    content = load_pi_prompt("audit")
    return extract_prompt_content(content) if content else None


def register_pi_skills():
    """Register all pi prompts as skills with the skills system.

    This function should be called during initialization to make
    the pi prompts available as skills.
    """
    from ouroboros.tools.skills import Skill, register_skill

    # PR Review Skill
    pr_prompt = get_pr_review_prompt()
    if pr_prompt:
        register_skill(
            Skill(
                name="github-review",
                aliases=["github-review", "/github-review", "pr-review", "/pr-review", "review-pr"],
                description="Review GitHub pull requests with structured code analysis",
                system_prompt_addition=f"""You are now in CODE REVIEW mode.

Your job is to thoroughly review GitHub pull requests and provide actionable feedback.

{pr_prompt}

Always be technical and concise. Focus on actual bugs, security issues, and performance problems.""",
                enabled_tools=["repo_read", "grep", "git_diff", "web_fetch", "github"],
                pre_task_prompt="Before reviewing: Understand the codebase structure and what this PR is trying to achieve.",
                post_task_prompt="""Summarize your review with:

## Summary
[1-2 sentence overview]

## Critical Issues
[Any bugs, security issues, or regressions]

## Suggestions
[Improvements and recommendations]

## Verdict
[Approve / Request Changes / Needs Discussion]""",
                triggers=["review", "pr", "pull request", "code review"],
                version="1.0.0",
            )
        )
        log.info("Registered github-review skill from .pi/prompts/pr.md")

    # Changelog Skill
    changelog_prompt = get_changelog_prompt()
    if changelog_prompt:
        register_skill(
            Skill(
                name="changelog",
                aliases=["changelog", "/changelog", "generate-changelog", "/generate-changelog"],
                description="Generate changelog entries from git history",
                system_prompt_addition=f"""You are now in CHANGELOG GENERATION mode.

Your job is to analyze git history and generate proper changelog entries.

{changelog_prompt}

Always follow the format and include axis tags for tracking growth.""",
                enabled_tools=["repo_read", "git_log", "git_diff", "git_show"],
                pre_task_prompt="Before generating: Check the last release tag to understand what commits to include.",
                post_task_prompt="""Provide the changelog entry in the proper format with axis tags.""",
                triggers=["changelog", "release notes", "what's new"],
                version="1.0.0",
            )
        )
        log.info("Registered changelog skill from .pi/prompts/changelog.md")

    # Issue Analyzer Skill
    issue_prompt = get_issue_prompt()
    if issue_prompt:
        register_skill(
            Skill(
                name="issue-analyzer",
                aliases=["issue-analyzer", "/issue-analyzer", "analyze-issue", "/analyze-issue"],
                description="Analyze GitHub issues (bugs or feature requests)",
                system_prompt_addition=f"""You are now in ISSUE ANALYSIS mode.

Your job is to thoroughly analyze GitHub issues and propose solutions.

{issue_prompt}

Do NOT implement unless explicitly asked. Analyze and propose only.""",
                enabled_tools=["repo_read", "grep", "git_log", "web_fetch", "github"],
                pre_task_prompt="Before analyzing: Read the issue completely including all comments.",
                post_task_prompt="""Provide your analysis in the structured format with:
- Issue type and summary
- Root cause analysis
- Affected files
- Proposed fix (if applicable)""",
                triggers=["issue", "bug", "analyze issue", "feature request"],
                version="1.0.0",
            )
        )
        log.info("Registered issue-analyzer skill from .pi/prompts/issue.md")

    log.info("Pi prompts skills registration complete")


# Auto-register on import
try:
    register_pi_skills()
except Exception as e:
    log.warning(f"Failed to register pi skills on import: {e}")
