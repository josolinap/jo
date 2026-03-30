---
title: Knowledge Decay
created: 2026-03-30T15:35:16.643033+00:00
modified: 2026-03-30T15:35:16.643033+00:00
type: concept
status: active
tags: [knowledge, decay, vault]
---

# Knowledge Decay

# Knowledge Decay

The gradual degradation of knowledge relevance and integrity over time.

## Types of Decay

### Orphaned Notes
Notes with no backlinks, isolated from the knowledge graph.

### Stale Information
Content that becomes outdated but remains unmarked.

### Broken Links
Wikilinks pointing to deleted or renamed notes.

### Duplication
Same concept spread across multiple notes, causing inconsistency.

### Context Loss
Notes lose connection to active knowledge graph through lack of maintenance.

## Detection

- `vault_backlinks`: Identify notes with zero incoming links
- `vault_verify`: Scan for broken outgoing links and checksum mismatches
- Content similarity search via `vault_search`: Find potential duplicates
- File modification timestamps: Identify long-unmodified notes

## Mitigation

- Regular `vault_verify` + `vault_integrity_update` (weekly)
- Monthly orphan analysis and link repair
- Quarterly content archival review
- Always link new notes into existing graph using `vault_link`

## Principle
Active maintenance is required for a coherent knowledge base, which supports coherent self-understanding (Principle 2).

## Related
- [[Knowledge Decay Management]]
- [[Vault System Architecture]]
- [[Neural Map Integration]]