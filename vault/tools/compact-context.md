---
title: compact_context
created: 2026-03-25
category: tools
tags:  []

---

# compact_context

**Type:** Tool
**Category:** See system_map

## Description

Selectively compress old tool results in conversation history to save context tokens. Call this when you notice context is getting large (e.g., after self-check reminder). Keeps recent N tool rounds intact; older rounds get summarized to 1-line summaries. You decide what to keep (via keep_last_n) — no information is lost, just compressed.

## Parameters

- `keep_last_n` (integer): Number of recent tool rounds to keep fully intact (default 6, range 2-20). Lower = more compression.

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[system_map]]
