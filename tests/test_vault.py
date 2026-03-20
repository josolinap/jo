"""Tests for vault module."""

from __future__ import annotations

import json
import pathlib
import tempfile

import pytest

from ouroboros.vault_parser import WikilinkParser, Wikilink
from ouroboros.vault_manager import VaultManager


@pytest.fixture
def temp_vault(tmp_path) -> VaultManager:
    """Create a temporary vault for testing."""
    vault_dir = tmp_path / "test_vault"
    vault_dir.mkdir()
    return VaultManager(vault_dir)


class TestWikilinkParser:
    """Tests for WikilinkParser."""

    def test_parse_basic_wikilink(self):
        parser = WikilinkParser()
        content = "See [[Note One]] for details."
        note = parser.parse_content(content)
        assert len(note.wikilinks) == 1
        assert note.wikilinks[0].note_name == "Note One"
        assert note.wikilinks[0].display is None

    def test_parse_wikilink_with_alias(self):
        parser = WikilinkParser()
        content = "Check [[Project Alpha|my project]] for more."
        note = parser.parse_content(content)
        assert len(note.wikilinks) == 1
        assert note.wikilinks[0].note_name == "Project Alpha"
        assert note.wikilinks[0].display == "my project"

    def test_parse_multiple_wikilinks(self):
        parser = WikilinkParser()
        content = "See [[Note A]] and [[Note B]] for reference."
        note = parser.parse_content(content)
        assert len(note.wikilinks) == 2
        names = {w.note_name for w in note.wikilinks}
        assert names == {"Note A", "Note B"}

    def test_parse_headings(self):
        parser = WikilinkParser()
        content = "# Title\n\n## Section One\n\n### Subsection\n\n## Section Two"
        note = parser.parse_content(content)
        assert len(note.headings) == 4
        assert note.headings[0].text == "Title"
        assert note.headings[0].level == 1
        assert note.headings[2].text == "Subsection"
        assert note.headings[2].level == 3

    def test_parse_frontmatter(self):
        parser = WikilinkParser()
        content = """---
title: Test Note
tags: [concept, idea]
type: reference
---

# Test Note
"""
        note = parser.parse_content(content)
        assert note.title == "Test Note"
        assert "concept" in note.tags
        assert "idea" in note.tags
        assert note.frontmatter.get("type") == "reference"

    def test_parse_block_ids(self):
        parser = WikilinkParser()
        content = "Some paragraph text. ^important-point"
        note = parser.parse_content(content)
        assert len(note.block_ids) == 1
        assert note.block_ids[0].id == "important-point"

    def test_render_wikilink(self):
        parser = WikilinkParser()
        assert parser.render_wikilink("Note") == "[[Note]]"
        assert parser.render_wikilink("Note", "Display") == "[[Note|Display]]"

    def test_resolve_link(self):
        parser = WikilinkParser()
        note_names = ["Note One.md", "concepts/Note Two.md", "projects/Project.md"]
        wl = Wikilink(raw="[[Note One]]", target="Note One", display=None, heading=None, block_id=None)
        assert parser.resolve_link(wl, note_names) == "Note One.md"


