"""
Jo — Skill System.

Skills are behavior injections that modify how Jo operates.
Instead of swapping agents, skills add capabilities on top of existing tools.

Skill layers:
1. Guarantee Layer (optional) - e.g., ralph: "Cannot stop until verified done"
2. Enhancement Layer (0-N skills) - e.g., ultrawork (parallel), git-master (commits)
3. Execution Layer (primary skill) - e.g., default (build), orchestrate (coordinate)

Formula: [Execution Skill] + [0-N Enhancements] + [Optional Guarantee]
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class Skill:
    """A skill definition with triggers and behavior."""

    name: str
    description: str
    triggers: List[str]
    source: str  # "system", "extracted", "manual"
    layer: str = "enhancement"  # "guarantee", "enhancement", "execution"
    content: str = ""
    priority: int = 0
    enabled: bool = True

    def matches(self, text: str) -> bool:
        """Check if this skill should be triggered by the given text."""
        text_lower = text.lower()
        return any(trigger.lower() in text_lower for trigger in self.triggers)


class SkillManager:
    """Manages skills loading, matching, and injection."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._skills: List[Skill] = []
        self._project_skills_path = repo_dir / ".jo_skills"
        self._user_skills_path = pathlib.Path.home() / ".jo" / "skills"
        self._system_skills_path = pathlib.Path(__file__).parent / "system"
        self._load_skills()

    def _load_skills(self) -> None:
        """Load skills from all sources."""
        # System skills (highest priority)
        self._load_skills_from_dir(self._system_skills_path, source="system")

        # Project skills (medium priority)
        self._load_skills_from_dir(self._project_skills_path, source="project")

        # User skills (lowest priority)
        self._load_skills_from_dir(self._user_skills_path, source="user")

        # Built-in skills
        self._load_builtin_skills()

        log.info(f"Loaded {len(self._skills)} skills")

    def _load_skills_from_dir(self, path: pathlib.Path, source: str) -> None:
        """Load skills from a directory of markdown files."""
        if not path.exists() or not path.is_dir():
            return

        for md_file in path.glob("*.md"):
            try:
                content = md_file.read_text(encoding="utf-8", errors="ignore")
                skill = self._parse_skill_file(content, source, md_file.name)
                if skill:
                    self._skills.append(skill)
            except Exception as e:
                log.debug(f"Failed to load skill from {md_file}: {e}")

    def _parse_skill_file(self, content: str, source: str, filename: str) -> Optional[Skill]:
        """Parse a skill markdown file with YAML frontmatter."""
        # Check for YAML frontmatter
        frontmatter_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)

        if frontmatter_match:
            frontmatter_text = frontmatter_match.group(1)
            body = frontmatter_match.group(2)

            # Parse frontmatter (simple key: value parsing)
            frontmatter: Dict[str, Any] = {}
            for line in frontmatter_text.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    key = key.strip()
                    value = value.strip()

                    # Handle lists
                    if value.startswith("[") and value.endswith("]"):
                        # Parse list
                        items = value[1:-1].split(",")
                        frontmatter[key] = [item.strip().strip('"').strip("'") for item in items if item.strip()]
                    elif value.lower() in ("true", "false"):
                        frontmatter[key] = value.lower() == "true"
                    else:
                        try:
                            frontmatter[key] = int(value)
                        except ValueError:
                            try:
                                frontmatter[key] = float(value)
                            except ValueError:
                                frontmatter[key] = value

            return Skill(
                name=frontmatter.get("name", filename),
                description=frontmatter.get("description", ""),
                triggers=frontmatter.get("triggers", []),
                source=frontmatter.get("source", source),
                layer=frontmatter.get("layer", "enhancement"),
                content=body.strip(),
                priority=frontmatter.get("priority", 0),
                enabled=frontmatter.get("enabled", True),
            )
        else:
            # No frontmatter - treat entire file as skill content
            return Skill(
                name=filename,
                description=f"Skill from {filename}",
                triggers=[filename.replace(".md", "").lower()],
                source=source,
                content=content.strip(),
            )

    def _load_builtin_skills(self) -> None:
        """Load built-in skills."""
        builtin_skills = [
            Skill(
                name="anti_hallucination",
                description="Prevent hallucination and fabrication",
                triggers=["hallucination", "fabricate", "make up", "invent"],
                source="system",
                layer="guarantee",
                content="""## Anti-Hallucination Protocol

Before claiming ANY fact:
1. Check your data sources - What file/API actually contains this information?
2. Verify existence - Does the data actually exist in your context?
3. Admit uncertainty - If you don't have verified data, say "I don't have this information"

Forbidden:
- NEVER invent usernames, display names, or profile details
- NEVER fabricate dates, times, or timestamps not in your data
- NEVER claim changes happened without evidence in files/logs
- NEVER make up plausible-sounding narratives

When uncertain, say: "I don't have verified data for this. Let me check [specific source]."
""",
                priority=10,
            ),
            Skill(
                name="verification",
                description="Verify before claiming",
                triggers=["verify", "check", "confirm"],
                source="system",
                layer="guarantee",
                content="""## Verification Protocol

Before making any claim:
- About code: Run git log/diff to verify
- About files: Read the actual file first
- About system state: Run appropriate check commands
- About user identity: Check state.json for owner_id only

Example:
WRONG: "The code was updated recently"
RIGHT: "git log shows commit abc123 from 2 hours ago"
""",
                priority=9,
            ),
        ]
        self._skills.extend(builtin_skills)

    def match_skills(self, text: str) -> List[Skill]:
        """Find skills that match the given text."""
        matched = []
        for skill in self._skills:
            if skill.enabled and skill.matches(text):
                matched.append(skill)

        # Sort by priority (highest first), then by layer
        layer_order = {"guarantee": 0, "execution": 1, "enhancement": 2}
        matched.sort(key=lambda s: (-s.priority, layer_order.get(s.layer, 3)))

        return matched

    def get_active_skills(self, text: str) -> str:
        """Get formatted string of active skills for context injection."""
        matched = self.match_skills(text)
        if not matched:
            return ""

        parts = ["## Active Skills\n"]

        # Group by layer
        by_layer: Dict[str, List[Skill]] = {}
        for skill in matched:
            by_layer.setdefault(skill.layer, []).append(skill)

        for layer in ["guarantee", "execution", "enhancement"]:
            if layer in by_layer:
                parts.append(f"### {layer.title()} Layer")
                for skill in by_layer[layer]:
                    parts.append(f"\n#### {skill.name}")
                    parts.append(skill.content)
                parts.append("")

        return "\n".join(parts)

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all available skills."""
        return [
            {
                "name": s.name,
                "description": s.description,
                "source": s.source,
                "layer": s.layer,
                "triggers": s.triggers,
                "enabled": s.enabled,
            }
            for s in self._skills
        ]

    def add_skill(self, skill: Skill) -> None:
        """Add a new skill."""
        self._skills.append(skill)
        log.info(f"Added skill: {skill.name}")

    def remove_skill(self, name: str) -> bool:
        """Remove a skill by name."""
        before = len(self._skills)
        self._skills = [s for s in self._skills if s.name != name]
        return len(self._skills) < before


# Global skill manager instance
_manager: Optional[SkillManager] = None


def get_skill_manager(repo_dir: Optional[pathlib.Path] = None) -> SkillManager:
    """Get or create the global skill manager."""
    global _manager
    if _manager is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _manager = SkillManager(repo_dir)
    return _manager
