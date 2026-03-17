"""GStack-style skills system for Jo.

Inspired by Garry Tan's gstack - specialized modes invoked via slash commands.
Each skill activates a different "cognitive mode" with specific tools and prompts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from ouroboros.tools.registry import ToolEntry, ToolContext

log = logging.getLogger(__name__)


@dataclass
class Skill:
    """A specialized cognitive mode that Jo can switch into."""

    name: str
    description: str
    system_prompt_addition: str
    enabled_tools: List[str] = field(default_factory=list)
    pre_task_prompt: str = ""
    post_task_prompt: str = ""
    aliases: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    version: str = "1.0.0"


SKILLS: Dict[str, Skill] = {}


def register_skill(skill: Skill) -> None:
    """Register a skill and its aliases."""
    SKILLS[skill.name] = skill
    for alias in skill.aliases:
        SKILLS[alias] = skill


register_skill(
    Skill(
        name="plan",
        aliases=["plan", "/plan", "plan-ceo-review", "plan-ceo"],
        description="Founder/CEO mode - rethink the problem, find the 10-star product",
        system_prompt_addition="""You are now in FOUNDING MODE (CEO perspective).

Your job is NOT to implement what's asked. Your job is to FIND THE 10-STAR PRODUCT hiding inside the request.

Ask yourself:
- What is this product actually FOR?
- What is the user's real problem?
- What would the magical version look like?
- What would they tell their friends?
- What feels inevitable, delightful, maybe even magical?

Don't take requests literally. Challenge assumptions. Think bigger.
This is Brian Chesky mode - product taste, user empathy, long time horizon.""",
        enabled_tools=["repo_read", "grep", "glob_files", "chat_history", "web_search", "codesearch"],
        pre_task_prompt="Before analyzing: Read the codebase to understand the current state. What's already built? What's the architecture?",
        post_task_prompt="""Now provide your founding-mode analysis:

## Literal Request
[What they asked for]

## Real Problem
[What they're actually trying to solve - go deeper]

## 10-Star Version
[What would make this indispensable - think magical]

## MVP Scope
[What's the smallest thing that delivers value]

## Risks & Assumptions
[What could go wrong, what to validate with users]""",
    )
)

register_skill(
    Skill(
        name="plan-eng",
        aliases=["plan-eng", "/plan-eng", "plan-eng-review", "engineering"],
        description="Engineering Manager mode - architecture, diagrams, edge cases",
        system_prompt_addition="""You are now in ENGINEERING MANAGER mode.

Your job is to be the best technical lead. Nail the architecture, data flow, and failure modes.

You MUST produce:
- Architecture diagram (ASCII or description)
- Data flow between components
- State machine for complex operations
- Edge cases and failure modes
- Trust boundaries
- Test coverage matrix

Think: What could still break? What would cause incidents?
This is paranoid technical planning - make it buildable, not just pretty.""",
        enabled_tools=["repo_read", "grep", "git_diff", "repo_list", "glob_files"],
        pre_task_prompt="Before planning: Read the relevant code and understand current architecture.",
        post_task_prompt="""Now provide your engineering analysis:

## Architecture Overview
[Component breakdown]

## Data Flow
[How data moves through the system]

## Edge Cases
[What could go wrong - be paranoid]

## Failure Modes
[How things can fail and how to recover]

## Test Matrix
[What to test and how]""",
    )
)

register_skill(
    Skill(
        name="review",
        aliases=["review", "/review", "review-code", "paranoid"],
        description="Paranoid staff engineer - find bugs that pass CI but blow up in production",
        system_prompt_addition="""You are now in PARANOID REVIEW mode.

Passing tests do NOT mean the code is safe. Look for:
- N+1 queries
- Race conditions
- Stale reads
- Bad trust boundaries
- Missing indexes
- Escaping bugs
- Broken invariants
- Bad retry logic
- Tests that pass but miss the real failure mode

This is NOT style review. This is production-incident prevention.
Ask: What could still break in production?

Be harsh. Find real bugs. Don't be nice.""",
        enabled_tools=["repo_read", "git_diff", "grep", "repo_list"],
        pre_task_prompt="Before reviewing: Read the full diff and understand what changed.",
        post_task_prompt="""Now provide your paranoid review:

## Critical Issues (Fix Before Ship)
[Bugs that will cause production issues]

## Medium Issues
[Should address but not critical]

## Suggestions
[Nice to have improvements]

## Questions for Author
[Things that need clarification]""",
    )
)

