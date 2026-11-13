---
type: Tool
title: Confidence-Based Model Cascading — escalate on failure/complexity (P0-4, 2026-09-04)
tags: [model-cascade, frugalgpt, free-models, P0]
created: "2026-09-04T07:16:51.866245+00:00"
updated: "2026-09-04T07:16:51.868452+00:00"
source: infra
confidence: 0.85
status: active
access_count: 0
last_accessed: "2026-11-09T18:40:12.240599+00:00"
reinforcement_count: 0
---

# Confidence-Based Model Cascading (P0-4)

Implements the FrugalGPT / CascadeLMs pattern: start with the cheapest fastest
free model and escalate to progressively stronger models only when needed.

## Files
- `tools/confidence_cascade.py` — the cascade engine + CLI
- `tvec/tests/test_confidence_cascade.py` — 13 tests

## Tier model
- Tier 0 (fast): tiny models for trivial calls
- Tier 1 (balanced): mid-size workhorses (glm-4.5-flash, nemotron-super-120b)
- Tier 2 (strong): larger models (nemotron-ultra-550b)
- Tier 3 (max): reserved for complex/high-stakes (big-pickle)

## Escalation triggers
1. force_tier wins outright
2. Task-family failure rate > 30% bumps +1 tier (failure tracking persisted)
3. Complexity keywords (security/architecture/plan/review/audit/...) → tier 2+
4. Long prompt (>1500 chars) bumps +1
5. Explicit depth markers (think/deep/careful/thorough) → tier 1+

## Task families
code, research, security, planning, debug, general — each tracks calls/failures
to drive failure-rate escalation.

## Why
- Free models have no API cost difference but dramatically different speed
  and quality. Cascade lets trivial calls use tiny models and reserves
  strong models for complex reasoning — reducing latency and token load.
- [[tools/graphify-cli]]
- [[tools/agent-grep]]
