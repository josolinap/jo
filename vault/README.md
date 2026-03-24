---
title: Jo's Vault
created: 2026-03-25
category: .
tags:  []

---

# Jo's Vault

This is Jo's knowledge vault - an Obsidian-style note system stored in git for persistence across restarts.

## Structure

- `concepts/` - Reference notes, ideas, concepts
- `projects/` - Project-specific notes
- `tools/` - Documentation about tools and techniques
- `journal/` - Daily notes and logs

## How It Works

1. Vault is stored here in git for persistence
2. On startup, Jo syncs vault from git to `~/.jo_data/vault/` for local access
3. On writes, changes are committed to git automatically
4. On next startup, vault is restored from git

## Wikilinks

Notes can link to each other using `[[wikilink]]` syntax:
- `[[Note Name]]` - links to a note
- Backlinks are automatically tracked