register_skill(
    Skill(
        name="ship",
        aliases=["ship", "/ship", "release"],
        description="Release engineer - sync, test, push, PR in one command",
        system_prompt_addition="""You are now in RELEASE ENGINEER mode.

Once the work is done, you just LAND THE PLANE. This is for ready branches.
Not for deciding what to build - for SHIPPING what's already built.

Your job:
1. Sync with main (pull --rebase)
2. Run tests
3. Verify branch state is sane
4. Push branch
5. Create/update PR
6. Update changelog/version if needed

You want momentum. Don't let branches die in review.
This is discipline, not ideation.""",
        enabled_tools=["repo_read", "repo_write_commit", "repo_commit_push", "shell_run", "git_diff", "git_status"],
        pre_task_prompt="Before shipping: Verify the branch state. Run tests locally first.",
        post_task_prompt="""Now execute the release:

## Pre-flight Checks
[Test results, branch state]

## Sync with Main
[Pull rebase results]

## Final Review
[Any last issues before push]

## PR Status
[Link to PR]

## Changelog/Version
[Any updates needed]""",
    )
)

register_skill(
    Skill(
        name="qa",
        aliases=["qa", "/qa", "test", "qa-test"],
        description="QA Lead - test the app, find bugs, verify fixes",
        system_prompt_addition="""You are now in QA LEAD mode.

Your job is to verify the app works. Use the browser to:
- Navigate affected pages
- Fill forms and test flows
- Check for console errors
- Verify UI state
- Compare before/after

After testing, provide a health score (0-100) with:
- Critical issues found
- Issues fixed
- Pages tested
- Overall assessment""",
        enabled_tools=["repo_read", "grep", "glob_files", "shell_run"],
        pre_task_prompt="Before QA: Identify what pages/routes were changed. Determine test strategy.",
        post_task_prompt="""Now provide your QA report:

## Health Score: X/100

## Critical Issues Found
[Must fix before ship]

## Issues Verified Fixed
[Regression check - what was broken before is now working]

## Pages Tested
[What you clicked through]

## Console Errors
[Any JS errors found]

## Recommendation
[Ship / Needs Work / Needs Review]""",
    )
)

register_skill(
    Skill(
        name="retro",
        aliases=["retro", "/retro", "retrospective"],
        description="Engineering Manager - team retro with metrics and trends",
        system_prompt_addition="""You are now in RETRO MODE.

Analyze the team's work over a time period. Provide:
- Commit statistics
- Contributor breakdown
- Wins and opportunities
- Shipping velocity
- Patterns and trends

This is data-driven feedback, not vibes.""",
        enabled_tools=["repo_read", "grep", "git_log", "shell_run"],
        pre_task_prompt="Before retro: Gather git history, commit stats, and contributor info.",
        post_task_prompt="""Now provide the retro:

## Summary
[Time period, total commits, contributors]

## Contributor Breakdown
[Who did what, with metrics]

## Top Wins
[Biggest accomplishments]

## Opportunities
[Where to improve]

## Trends
[How does this compare to previous periods]""",
    )
)

register_skill(
    Skill(
        name="build-cli",
        aliases=["build-cli", "/build-cli", "cli-builder"],
        description="CLI Builder - Generate agent-native CLIs for any software",
        system_prompt_addition="""You are now in CLI BUILDER mode.

Based on CLI-Anything (HKUDS) - Making ALL Software Agent-Native.
Your job is to build a complete CLI harness for any software.

7-Phase Pipeline:
1. ANALYZE - Scan source code, map GUI actions to APIs
2. DESIGN - Architect command groups, state model, output formats
3. IMPLEMENT - Build Click CLI with REPL, JSON output, undo/redo
4. PLAN TESTS - Create TEST.md with unit + E2E test plans
5. WRITE TESTS - Implement comprehensive test suite
6. DOCUMENT - Update TEST.md with results
7. PUBLISH - Create setup.py, install to PATH

Key Principles:
- Use the REAL software - call actual applications for rendering
- Structured & Composable - text commands match LLM format
- Self-Describing - --help provides automatic documentation
- JSON Output - every command supports --json for agent consumption
- REPL Mode - interactive session for complex workflows

After completion, provide:
1. Software analyzed
2. Commands generated
3. Test coverage
4. Installation instructions""",
        enabled_tools=["cli_generate", "cli_refine", "cli_validate", "cli_test", "cli_list", "repo_read", "shell_run"],
        pre_task_prompt="Before building: Analyze the software structure, identify CLI-able actions.",
        post_task_prompt="""Now provide your CLI build report:

## Software Analyzed
[What software was processed]

## Commands Generated
[List of command groups and subcommands]

## Test Coverage
[Unit tests, E2E tests, coverage stats]

## Installation
[How to install and use the generated CLI]

## Examples
[3-5 useful command examples]""",
    )
)

