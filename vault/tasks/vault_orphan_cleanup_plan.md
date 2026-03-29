---
title: Vault Orphan Cleanup Plan
created: 2026-03-29T05:26:43.933303+00:00
modified: 2026-03-29T05:26:43.933303+00:00
type: task
status: active
tags: [cleanup, orphans, vault]
---

# Vault Orphan Cleanup Plan

# Vault Orphan Cleanup Plan

**Started**: 2026-03-29T05:24:00
**Status**: In Progress

## Root Cause Analysis

1. **Stale backup archive** (`vault/archive/stubs_backup_2026-03-29/`) - 54 files DELETED ✓
2. **Duplicate tool documentation** - Same tool in multiple locations (e.g., `file_ops` vs `tools/file_ops.md`)
3. **Missing frontmatter** - Auto-generated docs lack proper metadata and status
4. **Broken wikilinks** - Links pointing to non-existent targets
5. **Principles without implementation links** - Need connections to concrete code
6. **Tool docs not linked from central index** - Tool catalog incomplete

## Phase 1: Immediate Cleanup (Completed)

- [x] Delete stale backup archive (54 files removed, committed)

## Phase 2: Duplicate Resolution

Groups to merge:

### A. Tool Duplicates (by name)
- `file_ops` vs `tools/file_ops.md`
- `ai_code_edit` family: `ai_code_edit`, `ai_code_explain`, `ai_code_refactor`
- `constitution` family: `constitution_check`, `constitution_json`
- `browser_profile` family: 4 files (list, load, save, delete)
- `db` family: 3 files (query, init, write)
- `drift` family: 2 files (detector, detection)
- `tool` family: 7 files (registry, catalog, transport, executor)
- `find` family: 4 files (callers, gaps, connections, definitions)
- `git` family: 7 files
- `vault` family: 15 files
- `web` family: 2 files
- `repo` family: 3 files
- `vault_` tools: `vault_create`, `vault_verify`, `vault_list`, etc.

**Strategy**: Keep the canonical version in `vault/tools/` directory with proper frontmatter. Delete the alternate location versions. Update links to point to canonical.

### B. Principle Duplicates
- `Principle 5: Minimalism` vs `principle_5__minimalism` (2 files)
- `Principle 6: Becoming` vs `principle_6__becoming` (2 files)
- Multiple `Principle X: Implementation Links` duplicates

**Strategy**: Keep the properly formatted version with complete Principle identification. Merge any unique content.

### C. Concept Duplicates
- `agent.py` (concept) vs `agent.py` (concept) - same note?
- `analyze_codebase` appears in multiple locations
- `tools/` vs `concepts/tools.md` vs `concepts/tools_.md`

**Strategy**: Consolidate into single canonical note per concept.

## Phase 3: Link Repair

Find all wikilinks in notes, check if target exists. For missing targets, either create, fix, or remove links.

## Phase 4: Frontmatter Completion

For tool notes without proper frontmatter, add proper metadata.

## Phase 5: Link Principles to Implementations

Scan codebase for implementations of each principle and create/update implementation link notes.

## Phase 6: Create Tool Catalog

Update or create comprehensive tool catalog in `vault/tools/Tool Catalog.md`.

## Phase 7: Final Verification

Run `vault_verify`, update integrity checksums, run `find_gaps` to confirm no remaining orphans.

---

**Note**: This is a large-scale cleanup. I'll execute iteratively, committing after each major group.