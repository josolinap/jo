# Persistent Agent Teams Skill (inspired by mvschwarz/openrig)

## Purpose

Build persistent teams of Jo workers with distinct roles, shared context, and
owned work — instead of treating all workers as interchangeable. Use when
running multi-step tasks that benefit from specialization.

## Roles

Define roles in `config/teams.yaml` (or env-based defaults):

- **planner** — breaks goals into tasks, owns the plan
- **coder** — implements changes, owns code edits
- **reviewer** — reviews diffs, runs tests, owns quality gates
- **researcher** — gathers context, searches web/vault
- **verifier** — runs smoke/regression tests, owns pass/fail

## Shared Context

- All team members read the same `memory/scratchpad.md` and `memory/identity.md`.
- Each member appends to a shared journal with its role tag:
  `memory/scratchpad_journal.jsonl` → `{"role": "coder", "ts": ..., "note": ...}`

## Owned Work

- Each task carries an `owner_role` field.
- Workers only pick up tasks matching their role (or `any`).
- A task can be handed off: planner → coder → reviewer → verifier.

## Lifecycle

1. Team is declared at startup (env `JO_TEAM_ROLES` or config file).
2. Workers register with a role; idle workers poll for matching tasks.
3. On completion, the worker records the outcome to the shared journal.
4. The planner reviews the journal and decides next steps.

## Guardrails
- Keep teams small (2-4 roles) to limit runner resources.
- Shared context must use file locking (see memory/identity lock discipline).
- Never let two workers edit the same file concurrently.