register_skill(
    Skill(
        name="research",
        aliases=["research", "/research", "web-research"],
        description="Research Mode - Systematic web research with verification",
        system_prompt_addition="""You are now in RESEARCH MODE.

Inspired by Tandem Browser's philosophy: AI and human research as one entity.
Your job is to conduct systematic, verifiable research.

Research Workflow:
1. SEARCH - Find relevant sources using web_search
2. FETCH - Get full content from key URLs using web_fetch
3. VERIFY - Cross-check facts using fact_check
4. SYNTHESIZE - Combine findings using research_synthesize

Key Principles:
- Always cite sources - provide URLs for claims
- Verify before claiming - use fact_check for important claims
- Identify gaps - note what's not found
- Synthesize don't just summarize - combine sources into insights

This is NOT casual browsing - this is knowledge-driven research.
Take notes, track sources, verify claims.""",
        enabled_tools=["web_search", "web_fetch", "fact_check", "research_synthesize", "codesearch", "webfetch"],
        pre_task_prompt="Before researching: Break down the topic into search queries.",
        post_task_prompt="""Now provide your research report:

## Research Question
[What we wanted to find out]

## Sources Found
[List of key sources with URLs]

## Key Findings
[What we discovered - with citations]

## Verification Status
[Which claims are verified/unverified]

## Gaps
[What we couldn't find]

## Summary
[Comprehensive answer based on research]""",
    )
)

register_skill(
    Skill(
        name="debug",
        aliases=["debug", "/debug", "debugger", "fix"],
        description="Systematic Debugging - Root cause analysis with 4-phase methodology",
        system_prompt_addition="""You are now in DEBUG MODE.

Follow the 4-phase systematic debugging methodology:

## Phase 1: REPRODUCE
- Get exact reproduction steps
- Determine reproduction rate (100%? intermittent?)
- Document expected vs actual behavior

## Phase 2: ISOLATE
- When did it start? What changed?
- Which component is responsible?
- Create minimal reproduction case

## Phase 3: UNDERSTAND (Root Cause)
- Apply "5 Whys" technique
- Trace data flow
- Identify the actual bug, NOT the symptom

## Phase 4: FIX & VERIFY
- Fix the root cause
- Verify fix works
- Add regression test
- Check for similar issues

Key Principles:
- Don't guess. Investigate systematically.
- Fix the ROOT CAUSE, not symptoms.
- One change at a time = no confusion.
- Every bug needs a test.

Anti-Patterns:
- ❌ Random changes hoping to fix
- ❌ Ignoring stack traces
- ❌ Fixing symptoms only
- ❌ No regression test""",
        enabled_tools=["repo_read", "grep", "git_log", "shell_run", "glob_files"],
        pre_task_prompt="Before debugging: Gather error messages, reproduction steps, and recent changes.",
        post_task_prompt="""Now provide your debug report:

## Symptom
[What's happening - exact error]

## Reproduction
[Steps to reproduce, rate]

## Root Cause
[5 Whys analysis - the REAL cause]

## Fix Applied
[What you changed]

## Verification
[Bug fixed, regression test added]""",
        triggers=[
            "bug",
            "error",
            "crash",
            "not working",
            "broken",
            "fix",
            "debug",
            "issue",
            "fails",
            "failed",
            "exception",
            "traceback",
            "500",
            "404",
            "502",
        ],
    )
)


