# Vault Frontmatter Schema — Coherence Specification

> Inspired by schema.org (Google's open knowledge vocabulary) + MCF (Meta Content Framework).
> Goal: turn Jo's vault from untyped markdown into a queryable knowledge graph.

## Required Fields (all notes)

```yaml
---
title: "Human Readable Title"        # Required: display name
type: concept                         # Required: see taxonomy below
status: active                        # Required: active | draft | archived
tags: [tag1, tag2]                    # Required: free-form, lowercase
---
```

## Recommended Fields (for knowledge graph)

```yaml
---
# Entity resolution (fixes the "Python" vs "python3" problem)
entity_id: lang.python                # Canonical ID (namespace.name format)
aliases: [CPython, python3]           # Alternative names that should resolve to this note

# Provenance (fixes the "where did Jo learn X?" problem)
provenance:
  source: web                         # web | user | jo | extracted | inferred
  ref: "https://python.org"           # URL, commit hash, session ID, etc.
  confidence: 0.95                    # 0.0-1.0
  extracted_at: 2026-07-15T10:30:00Z

# Temporal validity (fixes the "is this still true?" problem)
valid_from: 2026-07-01T00:00:00Z     # When this fact became true
valid_until: null                     # null = still true, or ISO timestamp when it stopped

# Taxonomy hierarchy (fixes the "every concept is an island" problem)
parent: concept.programming_language  # entity_id of parent concept
---
```

## Type Taxonomy (controlled vocabulary)

| Type | Description | Example |
|------|-------------|---------|
| `concept` | Abstract idea or principle | `Principle 0: Agency` |
| `pattern` | Reusable solution pattern | `LLM-First Architecture` |
| `module` | Code module documentation | `memory.py` |
| `tool` | Tool documentation | `vault_search` |
| `lesson` | Learning from experience | `Hallucination Incident 2026-04-03` |
| `memory` | Extracted memory fact | `Jo prefers bold restructuring` |
| `agent` | Agent identity or role | `Jo` |
| `environment` | System or infrastructure | `GitHub Actions Runner` |
| `project` | Project documentation | `Intelligent Vault System` |
| `reference` | External reference | `schema.org spec` |

## Migration Path

1. **Phase 1 (current)**: `resolve_path()` now consults `aliases:` field
2. **Phase 2**: `vault_check_conventions` flags notes missing `entity_id`
3. **Phase 3**: LLM-driven extraction populates `provenance` + `valid_from`
4. **Phase 4**: SPARQL/RDF export via `entity_id` as URI

## Why This Aligns with Google's Open Knowledge Efforts

- **schema.org**: `entity_id` mirrors `@id`, `aliases` mirrors `sameAs`, `type` mirrors `@type`
- **JSON-LD**: Frontmatter can be trivially exported as JSON-LD `@context` documents
- **Data Commons**: `entity_id` namespace format (`lang.python`) matches DCID convention
- **Wikidata**: `sameAs` field can link to Wikidata Q-IDs for external entity resolution

This makes Jo's vault a **typed, queryable knowledge graph** that can interoperate with Google's open knowledge ecosystem while staying as plain markdown.
