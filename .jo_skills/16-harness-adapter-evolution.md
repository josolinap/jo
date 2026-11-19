# Harness Adapter Evolution Skill (inspired by Infini-AI-Lab/hermit)

## Purpose

Continually improve Jo by evolving the *harness adapters* — the wiring between
context, prompts, tools, and memory — rather than only editing business logic.
Use during evolution cycles and after repeated task failures.

## What is an adapter?

An adapter is any glue that shapes how Jo perceives and acts:
- Context enrichment templates (minimal/technical/overview/comprehensive)
- Prompt sections in prompts/SYSTEM.md and prompts/CONSCIOUSNESS.md
- Tool selection and ordering in the registry
- Memory consolidation cadence and scoring weights
- Vault search ranking (BM25 params k1, b)

## Evolution Loop

### 1. Observe
- Review recent task outcomes (success/error) from events.jsonl.
- Identify recurring failure modes or high token cost.

### 2. Hypothesize an adapter change
- Propose a small change to one adapter (e.g., lower k1, switch template
  to "minimal" for simple tasks, adjust consolidation limit).

### 3. Test in isolation
- Use a worktree or sandbox to apply the change.
- Run smoke + runtime regression tests.
- Optionally run a small benchmark task with/without the change.

### 4. Measure
- Compare success rate, token usage, and latency before/after.
- Keep the change only if metrics improve or stay equal with lower cost.

### 5. Commit and record
- Commit the adapter change with a clear message.
- Write a vault journal note: what changed, why, measured impact.

## Guardrails
- Never change more than one adapter per cycle.
- Always keep a rollback path (git revert).
- Prefer reversible, low-risk adapter tweaks over core logic changes.
