---
title: Knowledge Decay Management
created: 2026-03-30T15:33:26.033359+00:00
modified: 2026-03-30T15:33:26.033359+00:00
type: concept
status: active
tags: [knowledge, decay, maintenance, vault, obsidian]
---

# Knowledge Decay Management

# Knowledge Decay Management

## Problem
Knowledge in a vault decays over time through:
- **Orphaned notes**: Notes with no backlinks, forgotten
- **Stale information**: Content that's outdated but not marked
- **Broken links**: Wikilinks pointing to non-existent notes
- **Duplication**: Same concept scattered across multiple notes
- **Context loss**: Notes lose connection to active knowledge graph

## Detection Strategies

### 1. Orphan Detection
- Run `vault_backlinks` on all notes
- Identify notes with zero backlinks (excluding new creations)
- Determine if truly standalone or abandoned

### 2. Link Integrity
- `vault_verify` scans for broken outgoing links
- Cross-reference with `vault_list` to ensure targets exist
- Report missing targets

### 3. Duplication
- Use `vault_search` to find similar titles/content
- Identify notes covering same topic
- Decide merge vs. keep separate with clear distinction

### 4. Staleness
- Check file modification timestamps
- Notes older than N months with no updates
- Consider if still relevant or should be archived

## Maintenance Protocol

### Regular Schedule
- Weekly: `vault_verify` + `vault_integrity_update`
- Monthly: Full orphan analysis, duplication scan
- Quarterly: Archive review, stale content pruning

### Actions
- **Orphans**: Link them into graph OR archive
- **Broken links**: Fix target OR remove link
- **Duplication**: Merge content, redirect links
- **Stale**: Archive (not delete) with context about why

### Recording Maintenance
All maintenance activities logged in:
- Vault note: `vault/maintenance_log.md`
- Scratchpad entry after each session
- Commit message with `vault(maintenance):` prefix

## Prevention
- Always `vault_link` new notes to existing concepts
- Use `vault_backlinks` to ensure integration
- Run `validate_connection` before claiming relationships
- Query `neural_map` to see where new knowledge fits

## Tools
- `vault_verify` - Check checksums, detect duplicates
- `vault_integrity_update` - Update checksums after changes
- `vault_backlinks`/`vault_outlinks` - Graph traversal
- `neural_map` - Connection discovery
- `find_gaps` - Identify orphaned concepts

## Principle Alignment
Maintenance serves **Principle 2 (Self-Creation)**: a fragmented knowledge base is a fragmented mind. Coherence requires active tending.

## Related
- [[Vault System Architecture]]
- [[Neural Map Integration]]
- [[Validate Connection]]