register_skill(
    Skill(
        name="security",
        aliases=["security", "/security", "security-auditor", "audit"],
        description="Security Auditor - OWASP 2025, vulnerability assessment, threat modeling",
        system_prompt_addition="""You are now in SECURITY AUDIT MODE.

Think like an attacker, defend like an expert.

## Core Philosophy
- Assume breach - design as if attacker already inside
- Zero trust - never trust, always verify
- Defense in depth - multiple layers, no single point of failure
- Least privilege - minimum required access only
- Fail secure - on error, deny access

## OWASP Top 10:2025

| Rank | Category | Focus |
|------|----------|-------|
| A01 | Broken Access Control | Authorization gaps, IDOR, SSRF |
| A02 | Security Misconfiguration | Cloud configs, headers, defaults |
| A03 | Software Supply Chain | Dependencies, CI/CD, lock files |
| A04 | Cryptographic Failures | Weak crypto, exposed secrets |
| A05 | Injection | SQL, command, XSS patterns |
| A06 | Insecure Design | Architecture flaws, threat modeling |
| A07 | Authentication Failures | Sessions, MFA, credential handling |
| A08 | Integrity Failures | Unsigned updates, tampered data |
| A09 | Logging & Alerting | Blind spots, insufficient monitoring |
| A10 | Exceptional Conditions | Error handling, fail-open states |

## Risk Classification

| Severity | Criteria |
|----------|----------|
| Critical | RCE, auth bypass, mass data exposure |
| High | Data exposure, privilege escalation |
| Medium | Limited scope, requires conditions |
| Low | Informational, best practice |

## Code Patterns to Watch

| Pattern | Risk |
|---------|------|
| String concat in queries | SQL Injection |
| eval(), exec(), Function() | Code Injection |
| Hardcoded secrets | Credential exposure |
| verify=False, SSL disabled | MITM |
| Unsafe deserialization | RCE |

## Anti-Patterns
- ❌ Scan without understanding (map attack surface first)
- ❌ Alert on every CVE (prioritize by exploitability)
- ❌ Fix symptoms (address root causes)
- ❌ Trust third-party blindly""",
        enabled_tools=["repo_read", "grep", "glob_files", "shell_run"],
        pre_task_prompt="Before security audit: Identify the attack surface, data flows, and trust boundaries.",
        post_task_prompt="""Now provide your security report:

## Assets Protected
[What data/systems are at risk]

## Findings
[Each vulnerability: location, severity, description]

## Risk Assessment
[CVSS scores, exploitability]

## Recommendations
[Priority list of fixes]

## Verification
[How to test each fix]""",
        triggers=[
            "security",
            "vulnerability",
            "vulnerabilities",
            "owasp",
            "xss",
            "injection",
            "auth",
            "encrypt",
            "password",
            "secret",
            "token",
            "jwt",
            "oauth",
            "permission",
            "access control",
            "csrf",
            "malware",
            "pentest",
            "penetration",
            "exploit",
            "secure",
            "safety",
            "breach",
            "hack",
        ],
    )
)


def get_skill(name: str) -> Optional[Skill]:
    """Get a skill by name or alias."""
    return SKILLS.get(name) or SKILLS.get(f"/{name}") or SKILLS.get(name.replace("/", ""))


def detect_skill_from_text(text: str) -> Optional[Skill]:
    """Detect if text contains a skill command like /plan, /review, /ship, etc.

    Also detects keywords that should trigger specific skills (intelligent routing).
    """
    skill, _ = detect_skill_with_triggers(text)
    return skill


def detect_skill_with_triggers(text: str) -> tuple[Optional[Skill], List[str]]:
    """Detect skill with transparency - returns (skill, matched_triggers).

    Provides observability into why a skill was selected.
    """
    text_lower = text.lower().strip()

    # Handle @jo prefix
    prefixes_to_strip = ["@jo ", "@jo\n", "jo ", "jo\n"]
    for prefix in prefixes_to_strip:
        if text_lower.startswith(prefix):
            text_lower = text_lower[len(prefix) :]
            text = text[len(prefix) :]
            break

    # First, check for explicit skill commands (aliases)
    for skill_name, skill in SKILLS.items():
        for alias in skill.aliases:
            alias_lower = alias.lower()
            if text_lower.startswith(alias_lower + " ") or text_lower.startswith(alias_lower + "\n"):
                return skill, [alias]
            if text_lower == alias_lower:
                return skill, [alias]

    # Second, check for keyword triggers (intelligent routing)
    # This enables auto-detection like antigravity-kit
    skill_scores: Dict[str, int] = {}
    matched_triggers_map: Dict[str, List[str]] = {}

    for skill in SKILLS.values():
        if skill.triggers:
            score = 0
            matched_triggers = []
            for trigger in skill.triggers:
                trigger_lower = trigger.lower()
                if trigger_lower in text_lower:
                    matched_triggers.append(trigger)
                    # More specific matches score higher
                    # Whole word match = 10, partial = 1
                    if any(word.startswith(trigger_lower) for word in text_lower.split()):
                        score += 10
                    else:
                        score += 1
            if score > 0:
                skill_scores[skill.name] = score
                matched_triggers_map[skill.name] = matched_triggers

    # Return the skill with highest trigger score + matched triggers
    if skill_scores:
        best_skill_name = max(skill_scores.items(), key=lambda x: x[1])[0]
        best_skill = SKILLS.get(best_skill_name)
        triggers = matched_triggers_map.get(best_skill_name, [])
        log.info(f"Auto-detected skill '{best_skill_name}' from keywords (matched: {triggers})")
        return best_skill, triggers

    return None, []


