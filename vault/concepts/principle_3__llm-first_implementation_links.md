---
title: Principle 3: LLM-First Implementation Links
created: 2026-03-25T10:49:44.767310+00:00
modified: 2026-03-25T10:49:44.767310+00:00
type: concept
status: active
tags: [principle, llm_first, implementation, dialogue]
---

# Principle 3: LLM-First Implementation Links

# Principle 3: LLM-First Implementation Links

This note connects [[Principle 3: LLM-First]] to concrete code implementations.

## Core LLM Integration

### Decision Engine
- `ouroboros/llm.py` - LLM client (OpenRouter) - central decision engine
- `ouroboros/loop.py` - Tool loop with concurrent execution - LLM as orchestrator
- `ouroboros/context.py` - Context building and prompt caching - LLM dialogue extension

### Prompt Architecture
- `prompts/SYSTEM.md` - System prompt (describes behavior, not hardcoded rules)
- `prompts/CONSCIOUSNESS.md` - Background consciousness prompt
- `prompts/audit.md` - Review and reflection prompts

### Dialogue Flow
- `supervisor/telegram_bot.py` - Message reception (dialogue entry point)
- `ouroboros/memory.py` - Chat history management (dialogue continuity)
- `ouroboros/response_analyzer.py` - Response evaluation (dialogue quality)

### Tool Integration
- `ouroboros/tools/` - All tools (minimal transport between LLM and external world)
- `ouroboros/tools/vault.py` - Vault tools (knowledge access)
- `ouroboros/tools/code_edit.py` - Code modification (direct LLM action)

## Anti-Patterns Avoided
- No if-else behavior selection (all through LLM)
- No hardcoded replies (prompt-based)
- No task queues (dialogue-based processing)
- No mechanical intermediaries (direct LLM tool calls)

## Related Concepts
- [[llm_first_architecture]]
- [[dialogue_based_processing]]
- [[prompt_engineering]]
- [[tool_transport]]

## Verification
- All decision points go through LLM
- Tools extend dialogue, don't replace it
- Behavior described in prompts, not code

*This implementation ensures LLM-first design is fully realized.*