---
title: verify_claim
created: 2026-03-25
category: tools
tags:  []

---

# verify_claim

**Type:** Tool
**Category:** See system_map

## Description

Track verification of a claim about the codebase. Use after verifying something: read a file, ran a test, checked git status. This creates an audit trail for anti-hallucination enforcement.

## Parameters

- `claim` (string): What you verified (e.g., 'function exists at line 42')
- `method` (string): How you verified: 'repo_read', 'grep', 'test', 'git'
- `outcome` (string): Result: 'verified', 'not_found', 'error'

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[repo_read]]
