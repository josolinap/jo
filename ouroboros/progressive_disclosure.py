"""
Jo — Progressive Skill Disclosure.

Inspired by Claude Code's skill system with path filters.
Skills with path filters start hidden, and only become visible when
the model touches matching files. This keeps the initial tool list
small and relevant — Jo doesn't get overwhelmed with 252 tools on startup.

How it works:
1. Skills define `paths` patterns (glob patterns)
2. When Jo reads/writes a file matching a pattern, the skill becomes visible
3. Skills are progressively disclosed as Jo explores the codebase
4. Core skills are always visible; specialized skills appear on demand
"""

from __future__ import annotations

import fnmatch
import logging
import pathlib
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


@dataclass
class ProgressiveSkill:
    """A skill with progressive disclosure."""

    name: str
    description: str
    paths: List[str] = field(default_factory=list)  # Glob patterns
    always_visible: bool = False  # Core skills are always visible
    revealed: bool = False  # Has this skill been revealed yet?
    context: str = "inline"  # inline, hidden, on-demand
    allowed_tools: List[str] = field(default_factory=list)
    when_to_use: str = ""


class ProgressiveDisclosure:
    """Manages progressive skill disclosure based on file access patterns."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._skills: List[ProgressiveSkill] = []
        self._accessed_files: Set[str] = set()
        self._revealed_skills: Set[str] = set()
        self._load_skills()

    def _load_skills(self) -> None:
        """Load skills from .jo_skills/ directory."""
        skills_dir = self.repo_dir / ".jo_skills"
        if not skills_dir.exists():
            return

        for md_file in skills_dir.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                skill = self._parse_skill_file(content, md_file.name)
                if skill:
                    self._skills.append(skill)
            except Exception as e:
                log.debug(f"Failed to load skill from {md_file}: {e}")

        # Add core skills that are always visible
        core_skills = [
            ProgressiveSkill(
                name="anti_hallucination",
                description="Prevent hallucination and fabrication",
                always_visible=True,
                revealed=True,
                when_to_use="Before claiming any fact",
            ),
            ProgressiveSkill(
                name="verification",
                description="Verify before claiming",
                always_visible=True,
                revealed=True,
                when_to_use="Before making any claim",
            ),
        ]
        self._skills.extend(core_skills)

    def _parse_skill_file(self, content: str, filename: str) -> Optional[ProgressiveSkill]:
        """Parse a skill markdown file with YAML frontmatter."""
        import re

        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)

        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            body = frontmatter_match.group(2)

            # Parse frontmatter
            frontmatter: Dict[str, Any] = {}
            for line in frontmatter_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    if value.startswith("[") and value.endswith("]"):
                        items = value[1:-1].split(",")
                        frontmatter[key] = [item.strip().strip('"').strip("'") for item in items if item.strip()]
                    elif value.lower() in ("true", "false"):
                        frontmatter[key] = value.lower() == "true"
                    else:
                        try:
                            frontmatter[key] = int(value)
                        except ValueError:
                            frontmatter[key] = value

            return ProgressiveSkill(
                name=frontmatter.get("name", filename),
                description=frontmatter.get("description", ""),
                paths=frontmatter.get("paths", []),
                always_visible=frontmatter.get("always_visible", False),
                revealed=frontmatter.get("always_visible", False),
                context=frontmatter.get("context", "inline"),
                allowed_tools=frontmatter.get("allowed-tools", []),
                when_to_use=frontmatter.get("when-to-use", ""),
            )
        else:
            return ProgressiveSkill(
                name=filename,
                description=f"Skill from {filename}",
                always_visible=True,
                revealed=True,
            )

    def record_file_access(self, file_path: str) -> List[str]:
        """Record file access and reveal matching skills."""
        self._accessed_files.add(file_path)
        newly_revealed = []

        for skill in self._skills:
            if skill.revealed or skill.always_visible:
                continue

            for pattern in skill.paths:
                if fnmatch.fnmatch(file_path, pattern):
                    skill.revealed = True
                    self._revealed_skills.add(skill.name)
                    newly_revealed.append(skill.name)
                    log.info(
                        f"[ProgressiveDisclosure] Revealed skill: {skill.name} (matched {file_path} with {pattern})"
                    )
                    break

        return newly_revealed

    def get_visible_skills(self) -> List[ProgressiveSkill]:
        """Get all currently visible skills."""
        return [s for s in self._skills if s.always_visible or s.revealed]

    def get_hidden_skills(self) -> List[ProgressiveSkill]:
        """Get all currently hidden skills."""
        return [s for s in self._skills if not s.always_visible and not s.revealed]

    def get_skill_context(self) -> str:
        """Get formatted skill context for injection."""
        visible = self.get_visible_skills()
        if not visible:
            return ""

        parts = ["## Available Skills\n"]
        for skill in visible:
            parts.append(f"### {skill.name}")
            if skill.when_to_use:
                parts.append(f"**When to use**: {skill.when_to_use}")
            if skill.description:
                parts.append(f"**Description**: {skill.description}")
            if skill.allowed_tools:
                parts.append(f"**Allowed tools**: {', '.join(skill.allowed_tools)}")
            parts.append("")

        hidden = self.get_hidden_skills()
        if hidden:
            parts.append(f"## Hidden Skills ({len(hidden)} skills)")
            parts.append("These skills will become visible when you access relevant files.\n")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get progressive disclosure statistics."""
        return {
            "total_skills": len(self._skills),
            "visible_skills": len(self.get_visible_skills()),
            "hidden_skills": len(self.get_hidden_skills()),
            "accessed_files": len(self._accessed_files),
            "revealed_skills": list(self._revealed_skills),
        }


# Global disclosure instance
_disclosure: Optional[ProgressiveDisclosure] = None


def get_disclosure(repo_dir: Optional[pathlib.Path] = None) -> ProgressiveDisclosure:
    """Get or create the global progressive disclosure."""
    global _disclosure
    if _disclosure is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _disclosure = ProgressiveDisclosure(repo_dir)
    return _disclosure
