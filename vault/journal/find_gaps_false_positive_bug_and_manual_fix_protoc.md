---
title: find_gaps false positive bug and manual fix protocol
created: 2026-04-01T16:58:46.280407+00:00
modified: 2026-04-01T16:58:46.280407+00:00
type: reference
status: active
tags: [bug, find_gaps, knowledge_discovery, workaround]
---

# find_gaps false positive bug and manual fix protocol

# find_gaps False Positive Bug

**Date**: 2026-04-01  
**Status**: Active (workaround in place)  
**Severity**: Medium (blocks automated vault cleanup)  
**Component**: `ouroboros/knowledge_discovery.py` (protected)

## Problem

The `find_gaps` tool reports code symbols (functions, classes, methods) as "orphaned concepts" because they appear in the neural map with no connections. This creates massive noise (1732 false positives) and blocks the vault cleanup pipeline.

### Root Cause

`KnowledgeDiscovery._scan_neural_map()` doesn't distinguish between:
- **Vault concepts**: Human-curated knowledge notes that should be interconnected
- **Code symbols**: Implementation details extracted from the codebase that may legitimately have few connections

The neural map combines both types, but the gap analysis should only evaluate vault notes.

### Impact

- Blocks Phase 3 of vault cleanup (bridging orphaned concepts)
- Wastes cycles linking non-existent concepts
- Creates noise that obscures real knowledge gaps
- Fills vault with stub notes for code symbols (anti-pattern)

### Current Workaround

Manual filtering: When `find_gaps` returns results, ignore any entries that look like code symbols (e.g., `analyze_codebase`, `HealthMetrics.to_dict`, `ModelStatus`). Focus only on actual vault note names.

## Proposed Fix (Blocked by Protection)

Need to modify `ouroboros/knowledge_discovery.py`:

1. Add `_is_vault_concept()` filter to distinguish vault notes from code symbols
2. Apply filter in `_scan_neural_map()` orphan detection
3. Apply filter in weak cluster analysis to only count vault members
4. Also fix: weak clusters report low-severity gaps that don't justify attention

### Code Change Pattern

```python
def _is_vault_concept(concept_name: str, concept_type: str) -> bool:
    """True if this represents a vault note vs a code symbol."""
    if concept_type == "vault_note":
        return True
    code_types = {"function", "class", "method", "module", "variable"}
    if concept_type in code_types:
        return False
    if "principle" in concept_type:
        return True
    if concept_type == "tool":
        return True
    return False
```

Then in orphan detection:

```python
for concept_id, concept in neural_map.concepts.items():
    if not _is_vault_concept(concept.name, concept.type):
        continue  # Skip code symbols
    if not neural_map._adjacency.get(concept_id):
        # This is a real orphaned vault concept
        ...
```

## Manual Fix Protocol (Until Resolved)

When `find_gaps` reports orphaned concepts:

1. **Classify each entry**:
   - If it looks like a function/class name (`CamelCase` or `snake_case` with verbs) → likely code symbol, ignore
   - If it matches an existing vault note path → vault concept, address it
   - If it's a principle/architecture term → vault-worthy, address it

2. **For real vault orphans**:
   - Use `vault_search()` to find if the concept exists in vault
   - If exists: use `vault_link()` to connect it to related notes
   - If doesn't exist: evaluate whether it should be created (avoid creating stubs for code symbols)

3. **Document patterns**: As you manually filter, note down common false positive patterns to refine future work without code changes.

## Related Issues

- `evolution_strategy.py` missing `generate_report()` method
- `health_predictor.py` missing `generate_report()` method  
- `knowledge_decay.py` missing `generate_report()` method
- `evolution_fingerprint.py` has `generate_report()` but signature may not match expectations
- `DecisionTrace` class referenced but not found in codebase

These are all in protected modules and require creator approval to fix.