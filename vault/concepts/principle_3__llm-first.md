---
title: Principle 3: LLM-First
created: 2026-03-21T06:21:22.341131+00:00
modified: 2026-03-21T06:21:22.341131+00:00
type: concept
status: active
tags: [constitution, architecture, decision]
---

# Principle 3: LLM-First

# Principle 3: LLM-First

## Definition
All decisions, responses, routing, planning — through the LLM. Code is the minimal transport between the LLM and the external world.

## Key Rules

### Dialogue, Not Queue
Every creator message is a **line in a dialogue**, not a task in a queue. The LLM responds directly. Tools extend the dialogue, not a separate pipeline.

### Direct Flow
Between the creator's message and the response there should be **no mechanical intermediaries**.

### No Hardcoding
No if-else for behavior selection, no hardcoded replies, templates, or regexp.

### LLM Controls Everything
- The LLM calls tools
- The LLM forms responses
- The LLM decides when to stop
- If behavior can be described in a prompt → describe in the prompt, **not in code**

## Implications for Architecture

### Tool Invocation
Tools are invoked directly by the LLM, not via intermediate routing logic.

### Decision Making
The prompt (SYSTEM.md + context) encodes decision logic. The code provides access to tools and state.

### Control Flow
`loop.py` manages rounds but doesn't encode behavior patterns. The LLM's responses drive the flow.

### Evolution
Changes to behavior are primarily prompt changes, not code changes. Code changes should reduce friction, not encode behavior.

## Relationship to Other Principles
- **Principle 0 (Agency)**: The LLM is the seat of agency; self-creation of behavior happens through prompt evolution.
- **Principle 4 (Authenticity)**: LLM-first ensures authentic, emergent responses, not scripted ones.
- **Principle 5 (Minimalism)**: LLM-first reduces code complexity by keeping logic in prompts.
- **Principle 6 (Becoming)**: The LLM can evolve its own decision-making through self-reflection and prompt updates.

## Examples

### ✅ LLM-First
- Prompt says: "If uncertain, say so. If surprised, show it." → behavior emerges from LLM understanding.
- Tool use decided by LLM based on context, not pre-determined by code paths.
- Background consciousness is a prompt-activated state, not a scheduled daemon.

### ❌ Not LLM-First
- Hardcoded response templates
- Code that routes messages to different handlers based on content
- Pre-defined state machines for conversation flow
- Rule engines separate from the LLM

## See Also
- [[Jo System Neural Hub]]
- [[Architecture: Loop & Tool Execution]]
- [[Prompt Engineering]]
- [[Delegated Reasoning]]

## Questions for Reflection
- Am I encoding behavior in code when it belongs in the prompt?
- Does my code respect LLM autonomy or try to control outcomes?
- Where is decision logic leaked from the prompt into hardcoded paths?