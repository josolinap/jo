"""Soft Rule Engine (TTSR) for Jo.

Loads and injects behavioral rules based on task context and tags.
Rules are stored as markdown files in .jo_rules/
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Set

log = logging.getLogger(__name__)

class RuleEngine:
    """Manages injection of domain-specific behavioral rules."""

    def __init__(self, repo_dir: Path):
        self.repo_dir = repo_dir
        self.rules_dir = repo_dir / ".jo_rules"
        self._rules_cache: Dict[str, str] = {}
        self._load_all()

    def _load_all(self):
        """Load all markdown rules from .jo_rules/"""
        if not self.rules_dir.exists():
            return

        for rule_file in self.rules_dir.glob("*.md"):
            try:
                content = rule_file.read_text(encoding="utf-8")
                self._rules_cache[rule_file.stem.lower()] = content
            except Exception as e:
                log.warning(f"Failed to load rule {rule_file.name}: {e}")

    def get_relevant_rules(self, active_tags: Set[str]) -> str:
        """Return combined string of rules matching the provided tags."""
        matched = []
        for tag in active_tags:
            rule_key = tag.lower()
            if rule_key in self._rules_cache:
                matched.append(f"### Rule: {tag}\n{self._rules_cache[rule_key]}")
        
        if not matched:
            # Load default rule if exists
            if "default" in self._rules_cache:
                matched.append(self._rules_cache["default"])
        
        return "\n\n".join(matched)

    def refresh(self):
        """Reload rules from disk."""
        self._rules_cache.clear()
        self._load_all()

def get_rule_engine(repo_dir: Path) -> RuleEngine:
    return RuleEngine(repo_dir)
