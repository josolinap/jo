---
type: Tool
title: Dynamic Free-Model Catalog
description: Aggregates freellmapi + OmniRoute + bench leaderboard free models into one live catalog with pick/verify/chat
tags: [free-models, swarm, omniroute, freellmapi, catalog, llm]
created: "2026-08-12T01:11:01.830898+00:00"
updated: "2026-08-12T01:11:01.830962+00:00"
source: manual
status: active
confidence: 0.219
access_count: 2
last_accessed: "2026-10-24T12:35:03.153401+00:00"
reinforcement_count: 2
---

Single source of truth for every *free* model Arch-Neo can actually call, live.

## Sources (aggregated on refresh, ~3s)
1. **freellmapi** (`127.0.0.1:3001/v1`) — every available model routes at cost 0 (deepseek-v4-flash, glm-4.7-flash, gpt-oss-120b, big-pickle, auto/fusion routers…). Availability is authoritative per model.
2. **OmniRoute** (`127.0.0.1:20128/v1`) — fast `/v1/models` endpoint; free slice = `oc/*` (opencode Zen keyless) + keyless mirror providers (g4f*, glb*, hc, dahl, unc, mcode) + known-free openrouter `:free`. Trusted = explicitly free-marked (`-free`/`:free`) or curated in the opencode.json omniroute provider block.
3. **Bench leaderboard** (`state/swarm_bench_*.json`, written by `tools/swarm_router.py bench`) — models the bench proved routable through OmniRoute that `/v1/models` hides: `g4fnv/z-ai/glm-5.2` (98ms, score 1.0), g4fgroq/*, felo/*, dahl/*. Health OK ⇒ live/trusted; latency maps to tier (flash <150ms).

## Picking strategies
- `round-robin` — swarm default, spreads load
- `random` — uniform
- `smart` — prefers router models (auto/fusion)
- `bench` — best healthy model from the leaderboard (score desc, latency asc), graceful fallback to rr

Picks prefer verified-live, then trusted; broken models (BROKEN_DEFAULT + provider blocklist, e.g. pol after key requirement) are excluded by default. `verify` probes live with tiny completions; probe results carry over across refreshes.

## Chat resilience
`chat()` rotates to another free model on HTTP 429/cooldown (max `fallbacks` attempts) without burning the cooling model's live flag (cooldown ≠ dead). Explicit `--model` requests never silently rotate.

## Usage
```bash
python3 tools/free_model_catalog.py list|pick|chat|refresh|verify|status
python3 swarm/make_worker.py [--strategy bench] [--apply]   # regen neo-worker.yaml
python3 tools/swarm_router.py list|pick <task-type>|bench   # bench leaderboard
```

## Integration
- `swarm/free_models.py` — facade: `pick_worker_model()` / `worker_spec()` / `chat_worker()`
- `swarm/orchestrator.py` — `llm_agent` role fans a brainstorm/synthesize/summarize goal to 2 free models (round-robin + random) + meta_agent merge
- `swarm/make_worker.py` — writes `swarm/agents/neo-worker.yaml` for the omnigent server (`--apply` restarts `neo-omnigent-server`)
- `tvec/oo_agents/model.py` — `OpenAICompatClient` (browser UA to pass WAFs, `stream:false`, 429 retry/backoff, reasoning-content fallback)

Keyed by `gateway:id` so freellmapi `big-pickle` and omniroute `oc/big-pickle` stay distinct. stdlib-only (AVX2-less E1-2100 safe).
