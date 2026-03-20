"""
Ouroboros — Vault Module.

Obsidian-style knowledge vault for Jo: notes, wikilinks, backlinks, and graph.
"""

from __future__ import annotations

from .vault_parser import WikilinkParser, Wikilink, ParsedNote, Heading, BlockId
from .vault_manager import VaultManager

__all__ = [
    "WikilinkParser",
    "Wikilink",
    "ParsedNote",
    "Heading",
    "BlockId",
    "VaultManager",
]