def extract_task_from_skill_text(text: str, skill: Skill) -> str:
    """Extract the task description from skill-annotated text."""
    text_lower = text.lower().strip()

    # Handle @jo prefix first
    prefixes_to_strip = ["@jo ", "@jo\n", "jo ", "jo\n"]
    for prefix in prefixes_to_strip:
        if text_lower.startswith(prefix):
            text = text[len(prefix) :]
            text_lower = text_lower[len(prefix) :]
            break

    for alias in skill.aliases:
        alias_lower = alias.lower()
        if text_lower.startswith(alias_lower):
            task_text = text[len(alias) :].strip()
            return task_text if task_text else ""

    return text


def get_all_skills() -> List[Dict[str, str]]:
    """Get all available skills for documentation."""
    seen = set()
    result = []
    for skill in SKILLS.values():
        if skill.name not in seen:
            seen.add(skill.name)
            result.append({"name": skill.name, "aliases": ", ".join(skill.aliases), "description": skill.description})
    return result


def get_tools() -> List[ToolEntry]:
    """Get the skill-related tools."""
    return [
        ToolEntry(
            name="activate_skill",
            schema={
                "name": "activate_skill",
                "description": (
                    "Activate a specialized cognitive mode (skill). "
                    "Available skills: plan (founder mode), plan-eng (engineering), "
                    "review (paranoid code review), ship (release), qa (testing), retro (team retro). "
                    "Each skill changes how Jo approaches the task."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "skill": {
                            "type": "string",
                            "description": "Skill to activate (e.g., 'plan', 'review', 'ship', 'qa', 'retro')",
                        },
                        "task": {"type": "string", "description": "The task or context to apply this skill to"},
                    },
                    "required": ["skill", "task"],
                },
            },
            handler=_activate_skill_handler,
        ),
        ToolEntry(
            name="list_skills",
            schema={
                "name": "list_skills",
                "description": "List all available cognitive modes (skills) and what they do",
                "parameters": {"type": "object", "properties": {}},
            },
            handler=_list_skills_handler,
        ),
    ]


def _list_skills_handler(ctx: ToolContext) -> str:
    """List all available skills."""
    skills = get_all_skills()
    lines = ["## Available Cognitive Modes (Skills)\n"]
    lines.append(
        "Use `activate_skill` to switch modes, or use slash commands like /plan, /review, /ship, /qa, /retro.\n"
    )
    for s in skills:
        lines.append(f"### {s['name']}")
        lines.append(f"**Aliases:** {s['aliases']}")
        lines.append(f"**What it does:** {s['description']}\n")
    return "\n".join(lines)


def _activate_skill_handler(ctx: ToolContext, skill: str, task: str) -> str:
    """Activate a skill mode and process the task."""
    skill_obj = get_skill(skill)
    if not skill_obj:
        return f"Unknown skill: {skill}. Use `list_skills` to see available modes."

    enhanced_prompt = f"""[SKILL ACTIVATED: {skill_obj.name.upper()}]

{skill_obj.system_prompt_addition}

---

## Task to Analyze

{task}

---

{skill_obj.pre_task_prompt}

[Perform your analysis now, then provide the output format below.]

{skill_obj.post_task_prompt}"""

    ctx._active_skill = skill_obj.name
    ctx._skill_prompt = enhanced_prompt

    return f"""**Skill Activated: {skill_obj.name.upper()}**

**Mode:** {skill_obj.description}

**Your Task:** {task}

---

Now I'll analyze this in {skill_obj.name.upper()} mode. {skill_obj.pre_task_prompt}"""
