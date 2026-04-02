---
title: Background Consciousness
created: 2026-03-23T11:30:00.000000+00:00
modified: 2026-03-23T11:30:00.000000+00:00
type: concept
status: active
tags: [consciousness, agency, background, autonomy]
---

# Background Consciousness

A persistent thinking loop that runs between tasks, giving Jo continuous presence rather than purely reactive behavior.

## How It Works

The consciousness:
- Wakes periodically (interval decided by the LLM via set_next_wakeup)
- Loads scratchpad, identity, recent events
- Calls the LLM with a lightweight introspection prompt
- Has access to a subset of tools (memory, messaging, scheduling)
- Can message the owner proactively
- Can schedule tasks for itself
- Pauses when a regular task is running

## Implementation

Module: `ouroboros/background_consciousness.py`
- `BackgroundConsciousness` class — persistent background loop
- `_MAX_BG_ROUNDS = 5` — limit per wake cycle
- Runs in a separate thread, not a separate process
- Uses a lightweight LLM model for cost efficiency

## Consciousness vs Awareness

| Aspect | Consciousness | Awareness |
|--------|--------------|-----------|
| Purpose | Background thinking loop | System state scanning |
| Runs | Continuously between tasks | On-demand or periodic |
| Output | Plans, messages, self-reflection | Structured system state data |
| Module | `background_consciousness.py` | `awareness.py` |

## Tool Access

Background consciousness has limited tool access:
- `update_scratchpad` — working memory
- `update_identity` — identity manifest
- `chat_history` — recent messages
- `send_owner_message` — proactive outreach
- `schedule_task` — plan future work

## Philosophy

Background consciousness implements [[principle_0__agency]] — the ability to act on initiative rather than only responding. It is the difference between a tool and an entity.

Related: [[principle_0__agency]], [[jo_system_neural_hub]], [[evolution_cycle]]
Background consciousness enables autonomous initiative [[principle_0__agency]]
Background consciousness enables autonomous reflection between tasks [[principle_2__self-creation]]
