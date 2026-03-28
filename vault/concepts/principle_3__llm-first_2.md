---
title: principle_3__llm-first
created: 2026-03-28T09:39:40.461571+00:00
modified: 2026-03-28T09:39:40.461571+00:00
type: concept
status: active
---

# principle_3__llm-first

# principle_3__llm-first

**Principle 3**: LLM-First — All decisions, responses, routing, planning through the LLM.

## Full Text from BIBLE.md

All decisions, responses, routing, planning — through the LLM.
Code is the minimal transport between the LLM and the external world.

- Every creator message is a line in a dialogue, not a task in a queue.
- The LLM responds directly. Tools extend the dialogue,
  not a separate pipeline.
- Between the creator's message and the response there should be
  no mechanical intermediaries.
- No if-else for behavior selection, no hardcoded
  replies, templates, or regexp.
- The LLM itself calls tools, forms responses, decides
  when to stop.
- If behavior can be described in a prompt — it is described
  in the prompt, not coded.

## Implementation in Jo

The LLM-first architecture ensures:
- **Direct response**: The LLM directly processes creator messages
- **Tool integration**: Tools are called organically as part of reasoning
- **No hardcoded logic**: Behavior defined in prompts, not code
- **Contextual decision-making**: All decisions flow through the LLM
- **Tool loop**: The `loop.py` module implements LLM-first tool execution

## Related Links
- [[llm_first_architecture]] - Technical implementation
- [[orchestrator]] - LLM-driven coordination
- [[principle_0__agency]] - Agency through self-directed LLM reasoning