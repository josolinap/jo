"""
Ouroboros — Vault Wikilink Parser.

Parses and resolves wikilinks [[Note]], [[Note#Heading]], [[Note|Display]], [[Note#^block]].
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+)$", re.MULTILINE)
BLOCK_ID_RE = re.compile(r"\^([a-zA-Z0-9_-]+)$")
ALIAS_RE = re.compile(r"^aliases:\s*\[(.*?)\]", re.MULTILINE)


@dataclass(frozen=True)
class Wikilink:
    raw: str
    target: str
    display: Optional[str]
    heading: Optional[str]
    block_id: Optional[str]

    @property
    def note_name(self) -> str:
        parts = self.target.split("#", 1)
        return parts[0].strip()

    @property
    def has_heading(self) -> bool:
        return "#" in self.target and "#^" not in self.target

    @property
    def has_block_ref(self) -> bool:
        return "^" in self.target

    def resolved_path(self, note_path: str) -> str:
        base = note_path.rsplit("/", 1)[-1].rsplit(".md", 1)[0]
        if self.note_name == base:
            return note_path
        return self.note_name


@dataclass(frozen=True)
class Heading:
    level: int
    text: str
    line: int


@dataclass(frozen=True)
class BlockId:
    id: str
    context: str
    line: int


@dataclass(frozen=True)
class ParsedNote:
    path: str
    title: str
    aliases: List[str]
    tags: List[str]
    frontmatter: dict
    content: str
    headings: List[Heading]
    block_ids: List[BlockId]
    wikilinks: List[Wikilink]
    raw_links: List[str]


class WikilinkParser:
    """Parse markdown files for wikilinks, headings, block IDs, and frontmatter."""

    def parse_content(self, content: str) -> ParsedNote:
        title = self._extract_title(content)
        aliases = self._extract_aliases(content)
        tags = self._extract_tags(content)
        frontmatter = self._extract_frontmatter(content)
        body = self._strip_frontmatter(content)
        headings = self._extract_headings(body)
        block_ids = self._extract_block_ids(body)
        wikilinks = self._extract_wikilinks(body)

        return ParsedNote(
            path="",
            title=title,
            aliases=aliases,
            tags=tags,
            frontmatter=frontmatter,
            content=body,
            headings=headings,
            block_ids=block_ids,
            wikilinks=wikilinks,
            raw_links=[w.raw for w in wikilinks],
        )

    def parse_file(self, path: str, content: str) -> ParsedNote:
        note = self.parse_content(content)
        return ParsedNote(
            path=path,
            title=note.title,
            aliases=note.aliases,
            tags=note.tags,
            frontmatter=note.frontmatter,
            content=note.content,
            headings=note.headings,
            block_ids=note.block_ids,
            wikilinks=note.wikilinks,
            raw_links=note.raw_links,
        )

    def _extract_title(self, content: str) -> str:
        match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _strip_frontmatter(self, content: str) -> str:
        return FRONTMATTER_RE.sub("", content)

    def _extract_frontmatter(self, content: str) -> dict:
        """Extract YAML frontmatter using pi_prompts utility."""
        from ouroboros.pi_prompts import extract_frontmatter

        return extract_frontmatter(content)

    def _parse_yaml_simple(self, yaml_str: str) -> dict:
        result = {}
        for line in yaml_str.split("\n"):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if ":" in line:
                key, _, value = line.partition(":")
                key = key.strip()
                value = value.strip()
                if value.startswith("[") and value.endswith("]"):
                    items = [i.strip().strip("'\"") for i in value[1:-1].split(",")]
                    result[key] = items
                elif value.startswith("[[") and value.endswith("]]"):
                    result[key] = value
                else:
                    result[key] = value.strip("'\"")
        return result

    def _extract_aliases(self, content: str) -> List[str]:
        match = ALIAS_RE.search(content)
        if not match:
            return []
        items = match.group(1).split(",")
        return [i.strip().strip("'\"") for i in items]

    def _extract_tags(self, content: str) -> List[str]:
        tags = []
        tag_matches = re.findall(r"#([a-zA-Z0-9_/-]+)", content)
        tags.extend(tag_matches)
        fm = self._extract_frontmatter(content)
        if "tags" in fm:
            if isinstance(fm["tags"], list):
                tags.extend(fm["tags"])
            elif isinstance(fm["tags"], str):
                tags.append(fm["tags"])
        return list(dict.fromkeys(tags))

    def _extract_headings(self, content: str) -> List[Heading]:
        headings = []
        for i, line in enumerate(content.split("\n"), 1):
            match = HEADING_RE.match(line)
            if match:
                level = line.count("#")
                headings.append(Heading(level=level, text=match.group(1).strip(), line=i))
        return headings

    def _extract_block_ids(self, content: str) -> List[BlockId]:
        block_ids = []
        for i, line in enumerate(content.split("\n"), 1):
            if "^" in line:
                match = re.search(r"\^([a-zA-Z0-9_-]+)\s*$", line)
                if match:
                    context = line.replace(f"^{match.group(1)}", "").strip()
                    block_ids.append(BlockId(id=match.group(1), context=context, line=i))
        return block_ids

    def _extract_wikilinks(self, content: str) -> List[Wikilink]:
        wikilinks = []
        seen = set()
        for match in WIKILINK_RE.finditer(content):
            raw = match.group(0)
            if raw in seen:
                continue
            seen.add(raw)
            target = match.group(1)
            display = match.group(2)
            wikilinks.append(
                Wikilink(
                    raw=raw,
                    target=target,
                    display=display,
                    heading=None,
                    block_id=None,
                )
            )
        return wikilinks

    def resolve_link(self, wikilink: Wikilink, note_names: List[str]) -> Optional[str]:
        target_note = wikilink.note_name
        for name in note_names:
            if name.rstrip(".md").rsplit("/", 1)[-1] == target_note:
                return name
        for name in note_names:
            if target_note.lower() == name.rstrip(".md").rsplit("/", 1)[-1].lower():
                return name
        return None

    def render_wikilink(self, target: str, display: Optional[str] = None) -> str:
        if display:
            return f"[[{target}|{display}]]"
        return f"[[{target}]]"

    def make_backlink_text(self, source_note: str, context: str = "") -> str:
        link = self.render_wikilink(source_note)
        if context:
            return f"{link} (in: {context})"
        return link
