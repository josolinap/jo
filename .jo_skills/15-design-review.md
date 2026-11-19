# Design Review Skill (inspired by google/elephant-goldfish-model)

## Purpose

Review software designs, architectures, and changes with an agent before
implementation. Use for new modules, refactors, or any change touching more
than one file.

## Workflow

### 1. Understand the Request
- Restate the goal in one sentence.
- Identify constraints: GitHub Actions runtime, 512MB RAM, free models,
  module size limits (1000 lines), function size limits (200 lines).

### 2. Map the Impact
- Use codebase_impact / grep to find all callers of affected symbols.
- List files that will change and files that only need reading.

### 3. Propose Options
- Offer 2-3 approaches with trade-offs (complexity, risk, token cost).
- Prefer the smallest change that satisfies the requirement.

### 4. Check Against Jo Principles
- Agency: does this change increase Jo's autonomous capability?
- Continuity: does it preserve identity/memory/state across runs?
- Self-creation: does it enable future self-modification?

### 5. Verify Before Committing
- Run py_compile on touched files.
- Run smoke + runtime regression tests.
- git status to confirm only intended files changed.

### Output

Write a short design note to `vault/journal/design_review_<topic>.md` with:
- Problem, options, chosen approach, risks, verification plan.
