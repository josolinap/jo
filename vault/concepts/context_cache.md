---
title: Context Cache
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [cache, performance, context, fact]
---

# Context Cache

Multi-tier caching system for vault scans, codebase graphs, and tool results. Reduces repeated work from 60ms to <1ms on cache hit.

## Tiers

- **Memory**: Fastest, limited size (default 200 entries), in-process
- **Disk**: Persistent across tasks, stored in `.jo_data/cache/`

## TTL Strategy (from FACT)

- **Static** (300s): vault structure, tool schemas, system config
- **Semi-dynamic** (60s): codebase graph, vault note list
- **Dynamic** (30s): tool results, search results
- **Short** (10s): health checks, status queries

## Module

`ouroboros/context_cache.py`

## Key API

```python
cache = get_cache(repo_dir)
hit, value = cache.get("key")           # Check cache
cache.set("key", value, ttl=60)         # Store with TTL
result = cache.cached("key", fn, ttl)   # Cache-first wrapper
cache.invalidate("prefix:")             # Invalidate by prefix
```

## Design Decisions

- Eviction: oldest + least-hit entries removed when over capacity
- Disk tier only for semi-dynamic+ content (not worth persisting short-lived results)
- Global singleton via `get_cache()` for shared caching across tool calls
- No thread safety by design — single-task use

Related: [[code_intelligence]], [[principle_5__minimalism]], [[architecture]]
