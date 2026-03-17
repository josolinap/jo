"""Spice system for Jo - random prompt injections to prevent stale conversations.

Inspired by Sapphire's spice system - injects random snippets each round
to keep conversations fresh, break loops, and add variety.

Spice categories for Jo:
- thinking: Different approaches to problem-solving
- format: Vary output formatting
- perspective: Look at problems differently
- action: Encourage specific behaviors
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
