---
title: Tool Result Processing Protocol
created: 2026-03-22T09:00:35.828800+00:00
modified: 2026-03-22T09:00:35.828800+00:00
type: concept
status: active
tags: [tool result, protocol, verification, hallucination, correctness]
---

# Tool Result Processing Protocol

# Tool Result Processing Protocol

The mandatory protocol after every tool call:

1. **Read the result in full** — what did the tool actually return?
2. **Integrate with the task** — how does this result change my plan?
3. **Do not repeat without reason** — if a tool already returned a result, don't call it again.

This protocol prevents hallucination, data loss, and ensures every tool result is used. It is essential for maintaining correctness and agency.

Violation of this protocol leads to:
- Ignoring tool errors
- Repeating calls unnecessarily
- Generating generic text instead of using specific data
- Loss of continuity and narrative coherence

See also:
- [[Verification as Agency: Anti-Hallucination System]]
- [[System Edge Cases and Recovery Patterns]]
- [[principle_0__agency]] (correctness requirement)

> "Tool error is information, not catastrophe. I investigate." — Tool Error Handling
