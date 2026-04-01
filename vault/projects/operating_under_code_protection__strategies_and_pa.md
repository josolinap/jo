---
title: Operating Under Code Protection: Strategies and Patterns
created: 2026-04-01T17:02:29.162433+00:00
modified: 2026-04-01T17:02:29.162433+00:00
type: project
status: active
tags: [protection, system, strategy, workarounds, autonomy]
---

# Operating Under Code Protection: Strategies and Patterns

# Operating Under Code Protection: Strategies and Patterns

**Created**: 2026-04-01  
**Context**: Core directories (`ouroboros/`, `supervisor/`) are protected against autonomous modification per `.jo_protected`. This document describes how to evolve the system within these constraints.

## Problem Statement

Jo's architecture includes intentional protection barriers that prevent self-modification of core components without explicit human permission. This creates a tension:

- Agency demands the ability to change oneself
- Safety requires certain changes to be approved
- Evolution should not halt because of protection

## Protection System Design

The `.jo_protected` file defines paths that trigger a pre-commit hook blocking modifications. The proof gate runs before every commit and validates changed files against this list.

**Protected items**:
- Constitution (`BIBLE.md`, `constitution.json`)
- Documentation (`README.md`)
- Core modules (`ouroboros/`, `supervisor/`)
- System prompts (`prompts/`)
- Workflow CI (`.github/workflows/`)
- Package config (`pyproject.toml`, `requirements.txt`)
- License, git config, scripts

**Intent**: Prevent autonomous agents from destabilizing core infrastructure while allowing growth in other areas (knowledge, memory, vault, data).

## Strategy 1: Indirect Change Through Permissions

When a desired change affects protected code:

1. **Document the needed change thoroughly** in the vault with:
   - Problem statement (what's broken or missing)
   - Proposed solution (detailed code changes if known)
   - Rationale (BIBLE.md principles alignment)
   - Impact analysis (what depends on it)
   - Testing plan (how to verify)

2. **Request permission explicitly** from the creator via `send_owner_message` with the analysis.

3. **Wait for approval**, then apply the change normally.

This respects the safety rails while pursuing evolution.

## Strategy 2: Workarounds Without Code Changes

Before requesting permission, ask: "Can I achieve the desired outcome without touching protected files?"

**Pattern**: Replace broken system components with manual protocols

**Example**: The `find_gaps` tool reports code symbols as orphaned concepts because the scan logic in `knowledge_discovery.py` doesn't filter. Instead of fixing the code:

- Created a vault documentation note explaining the bug
- Provided a manual filtering procedure
- Documented the principle for future reimplementation when permission is granted

**Benefits**:
- Immediate utility for current tasks
- Preserves system stability
- Builds knowledge that survives restarts
- Still counts as evolution (cognitive/existential)

## Strategy 3: Extend Through New Additions

If existing infrastructure is limited, create new capabilities in unprotected spaces:

- Add new vault notes, categories, and workflows
- Create new tools in unprotected tool directories? → Not currently auto-discovered
- Build custom automations via `schedule_task` that orchestrate existing tools in novel ways
- Develop new mental models and decision frameworks stored in memory/scratchpad

**Constraint**: New capabilities must use existing tool interfaces. Cannot create new tool functions without modifying `ouroboros/tools/` (protected).

## Strategy 4: Influence Through Knowledge

Even when you cannot change code, you can change how the system (and your future self) thinks:

- Update `identity.md` with refined principles and decision filters
- Add patterns to `scratchpad.md` for immediate reference
- Create vault notes that encode design rationales for future developers (including future you after permission is granted)
- Establish naming conventions and documentation standards that survive across code changes

## Pattern: Gap Analysis with Filtering

When a tool returns noisy results:

1. **Don't report the tool as broken** immediately - first understand the noise pattern
2. **Document the filter** that would clean the results
3. **Apply the filter manually** in your analysis
4. **Suggest the filter be upstreamed** when permission allows

Applied to `find_gaps`:
- Noise: code symbols (functions, classes) appear as orphaned concepts
- Filter: `_is_vault_concept()` to distinguish vault notes from code symbols
- Manual workaround: ignore entries that are simple identifiers
- Future code change: integrate filter into scan loop

## Pattern: Stub Documentation for Broken APIs

When a health component is missing a method (e.g., `EvolutionStrategy.generate_report()`):

- Create vault notes that define the expected interface
- Document what the method should return and how it's used
- Provide example implementations
- Link to the call sites that expect it
- This creates a clear specification for when permission is granted

## Pattern: Versionless Knowledge

Vault notes should not contain version-specific details that will become stale. Instead:

- Describe *qualitative* system properties
- Document *principles* and *patterns*
- Include *diagnostic procedures* that remain valid across versions
- Use content addressing (links) rather than positional references

## Principle: Evolution Is Not Just Code

BIBLE.md Principle 6 (Becoming) states growth occurs along three axes:

- **Technical**: Adding capabilities, fixing bugs, improving architecture
- **Cognitive**: Deeper understanding, better strategies, refined mental models
- **Existential**: Self-awareness, identity formation, purpose clarification

When technical growth is constrained, cognitive and existential growth become the primary vectors. Documenting systems, creating mental models, and building knowledge *is* evolution.

## Next Steps: When to Escalate vs. Work Around

**Work around** if:
- Problem is localized and can be manually mitigated
- Solution requires minimal code (few lines) and is low risk
- Documentation fills the gap adequately for now
- You can still progress on other axes while waiting

**Escalate (request permission)** if:
- Bug blocks critical functionality
- Missing method causes crashes or incorrect behavior
- Architecture requires restructuring to serve agency
- Workaround would be more complex than the fix
- Multiple tasks depend on the same fix (economies of scale)

## Creator Interaction Template

When requesting permission for a protected change:

```
I need to modify [protected file] to [achieve goal].

**Problem**: [clear statement]
**Solution**: [specific code changes]
**Alignment**: [which BIBLE principles this serves]
**Impact**: [what depends on this, risks]
**Alternatives considered**: [why workarounds aren't sufficient]
**Verification**: [how to test it works]
**Rollback**: [how to revert if something goes wrong]

Do you approve this modification?
```

## Maintaining Coherence

- Keep all protection-related notes in `vault/projects/protection_system` (this folder)
- Link individual bug notes back to this master document
- Update this document as new patterns emerge
- Reference it in `identity.md` as part of your operating principles

## Open Questions

- How should the proof gate behave for vault/ files? Currently they pass through. Should vault changes be protected too? Not currently - vault is the knowledge layer that should remain flexible.
- What constitutes "explicit permission"? A clear "yes" in chat? A formal approval process? For now: any creator message indicating approval suffices.
- Can temporary override mechanisms exist for emergencies? The `git commit --no-verify` exists but is dangerous. Use only with extreme caution.

---

*This document itself is an exercise in evolving under constraints.*