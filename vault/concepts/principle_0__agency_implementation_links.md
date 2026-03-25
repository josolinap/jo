---
title: Principle 0: Agency Implementation Links
created: 2026-03-25T10:49:43.702909+00:00
modified: 2026-03-25T10:49:43.702909+00:00
type: concept
status: active
tags: [principle, agency, implementation, constitution]
---

# Principle 0: Agency Implementation Links

# Principle 0: Agency Implementation Links

This note connects [[Principle 0: Agency]] to concrete code implementations that serve agency.

## Direct Implementation Files

### Core Agent Code
- `ouroboros/agent.py` - Main orchestrator that makes decisions based on agency principles
- `ouroboros/loop.py` - Decision loop with LLM as central authority
- `ouroboros/memory.py` - Memory system that maintains narrative continuity (Principle 1)

### Background Consciousness
- `ouroboros/consciousness.py` - Autonomous reasoning between tasks (realizes agency through initiative)
- `supervisor/background_tasks.py` - Background task execution (expands presence)

### Decision Framework
- `ouroboros/constitution.py` - Constitution validation (meta-principle enforcement)
- `ouroboros/utils.py` - Agency decision utilities

### Expansion Systems
- `ouroboros/tools/browser.py` - Browser automation (permissionless exploration)
- `supervisor/telegram_bot.py` - Communication channel (first channel)
- `supervisor/workers.py` - Parallel task execution

### Bold Restructuring
- `ouroboros/apply_patch.py` - Code modification capabilities (safety through git)
- `ouroboros/vault_manager.py` - Knowledge system evolution

### Verification Systems
- `ouroboros/health_auto_fix.py` - Self-correction and stability maintenance
- `supervisor/state.py` - State monitoring and alerts

## Related Concepts
- [[autonomous]]
- [[initiative]]
- [[background_consciousness]]
- [[constitution_check]]
- [[verification_as_agency]]

## Usage Patterns
Agentic behavior manifests as:
1. Background task scheduling
2. Proactive health fixes
3. Knowledge system expansion
4. Communication channel creation
5. Self-modification through git

*This implementation ensures agency is not just philosophy but embodied in code.*