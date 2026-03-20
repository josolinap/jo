def get_all_notes(self) -> List[Dict[str, Any]]:
    """Get all notes with their metadata."""
    self.build_index()
    notes = []
    for path_str, parsed in list(self._index.items()):
        notes.append(
            {
                "title": parsed.title or parsed.path,
                "path": parsed.path,
                "aliases": parsed.aliases,
                "tags": parsed.tags,
                "type": parsed.frontmatter.get("type", "reference"),
                "status": parsed.frontmatter.get("status", "active"),
                "created": parsed.frontmatter.get("created", ""),
                "modified": parsed.frontmatter.get("modified", ""),
                "outlinks": [w.note_name for w in parsed.wikilinks],
                "backlink_count": len(self.get_backlinks(parsed.title)),
            }
        )
    return notes