class TestVaultManager:
    """Tests for VaultManager."""

    def test_create_note(self, temp_vault):
        path = temp_vault.create_note("Test Note", folder="concepts", content="Hello world")
        assert pathlib.Path(path).exists()
        assert "test_note.md" in path.lower()
        content = pathlib.Path(path).read_text()
        assert "Test Note" in content
        assert "Hello world" in content

    def test_create_note_with_tags(self, temp_vault):
        path = temp_vault.create_note("Tagged Note", tags=["concept", "ai"], status="active")
        content = pathlib.Path(path).read_text()
        assert "concept" in content
        assert "ai" in content

    def test_get_note(self, temp_vault):
        temp_vault.create_note("Existing Note", folder="concepts", content="Test content")
        note = temp_vault.get_note("existing_note")
        assert note is not None
        assert note.title == "Existing Note"

    def test_write_note_append(self, temp_vault):
        path = temp_vault.create_note("Append Test", content="Initial")
        result = temp_vault.write_note("append_test", "\n\nAppended content", mode="append")
        assert "OK" in result
        content = pathlib.Path(path).read_text()
        assert "Initial" in content
        assert "Appended content" in content

    def test_link_notes(self, temp_vault):
        temp_vault.create_note("Source", content="Source note")
        temp_vault.create_note("Target", content="Target note")
        result = temp_vault.link_notes("Source", "Target", "Related to")
        assert "OK" in result
        source_content = temp_vault.resolve_path("Source").read_text()
        assert "[[Target]]" in source_content

    def test_get_outlinks(self, temp_vault):
        temp_vault.create_note("A", content="Links to [[B]] and [[C]]")
        temp_vault.create_note("B")
        temp_vault.create_note("C")
        outlinks = temp_vault.get_outlinks("A")
        assert "B" in outlinks
        assert "C" in outlinks

    def test_get_backlinks(self, temp_vault):
        temp_vault.create_note("A", content="I link to [[B]]")
        temp_vault.create_note("B", content="I am linked")
        temp_vault.build_index()
        backlinks = temp_vault.get_backlinks("B")
        assert len(backlinks) == 1
        assert backlinks[0]["note"] == "A"

    def test_search_by_content(self, temp_vault):
        temp_vault.create_note("Note One", content="Python programming language")
        temp_vault.create_note("Note Two", content="JavaScript programming")
        results = temp_vault.search("Python")
        assert len(results) == 1
        assert "Note One" in results[0]["note"]

    def test_search_by_tags(self, temp_vault):
        temp_vault.create_note("AI Note", tags=["ai", "ml"])
        temp_vault.create_note("Other Note", tags=["other"])
        results = temp_vault.search("ai", field="tags")
        assert len(results) == 1
        assert "AI Note" in results[0]["note"]

    def test_get_graph_data(self, temp_vault):
        temp_vault.create_note("A", content="Links to [[B]]")
        temp_vault.create_note("B", content="Links to [[A]]")
        graph = temp_vault.get_graph_data()
        assert len(graph["nodes"]) == 2
        assert len(graph["links"]) >= 1

    def test_export_mermaid(self, temp_vault):
        temp_vault.create_note("A", content="Links to [[B]]")
        temp_vault.create_note("B")
        mermaid = temp_vault.export_mermaid()
        assert "```mermaid" in mermaid
        assert "graph TD" in mermaid

    def test_delete_note(self, temp_vault):
        temp_vault.create_note("To Delete")
        result = temp_vault.delete_note("to_delete")
        assert "OK" in result
        assert temp_vault.get_note("to_delete") is None

    def test_render_backlinks_section(self, temp_vault):
        temp_vault.create_note("A", content="I link to [[B]]")
        temp_vault.create_note("B", content="I am B")
        temp_vault.build_index()
        section = temp_vault.render_backlinks_section("B")
        assert "Backlinks" in section
        assert "[[A]]" in section


class TestVaultTools:
    """Tests for vault tools integration."""

    def test_vault_ensure_structure(self, temp_vault):
        temp_vault.ensure_vault_structure()
        assert (temp_vault.vault_root / "concepts").exists()
        assert (temp_vault.vault_root / "projects").exists()
        assert (temp_vault.vault_root / "tools").exists()
        assert (temp_vault.vault_root / "journal").exists()

    def test_vault_note_creation_flow(self, temp_vault):
        path = temp_vault.create_note(
            title="Evolution Cycle 2026",
            folder="journal",
            content="## Summary\n\nAnalyzed Obsidian integration.",
            tags=["evolution", "vault"],
            type="journal",
            status="active",
        )
        note = temp_vault.get_note("evolution_cycle_2026")
        assert note is not None
        assert "Evolution Cycle 2026" in note.title
        assert "evolution" in note.tags
        assert "vault" in note.tags
