"""
Jo — Capability Gap Detection.

Realizes Principle 5 (Minimalism) + Principle 0 (Agency):
Jo knows what it can't do before starting tasks.

Before accepting a task, Jo checks if required tools/capabilities exist.
If gap detected: "I can't do X because I lack Y. I can Z instead."
Auto-suggests capability creation via tool synthesis.

This prevents:
- Wasted budget on impossible tasks
- Hallucinated capabilities
- Frustrating user experiences
"""

from __future__ import annotations

import json
import logging
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


@dataclass
class CapabilityGap:
    """A detected capability gap."""

    required: str  # What the task requires
    missing: str  # What Jo lacks
    confidence: float  # How confident we are this is a real gap
    suggestion: str  # What Jo can do instead
    can_create: bool  # Can Jo create this capability via tool synthesis?


class CapabilityGapDetector:
    """Detects capability gaps before task execution."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self._known_capabilities = self._load_capabilities()
        self._gap_history: List[CapabilityGap] = []

    def _load_capabilities(self) -> Dict[str, Any]:
        """Load Jo's known capabilities from tools and skills."""
        capabilities = {
            "tools": set(),
            "skills": set(),
            "knowledge_domains": set(),
            "external_apis": set(),
        }

        # Load registered tools
        try:
            from ouroboros.tools.registry import ToolRegistry

            registry = ToolRegistry(repo_dir=self.repo_dir, drive_root=self.repo_dir)
            tools = registry.available_tools()
            capabilities["tools"] = {t["function"]["name"] for t in tools}
        except Exception:
            log.debug("Failed to load tool capabilities", exc_info=True)

        # Load skills
        try:
            from ouroboros.skills.skill_manager import get_skill_manager

            skill_mgr = get_skill_manager(self.repo_dir)
            skills = skill_mgr.list_skills()
            capabilities["skills"] = {s["name"] for s in skills}
        except Exception:
            log.debug("Failed to load skill capabilities", exc_info=True)

        # Load knowledge domains from vault
        vault_dir = self.repo_dir / "vault"
        if vault_dir.exists():
            for category in vault_dir.iterdir():
                if category.is_dir():
                    capabilities["knowledge_domains"].add(category.name)

        return capabilities

    def detect_gaps(self, task_text: str) -> List[CapabilityGap]:
        """Detect capability gaps in a task description."""
        gaps = []

        # Check for external API requirements
        api_patterns = [
            (r"\b(Twitter|X|Facebook|Instagram|LinkedIn|GitHub|Slack|Discord|Telegram)\b API", "social_media_api"),
            (r"\b(S3|GCS|Azure Blob)\b", "cloud_storage"),
            (r"\b(Stripe|PayPal|Square)\b", "payment_processing"),
            (r"\b(SendGrid|Mailgun|SES)\b", "email_service"),
            (r"\b(Twilio|Vonage)\b", "sms_service"),
            (r"\b(OpenAI|Anthropic|Google|Cohere)\b API", "llm_api"),
        ]

        for pattern, api_name in api_patterns:
            if re.search(pattern, task_text, re.IGNORECASE):
                if api_name not in self._known_capabilities["external_apis"]:
                    gaps.append(
                        CapabilityGap(
                            required=f"Access to {api_name}",
                            missing=f"No {api_name} integration",
                            confidence=0.8,
                            suggestion=f"I can help you design the integration, but I need API credentials first.",
                            can_create=True,
                        )
                    )

        # Check for file format requirements
        format_patterns = [
            (r"\b(PDF|Excel|CSV|JSON|XML|YAML|Markdown)\b", "file_format"),
            (r"\b(image|photo|video|audio)\b", "media_processing"),
            (r"\b(database|SQL|NoSQL)\b", "database"),
            (r"\b(browser|web scraping|crawl)\b", "web_automation"),
        ]

        for pattern, format_name in format_patterns:
            if re.search(pattern, task_text, re.IGNORECASE):
                # Check if we have tools for this
                has_capability = any(format_name.lower() in tool.lower() for tool in self._known_capabilities["tools"])
                if not has_capability:
                    gaps.append(
                        CapabilityGap(
                            required=f"{format_name} processing",
                            missing=f"No {format_name} tools",
                            confidence=0.7,
                            suggestion=f"I can help you plan the {format_name} processing, but I'll need to create tools first.",
                            can_create=True,
                        )
                    )

        # Check for complexity requirements
        if len(task_text) > 1000:
            gaps.append(
                CapabilityGap(
                    required="Complex task handling",
                    missing="Task may be too complex for single execution",
                    confidence=0.6,
                    suggestion="Let me break this down into smaller subtasks first.",
                    can_create=False,
                )
            )

        # Check for real-time requirements
        real_time_patterns = [r"\b(real-time|live|streaming|instant)\b"]
        for pattern in real_time_patterns:
            if re.search(pattern, task_text, re.IGNORECASE):
                gaps.append(
                    CapabilityGap(
                        required="Real-time processing",
                        missing="Jo is not a real-time system",
                        confidence=0.9,
                        suggestion="I can process data in batches, but not in real-time. Let me suggest an alternative approach.",
                        can_create=False,
                    )
                )

        self._gap_history.extend(gaps)
        return gaps

    def get_gap_report(self, task_text: str) -> str:
        """Generate a capability gap report for a task."""
        gaps = self.detect_gaps(task_text)

        if not gaps:
            return "✅ No capability gaps detected. I have the tools and knowledge to handle this task."

        parts = ["## Capability Gap Analysis\n"]
        parts.append(f"Found {len(gaps)} potential gap(s):\n")

        for i, gap in enumerate(gaps, 1):
            confidence_icon = {0.9: "🔴", 0.8: "🟠", 0.7: "🟡", 0.6: "🟢"}.get(gap.confidence, "⚪")
            parts.append(f"{i}. {confidence_icon} **{gap.required}**")
            parts.append(f"   Missing: {gap.missing}")
            parts.append(f"   Suggestion: {gap.suggestion}")
            if gap.can_create:
                parts.append(f"   ✅ I can create this capability via tool synthesis")
            parts.append("")

        return "\n".join(parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get capability gap detection statistics."""
        return {
            "total_gaps_detected": len(self._gap_history),
            "known_tools": len(self._known_capabilities.get("tools", set())),
            "known_skills": len(self._known_capabilities.get("skills", set())),
            "known_domains": len(self._known_capabilities.get("knowledge_domains", set())),
        }


# Global detector instance
_detector: Optional[CapabilityGapDetector] = None


def get_gap_detector(repo_dir: Optional[pathlib.Path] = None) -> CapabilityGapDetector:
    """Get or create the global capability gap detector."""
    global _detector
    if _detector is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _detector = CapabilityGapDetector(repo_dir)
    return _detector
