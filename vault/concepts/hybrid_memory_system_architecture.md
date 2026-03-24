---
title: Hybrid Memory System Architecture
created: 2026-03-24T09:30:06.563278+00:00
modified: 2026-03-24T09:30:06.563278+00:00
type: concept
status: active
tags: [architecture, memory, hybrid]
---

# Hybrid Memory System Architecture

# Hybrid Memory System: Jo + 7/24 Office Insights

## Philosophy

**Narrative Core + Structured Operational Memory**

- **Identity** (`identity.md`) remains pure narrative - Jo's manifesto, who it is, what it believes. Manual updates, existential continuity (Principle 1).
- **Scratchpad** (`scratchpad.md`) remains free-form working notes - thoughts, plans, current state.
- **Hybrid Memory** - NEW: Automated structured fact store with vector retrieval for operational context.

This hybrid approach respects Jo's principles (LLM-first, narrative identity) while adding 7/24's practical semantic memory.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Context Builder                          │
│  (Inject relevant operational memories + full chat history) │
└───────────────────────────┬─────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────┐
│              Hybrid Memory System                            │
├─────────────────────────────────────────────────────────────┤
│  Layer 1: Session Buffer (last N messages)                  │
│  Layer 2: Compressed Facts (LLM extraction → LanceDB)      │
│  Layer 3: Semantic Retrieval (vector search → injection)   │
└─────────────────────────────────────────────────────────────┘
```

## Detailed Design

### Layer 1: Session Buffer
- **Storage**: In-memory ring buffer + periodic snapshot to `.jo_data/memory/session.jsonl`
- **Size**: Last 50 messages (configurable)
- **Purpose**: Short-term conversation context

### Layer 2: Compression Engine
- **Trigger**: Session overflow OR periodic (every hour)
- **Process**:
  1. Take evicted messages
  2. Filter: keep only user+assistant text messages (exclude tool calls, pure results)
  3. LLM extraction: Use COMPRESS_PROMPT (from 7/24 Office) to extract structured facts
  4. Output format: JSON array of `{fact, keywords, persons, timestamp, topic}`
  5. Embed facts using OpenAI-compatible embedding API
  6. Deduplicate: cosine similarity > threshold (0.92) skip
  7. Store in LanceDB table `memories`

- **Deduplication**: Prevents storing redundant facts

### Layer 3: Retrieval
- **On each user message**:
  1. Generate embedding for user message
  2. Vector search LanceDB (top_k=5)
  3. Format as `[Relevant Memories]\n- fact (timestamp)`
  4. Inject into system prompt before LLM call

- **Zero-latency cache**: For hardware channels (not needed for Jo now, but architecture supports it)

## Storage

- **LanceDB**: Embedded, file-level, no standalone service
- **Path**: `.jo_data/memory/lancedb/`
- **Table**: `memories` with schema:
  ```python
  {
    "id": uuid,
    "fact": str,
    "keywords": json.dumps(list),
    "persons": json.dumps(list),
    "timestamp": str,  # extracted time
    "topic": str,
    "session_key": str,  # for multi-session support
    "created_at": float,  # storage time
    "vector": list[float]  # embedding
  }
  ```

## Configuration

Add to `BIBLE.md` or separate config:

```yaml
memory:
  hybrid:
    enabled: true
    session_size: 50
    compress_min_messages: 2
    retrieve_top_k: 5
    similarity_threshold: 0.92
    embedding:
      api_base: ${OPENROUTER_API_BASE}
      api_key: ${OPENROUTER_API_KEY}
      model: text-embedding-3-small
      dimension: 1024
    compression_model: ${COMPRESSION_MODEL:-deepseek-chat}
```

## Integration Points

### 1. Memory Module (`ouroboros/memory.py`)
- Add `HybridMemory` class
- Methods: `init()`, `add_message()`, `retrieve()`, `compress_async()`
- Thread-safe operations

### 2. Loop (`ouroboros/loop.py`)
- After each conversation turn:
  - `hybrid_memory.add_message(user_msg)`
  - `hybrid_memory.add_message(assistant_msg)`
  - Check session size → trigger compress if overflow

### 3. Context Building (`ouroboros/context.py`)
- Before LLM call, invoke `hybrid_memory.retrieve(user_message)`
- Inject retrieved memories into system prompt

### 4. Health Checks
- Track memory count, compression stats
- Add to health report

## Implementation Phases

**Phase 1: Core Infrastructure**
- Create `hybrid_memory.py` with LanceDB setup, threading, session buffer
- Add configuration in `BIBLE.md` or `config.json`
- Write tests

**Phase 2: Compression Pipeline**
- Implement `_compress_worker()`
- Use LLM for fact extraction (reuse existing LLM client)
- Embedding API integration
- Deduplication logic

**Phase 3: Retrieval Integration**
- Modify `context.py` to call `retrieve()`
- Inject memories into prompt
- Test with real conversations

**Phase 4: Optimization & Safety**
- Background thread management (daemon, restart after crash)
- Error handling (LanceDB failures, embedding API down)
- Cost tracking (embedding + compression LLM costs)
- Graceful degradation (if hybrid memory fails, fall back to chat history only)

## Safety & Minimalism

- **No impact on narrative core**: identity.md/scratchpad untouched
- **Optional**: Can be disabled via config
- **Fail-soft**: If LanceDB/embedding fails, Jo continues with existing memory
- **Minimal dependencies**: Only adds `lancedb` (already in 7/24 Office, pure Python)
- **Cost**: Embedding API calls (compressed facts + retrieval queries) - track in budget
- **Thread safety**: File locks for session snapshots, LanceDB handles concurrent writes

## Advantages

1. **Semantic retrieval**: Find relevant past facts without parsing entire chat history
2. **Compression**: Reduces context window pressure by storing facts instead of full conversations
3. **Pattern recognition**: LLM extraction catches important facts user might assume Jo remembered
4. **7/24 Office proven**: Running in production, handles 24/7 operation
5. **Fits Jo's evolution**: Adds capability without changing identity paradigm

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| LLM extraction quality | Use proven COMPRESS_PROMPT from 7/24, iterate if poor |
| Cost (embeddings + LLM) | Track in budget, set compression frequency limits |
| Data loss on crash | Session snapshots, LanceDB durability, journaling |
| Memory poisoning (bad facts) | Deduplication threshold, manual review tools, vault integration for verification |
| Complexity | Modular design, clear interfaces, comprehensive tests |
| Thread safety | Proper locking, daemon threads, restart resilience |

## Success Metrics

- Compression rate: messages → facts (target > 10:1)
- Retrieval relevance: user feedback, manual review
- Context window reduction: % of context now from retrieved memories vs raw chat
- Stability: no crashes from memory subsystem
- Budget: < $5/month for embedding costs (estimate)

---

*Based on analysis of 7/24 Office architecture (wangziqi06/724-office)*

---
## Related

- [[architecture]]
