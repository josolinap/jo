---
type: Infrastructure
title: OmniRoute Master-Orchestrator — egress fix + client + swarm wiring
description: OmniRoute egress sandbox root cause + fix; master-orchestrator client; swarm --master mode; live proof
tags: [omniroute, systemd, egress, free-models, master-router, research-swarm]
created: "2026-09-08T00:56:55.797680+00:00"
updated: "2026-09-08T00:56:55.797746+00:00"
source: derived
confidence: 0.8
status: active
access_count: 2
last_accessed: "2026-11-07T15:28:30.909019+00:00"
reinforcement_count: 2
---

## Root cause

The **11-day free-model outage** (Aug 27 → Sep 7 2026) was NOT a network/provides issue — it was a systemd egress sandbox. The Sep-01 reinstall restored `IPAddressDeny=any` + `IPAddressAllow=127.0.0.1/8,100.64.0.0/10,fd7a:115c:a1e0::/48` in `/etc/systemd/system/arch-neo-omniroute.service.d/hardening.conf`, silently blocking ALL public upstreams for the OmniRoute router (:20128). Direct curl/Node probes reached provider APIs in 0.1–0.24s while the router timed out → packets were being DROPPED at the service boundary, not refused.

The same class of bug broke tg-bridge (Sep-01) — **any service whose job is reaching public providers must NOT have IPAddressDeny**.

## Fix

Removed the IPAddress lines (backup `hardening.conf.bak-ipfix-0907`, inline comment), `systemctl daemon-reload && systemctl restart arch-neo-omniroute`. Verified running config shows empty `IPAddressDeny=`/`IPAddressAllow=`. Provider health went 2 → 8 active (g4f-gemini, g4f-groq, g4f-nvidia, hackclub, nvidia, opencode, openrouter, pollinations).

## Master-orchestrator architecture

- `tools/omniroute_master.py` — read-only sqlite (`file:/root/.omniroute/storage.sqlite?mode=ro`) health/routes + app.log completion counter (BOTH log formats: legacy `[STREAM] X | model | Xms | complete` and 2026+ `Model provider/model succeeded (Nms, M fallbacks)`, merged under uppercase per-provider keys) + `chat()` POST to `{OMNI_BASE}/chat/completions` (anonymous or key, stream:false, honest error surfacing). CLI: status|routes|usage|chat|test.
- `tools/research_swarm.py --master` — routes swarm tasks through the router's `auto` chain: router picks healthiest provider, applies cooldowns/circuit-breakers, retries internally. `_master_mod` loaded once at import (patchable, graceful degradation if the module is unavailable).
- `tools/run_research_swarm.sh` — cron wrapper now defaults to `--master`.
- Auto-routes in key_value: `auto:auto`→dahl, `auto/best-free`→felo-web, `auto/best-coding`→nvidia, `auto/coding:free`→felo-web.
- `REQUIRE_API_KEY=false` → anonymous requests OK; wrong bearer falls through to anonymous ("invalid bearer ... falling through to anonymous").

## Live proof (2026-09-08 00:47)

Swarm run via master: memory-retrieval ✅ MiniMaxAI/MiniMax-M2.7 (16.8s), governance ✅ MiniMax-M2.7 (11.1s), tool-reliability ❌ timeout, self-improvement ❌ HTTP 401 (router tried opencode/big-pickle, hy3-free, openrouter — all exhausted), multi-model ✅ glm-4.7-flash (10.6s). Counters went 182 (legacy only) → 265 (both formats merged).

## Caveats

- `/v1/models` returns EMPTY even with key — model IDs come from app.log success lines / known sets (e.g. `zai/glm-4.7-flash`, `openrouter/nvidia/nemotron-3-ultra-550b-a55b:free`, `dahl/MiniMaxAI/MiniMax-M2.7`).
- Router internal retry chains (3 × cooldowns) can exceed client timeouts → timeouts reported to clients are not necessarily provider failures.
- dahl `inference.dahl.global/v1/models` still times out; openrouter key is invalid upstream ("User not found").
- Related concept: infra/omniroute-routing (provider table, ports 20128/20132, CLI broken due to missing update-notifier).

## Related
- [[infrastructure/omniroute-free-model-mechanism]] — OmniRoute Free-Model Acquisition Mechanism
- [[research/omniroute-free-gateway-study-2026]] — OmniRoute + free-claude-code study: free-model gateway landscape (Aug 2026)
- [[infrastructure/omniroute-gateway]] — OmniRoute Free AI Gateway (archlinux)
- [[research/agent-swarm-architecture-2026]] — Agent Swarm Architecture — Combining ServerlessClaw, Prime Agent, CCR, Omnigent
- [[research/swarm-orchestration-2026]] — Swarm Orchestration SOTA 2026 — fan-out contracts, deterministic verifiers
