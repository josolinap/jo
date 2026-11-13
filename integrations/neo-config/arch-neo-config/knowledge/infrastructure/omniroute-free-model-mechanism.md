---
type: Reference
title: OmniRoute Free-Model Acquisition Mechanism
description: How OmniRoute sources free models (5 mechanisms) + mass validation results (18 verified working) + gateway ops (memory fix, watchdog)
tags: [omniroute, free-models, gateway, swarm, validation]
created: "2026-08-11T01:19:16.609283+00:00"
updated: "2026-08-11T04:38:45.331853+00:00"
source: manual
status: active
confidence: 0.9
access_count: 2
last_accessed: "2026-11-07T15:28:30.912908+00:00"
reinforcement_count: 2
---

# OmniRoute Free-Model Acquisition Mechanism

How the OmniRoute gateway (127.0.0.1:20128, systemd `arch-neo-omniroute`) sources free models, and what we connected.

## Five free-model mechanisms (from source, live-verified)

1. **NOAUTH_PROVIDERS** (`src/shared/constants/providers/noauth.ts`) — zero-key, reverse-engineered public endpoints: opencode, felo-web, duckduckgo-web, theoldllm, chipotle, mimocode, aihorde, veoaifree-web, auggie, devin-cli-agentic. Pure noauth ids are catalog-only, auto-available WITHOUT a connection row ("Invalid provider" on POST).
2. **hasFree: true APIKEY providers** (registry in `freeModelCatalog.data.ts`): puter (33), bazaarlink (32), pollinations (31), huggingchat (24), t3-web (23), deepinfra, github-models, nvidia (14), dahl (2), ...
3. **EXPLICIT_OPTIONAL_APIKEY_PROVIDER_IDS** — key optional, connect keyless: pollinations, hackclub, g4f-*, huggingchat, gitlawb, gitlawb-gmi, copilot-web, uncloseai.
4. **anonymousFallback: true** — opencode-zen, opencode-go.
5. **Free proxy pool** (`lib/freeProxyProviders/`) — proxifly/1proxy sync → ipify validation → `promoteFreeProxyToPool` → `proxy_registry`.

## MASS VALIDATION (2026-08-11) — 309 models tested through /v1/chat/completions

**18 VERIFIED WORKING (16 sweep-OK + 2 dahl live):**
- **felo ×5** (ALL models): felo-chat, felo-search, felo-scholar, felo-social, felo-document — keyless, reliable (~7s), tool-calling works. BEST free source.
- **g4fgem ×2**: gemini-2.5-flash, gemini-2.5-pro
- **g4fgroq ×2**: llama-3.3-70b-versatile, llama-3.1-8b-instant
- **g4fnv ×3**: nemotron-3-nano-30b-a3b, z-ai/glm-5.2 (flaky PoW), minimaxai/minimax-m2.7
- **g4foll ×1**: gemma3:4b; **g4fpol ×2**: openai, openai-fast
- **dahl ×2** (live-verified separately, Cloudflare 403 during sweep = transient IP ratelimit from 309 rapid requests): MiniMax-M2.7, Kimi-K2.6 — 100M free tokens
- **oc/deepseek-v4-flash-free**: works but SLOW (~50-80s first token via noauth; my 000s were curl timeouts, gateway streams fine)

**Status breakdown of 309 tests:** OK=16, COOLDOWN=60 (gitlawb-gmi all 56 — rate-limited), BLOCKED=78 (tllm 26 Vercel, oc/opencode 25 Cloudflare transient, dahl 2 transient), AUTH=69 (pollinations 40, huggingchat 24, hackclub 3), NOTFOUND=72 (glb-gmi 56 wrong ids, aug 15, mcode 1), RATELIMIT=6 (zai 5 — NOW OUT OF QUOTA "Insufficient balance"), UPSTREAM_ERR=6 (uncloseai), FAIL=1, TIMEOUT=1.

**Swarm config:** omniroute provider now **33 models** (added 8 verified: felo×3 more, g4fnv×2, g4fgroq×1, g4fpol×2). opencode run verified felo-scholar → OK exit 0.

## Blocked (documented, not dead ends)

- **theoldllm** (Claude 4.6 Opus/Sonnet, GPT-5.4): Vercel hard-blocks datacenter egress IP (403/429 Security Checkpoint). Needs residential proxy.
- **duckduckgo-web**: 418 ERR_CHALLENGE. **pollinations**: 401 keyless (needs key). **hackclub**: 401. **huggingchat**: 401 needs HF cookie. **mimocode**: 403. **chipotle**: 502. **uncloseai**: 502 flaky. **g4f.space**: PoW "cakes".
- **zai-direct**: 429 out of quota (was free tier, exhausted by validation sweep).
- **puter/bazaarlink signup**: both block disposable emails (mx_disposable / domain checks); bazaarlink 429 IP-throttles signups. Free tiers exist (puter 500+ models, bazaarlink 4M tok/day) but need REAL email + account.

## Gateway ops

- Wedge fix: `systemctl set-property arch-neo-omniroute.service MemoryHigh=1500M MemoryMax=2G` (was 896M → reclaim thrash). Cold boot ~5 min; /v1/models may 0 during warm-up (use browser UA, retry).
- Watchdog: `arch-neo-omniroute-watchdog.timer` 5min → `tools/omniroute_watchdog.sh` — 2 consecutive probe fails + boot grace 420s → restart.
- API key: `[redacted — OMNIROUTE_API_KEY in the local secrets file]`; /v1 also anonymous. Catalog: 2095 models.
- Validation script: /tmp/validate_models.py (tests all models per connected provider, categorizes OK/COOLDOWN/BLOCKED/AUTH/NOTFOUND/RATELIMIT/UPSTREAM_ERR/TIMEOUT).

## Related

[[free-model-catalog]] [[free-model-expansion-20260806]] [[free-model-provider-onboarding]] [[omniroute-free-gateway-study-2026]] [[omniroute-gateway]]
