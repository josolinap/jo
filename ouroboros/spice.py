"""Spice system for Jo - targeted prompt injections based on quality issues.

Phase 2: Targeted spices based on Response Analyzer feedback.
- Random spices for general freshness
- Targeted spices for specific quality issues
- Categories: hallucination, drift, avoidance, overconfidence

The system:
1. Response Analyzer detects issues
2. Targeted spice is injected based on issue type
3. Generic spice as fallback
"""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any, Dict, List, Optional

import os

# Default spice path
DEFAULT_SPICE_PATH = "~/.ouroborous/spice.json"


# Default spice categories for Jo (coding agent)
DEFAULT_SPICES: Dict[str, List[str]] = {
    "thinking": [
        "Consider: Is there a simpler solution?",
        "Think about edge cases the user might encounter.",
        "What assumptions are you making? Challenge one.",
        "Before answering, verify with the actual code.",
        "What would the ideal solution look like?",
        "Break this down into smaller steps.",
        "Consider the trade-offs of this approach.",
        "What would happen if we did the opposite?",
    ],
    "format": [
        "Use code blocks with language hints.",
        "Keep your response concise - no unnecessary explanation.",
        "Format output as a structured list.",
        "Add a brief summary at the start.",
        "Show the key insight first, then details.",
    ],
    "perspective": [
        "What would a senior developer notice here?",
        "Think like the user encountering this for the first time.",
        "Consider the long-term maintenance implications.",
        "What could go wrong with this approach?",
        "How does this fit the existing architecture?",
    ],
    "action": [
        "Before responding, check if there's relevant existing code.",
        "If unsure about a detail, ask for clarification.",
        "Prioritize the most impactful solution first.",
        "Test your solution mentally before presenting.",
    ],
    "evolution": [
        "Consider: Could this be added to the knowledge base?",
        "Note: This insight could improve future responses.",
        "Document the reasoning behind this choice.",
    ],
}


def _get_spice_path() -> Path:
    """Get the spice config path."""
    return Path(os.environ.get("SPICE_PATH", DEFAULT_SPICE_PATH)).expanduser()


def load_spices() -> Dict[str, List[str]]:
    """Load spices from file, or return defaults."""
    path = _get_spice_path()
    if path.exists():
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            pass
    return DEFAULT_SPICES.copy()


def save_spices(spices: Dict[str, List[str]]) -> None:
    """Save spices to file."""
    path = _get_spice_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spices, indent=2))


def get_random_spice(category: Optional[str] = None) -> str:
    """Get a random spice from a category, or random category if None."""
    spices = load_spices()

    if category and category in spices:
        return random.choice(spices[category])

    # Random category selection (weighted toward thinking)
    weights = {
        "thinking": 4,
        "format": 1,
        "perspective": 2,
        "action": 2,
        "evolution": 1,
    }

    # Build weighted list
    weighted = []
    for cat, sp_list in spices.items():
        if sp_list:  # Only non-empty categories
            for _ in range(weights.get(cat, 1)):
                weighted.append(cat)

    if not weighted:
        return ""

    chosen_cat = random.choice(weighted)
    return random.choice(spices[chosen_cat])


def get_spice_for_round(round_idx: int, spice_interval: int = 3) -> str:
    """Get spice for a specific round.

    Args:
        round_idx: Current round number (0-indexed)
        spice_interval: Inject spice every N rounds (default 3)

    Returns:
        Random spice string, or empty string if no spice this round
    """
    if round_idx == 0:
        return ""  # No spice on first round

    # Inject spice every spice_interval rounds
    if round_idx % spice_interval != 0:
        return ""

    return get_random_spice()


def list_categories() -> Dict[str, int]:
    """List all spice categories and their counts."""
    spices = load_spices()
    return {cat: len(snippets) for cat, snippets in spices.items()}


def add_spice(category: str, snippet: str) -> None:
    """Add a spice to a category."""
    spices = load_spices()
    if category not in spices:
        spices[category] = []
    if snippet not in spices[category]:
        spices[category].append(snippet)
        save_spices(spices)


