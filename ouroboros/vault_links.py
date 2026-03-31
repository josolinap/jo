"""Vault note linking with bidirectional tracking.

Inspired by Zotero Better Notes: connect knowledge fragments
with [[wikilinks]]. Track inbound/outbound links automatically.

Following Principle 5 (Minimalism): under 250 lines.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

log = logging.getLogger(__name__)


class VaultLinkTracker:
    """Track bidirectional links between vault notes.

    Parses [[wikilinks]] in markdown files and maintains
    a link graph for navigation and discovery.

    Usage:
        tracker = VaultLinkTracker(vault_dir="vault")
        tracker.scan()
        inbound = tracker.get_inbound_links("concepts/agency")
        outbound = tracker.get_outbound_links("concepts/agency")
    """

    def __init__(self, vault_dir: str = "vault") -> None:
        self.vault_dir = Path(vault_dir)
        self._outbound: Dict[str, Set[str]] = {}  # note -> links
        self._inbound: Dict[str, Set[str]] = {}  # note -> backlinks
        self._note_titles: Dict[str, str] = {}  # path -> title

    def scan(self) -> int:
        """Scan vault for all notes and their links."""
        self._outbound.clear()
        self._inbound.clear()
        self._note_titles.clear()

        if not self.vault_dir.exists():
            return 0

        count = 0
        for md_file in self.vault_dir.rglob("*.md"):
            if md_file.name.startswith("."):
                continue

            rel_path = str(md_file.relative_to(self.vault_dir)).replace("\\", "/").replace(".md", "")
            self._note_titles[rel_path] = md_file.stem

            try:
                content = md_file.read_text(encoding="utf-8")
                links = self._extract_links(content)

                self._outbound[rel_path] = set()

                for link in links:
                    normalized = self._normalize_link(link)
                    self._outbound[rel_path].add(normalized)

                    if normalized not in self._inbound:
                        self._inbound[normalized] = set()
                    self._inbound[normalized].add(rel_path)

                count += 1
            except Exception as e:
                log.debug(f"Failed to scan {md_file}: {e}")

        return count

    def _extract_links(self, content: str) -> List[str]:
        """Extract [[wikilinks]] from content."""
        # Match [[link]] or [[link|display text]]
        pattern = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"
        return re.findall(pattern, content)

    def _normalize_link(self, link: str) -> str:
        """Normalize link path for consistent matching."""
        # Convert "My Note" to "my_note"
        normalized = link.strip().lower().replace(" ", "_")
        return normalized

    def get_outbound_links(self, note_path: str) -> List[str]:
        """Get all links from a note."""
        return sorted(self._outbound.get(note_path, set()))

    def get_inbound_links(self, note_path: str) -> List[str]:
        """Get all backlinks to a note."""
        return sorted(self._inbound.get(note_path, set()))

    def get_related_notes(self, note_path: str, max_depth: int = 2) -> List[str]:
        """Get related notes through link traversal."""
        visited = set()
        frontier = {note_path}
        related = set()

        for _ in range(max_depth):
            next_frontier = set()
            for note in frontier:
                if note in visited:
                    continue
                visited.add(note)

                # Add outbound links
                for link in self._outbound.get(note, set()):
                    if link not in visited:
                        next_frontier.add(link)
                        related.add(link)

                # Add inbound links
                for link in self._inbound.get(note, set()):
                    if link not in visited:
                        next_frontier.add(link)
                        related.add(link)

            frontier = next_frontier

        related.discard(note_path)
        return sorted(related)

    def get_orphan_notes(self) -> List[str]:
        """Find notes with no incoming or outgoing links."""
        all_notes = set(self._outbound.keys())
        linked_notes = set()

        for links in self._outbound.values():
            linked_notes.update(links)
        for links in self._inbound.values():
            linked_notes.update(links)

        orphans = all_notes - linked_notes
        return sorted(orphans)

    def get_hub_notes(self, min_connections: int = 3) -> List[Dict[str, Any]]:
        """Find notes with many connections (knowledge hubs)."""
        hubs = []
        for note, links in self._outbound.items():
            total = len(links) + len(self._inbound.get(note, set()))
            if total >= min_connections:
                hubs.append(
                    {
                        "note": note,
                        "outbound": len(links),
                        "inbound": len(self._inbound.get(note, set())),
                        "total": total,
                    }
                )

        return sorted(hubs, key=lambda x: -x["total"])

    def insert_link(self, file_path: str, target_note: str, display_text: str = "") -> bool:
        """Insert a wikilink into a note file."""
        path = self.vault_dir / f"{file_path}.md"
        if not path.exists():
            return False

        try:
            content = path.read_text(encoding="utf-8")
            link = f"[[{target_note}]]" if not display_text else f"[[{target_note}|{display_text}]]"

            # Append link at end of file
            new_content = content.rstrip() + f"\n\n{link}\n"
            path.write_text(new_content, encoding="utf-8")

            # Update tracking
            if file_path not in self._outbound:
                self._outbound[file_path] = set()
            self._outbound[file_path].add(target_note)

            if target_note not in self._inbound:
                self._inbound[target_note] = set()
            self._inbound[target_note].add(file_path)

            return True
        except Exception as e:
            log.warning(f"Failed to insert link: {e}")
            return False

    def get_stats(self) -> Dict[str, Any]:
        """Get link statistics."""
        total_notes = len(self._outbound)
        total_links = sum(len(links) for links in self._outbound.values())
        orphans = len(self.get_orphan_notes())

        return {
            "notes": total_notes,
            "links": total_links,
            "avg_links_per_note": total_links / max(1, total_notes),
            "orphans": orphans,
            "hub_count": len(self.get_hub_notes()),
        }


# Global tracker instance
_tracker: Optional[VaultLinkTracker] = None


def get_tracker(vault_dir: str = "vault") -> VaultLinkTracker:
    """Get or create the global vault link tracker."""
    global _tracker
    if _tracker is None:
        _tracker = VaultLinkTracker(vault_dir)
        _tracker.scan()
    return _tracker