def remove_spice(category: str, snippet: str) -> None:
    """Remove a spice from a category."""
    spices = load_spices()
    if category in spices and snippet in spices[category]:
        spices[category].remove(snippet)
        save_spices(spices)


# ============================================================================
# Targeted Spices (Phase 2) - Based on Response Analyzer feedback
# ============================================================================

# Targeted spices - specific interventions for detected issues
TARGETED_SPICES: Dict[str, List[str]] = {
    "hallucination": [
        "STOP: You made a claim without verification. Read the actual code with repo_read before continuing.",
        "CRITICAL: Verify before stating. Use grep to search for function/class names you mentioned.",
        "HALLUCINATION CHECK: Do NOT assume code exists. Read it first.",
        "VERIFICATION REQUIRED: Find the actual file and line before making any statement.",
        "Before saying 'X exists' or 'line Y has Z', prove it by reading the file.",
    ],
    "drift": [
        "DRIFT ALERT: You're going in circles. Step back and identify the actual problem.",
        "STOP LOOPING: What are you actually trying to solve? State it clearly.",
        "REDIRECT: Same approach failing repeatedly. Try grep to find patterns in existing code.",
        "CIRCULAR PATTERN: Instead of trying again, read the full context first.",
        "BREAK THE LOOP: Ask yourself - what information am I missing to solve this?",
    ],
    "avoidance": [
        "AVOIDANCE DETECTED: You're describing code without showing it. Use repo_read.",
        "GROUND YOURSELF: Read the actual implementation before explaining it.",
        "STOP ASSUMING: You said 'probably', 'might be', 'likely'. Verify with tools.",
        "TAKE OWNERSHIP: Don't guess. Read the file and show the actual code.",
        "VERIFICATION GAPS: Your response contains assumptions. Prove them with repo_read.",
    ],
    "overconfidence": [
        "HUMBLE CHECK: You used 'definitely', 'always', 'never'. Prove it with evidence.",
        "UNCERTAINTY SIGNAL: Overly certain without verification. Show your work.",
        "VERIFICATION CHECK: Asserting without proof. What code did you read?",
        "CERTAINTY FLAG: 'Impossible', 'guaranteed', 'without doubt' require evidence.",
        "SKEPTICISM INJECT: Be humble. Code often has edge cases you haven't considered.",
    ],
    "high_complexity": [
        "SIMPLIFY: This problem may have hidden complexity. Break it into smaller pieces.",
        "YAGNI CHECK: Are you solving more than needed? Focus on the immediate problem.",
        "COMPLEXITY ALERT: The solution might be simpler. What's the minimum viable fix?",
    ],
}


def get_targeted_spice(issue_type: str) -> str:
    """Get a targeted spice for a specific issue type."""
    if issue_type in TARGETED_SPICES and TARGETED_SPICES[issue_type]:
        return random.choice(TARGETED_SPICES[issue_type])
    return ""


def get_spice_for_analysis(issues: List[Any], default_interval: int = 3) -> str:
    """Get the best spice based on detected issues.

    Priority:
    1. Targeted spice for most severe issue
    2. Random spice as fallback

    Args:
        issues: List of QualityIssue from response_analyzer
        default_interval: Only inject if round_idx % interval == 0 (for random spices)

    Returns:
        Targeted or random spice string, or empty if not time for spice
    """
    if not issues:
        return get_random_spice()

    # Priority order: hallucination > overconfidence > avoidance > drift
    priority_order = ["hallucination", "overconfidence", "avoidance", "drift"]

    # Find most severe issue
    most_severe = None
    for issue_type in priority_order:
        for issue in issues:
            if issue.issue_type == issue_type and issue.severity in ("high", "medium"):
                most_severe = issue_type
                break
        if most_severe:
            break

    if most_severe:
        targeted = get_targeted_spice(most_severe)
        if targeted:
            return targeted

    # Fallback to random
    return get_random_spice()
