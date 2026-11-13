# Porting notes: wiring neo-config / arch-neo-config into Jo

## Jo architecture (what we have)

- **GUI (static, GitHub Pages):** `gui/` — chat UI with settings, searchable/grouped model picker, streaming, local sessions, export/import, reconnect/auto-discovery via `./backend.json`, health/status/model diagnostics.
- **Backend (ephemeral, Actions-hosted):** `server/app.py` (FastAPI) — `/health`, `/v1/status`, `/v1/models`, `/v1/chat`, `/v1/chat/stream`; OmniRoute-prioritized strategy with discovery/ranking, explicit model preference, multi-layer fallbacks, bad-response filtering, provider/model/latency metadata.
- **Live deploy owner:** `.github/workflows/web-backend.yml` — starts OmniRoute + local llama.cpp fallback + uvicorn + tunnel, writes `gui/backend.json` (with metadata), deploys `gui/` to Pages, runs smoke/summary (incl. chat probe), keeps alive. `pages.yml` validates GUI only.
- **Agent/bot:** `.github/workflows/run.yml` and Ouroboros/supervisor runtime (separate concern from web GUI/backend).

## How upstream assets map to purpose

1. **Agent personas (neo-config / arch-neo-config `agent/*.md`)**
   - *Purpose:* consistent guardian/executor roles (evidence-first verification, execution discipline).
   - *Wiring:* keep as curated references in `integrations/neo-config/**/agent/`; selectively reflect compatible guidance in `.jo_rules/`, `.jo_skills/`, or operator prompts without overriding Jo/Ouroboros-specific safety and repo rules.

2. **OmniRoute-first operations**
   - *Purpose:* reliable, free-first routing with fallbacks.
   - *Wiring:* already implemented in `server/app.py` and `web-backend.yml`. Upstream configs reinforce: keep OmniRoute primary, surface reachability/model availability in `/v1/status` & UI, preserve fallback transparency and smoke checks.

3. **OpenCode plugins/tools (e.g. arch-neo `graphify.js`)**
   - *Purpose:* nudge better codebase exploration when a knowledge graph exists.
   - *Wiring:* reference plugin stored at `integrations/neo-config/arch-neo-config/plugins/graphify.js`; can be adopted into `.opencode/plugins/` in environments that use opencode + graphify outputs.

4. **Operational resilience patterns**
   - *Purpose:* stability on ephemeral infra.
   - *Wiring:* `backend.json` discovery+metadata, polling/reconnect, workflow smoke summaries, and (future) persistent backend/self-hosted runner with Actions+tunnel fallback.

5. **Free-model catalog & OmniRoute mechanism knowledge (`arch-neo-config/knowledge/*`)**
   - *Purpose:* reverse-engineered patterns for multi-source free-model aggregation, verification, bench/smart picking, cooldown/rotation, and OmniRoute gateway behavior.
   - *Wiring (implemented):* informs and is partially wired into `server/app.py` (`/v1/status` and `/health` expose `reasons`/`fallback_active`; `/v1/models` includes recommendation metadata), `gui/` diagnostics/status UX (copy-diagnostics, discovered-backend age/staleness hints, readiness/fallback reason surfacing), and `web-backend.yml` smoke/summary (local/OmniRoute reachability, fallback active, readiness reasons) while preserving OmniRoute-first + fallback behavior.

6. **Additional arch-neo commands & guardian/routing knowledge (`arch-neo-config/command/*`, `knowledge/infrastructure/*`, `knowledge/tools/*`)**
   - *Purpose:* curated references for guardian/verification workflows (Jo/duality concepts), critique loops, multi-model dispatch, confidence-based model cascading, and OmniRoute master-orchestrator/egress lessons.
   - *Wiring:* provenance-tracked references to guide safe adaptation into Jo’s `.jo_rules`/`.jo_skills`, backend routing/fallback heuristics, and CI/ops practices (without importing arch/system-specific or sensitive tooling). Currently ported: `command/{jo,openmodel,critic-loop,fork-eval}.md`, `knowledge/tools/confidence-model-cascading-p0-4.md`, `knowledge/infrastructure/{omniroute-master-orchestrator,jo-guardian-system}.md`.

## Recommended next wiring steps (safe, high-value)

- Add a `.jo_rules/` note aligning guardian/review behavior with the ported Jo persona (evidence, read-only verification, concise verdicts) where it fits Ouroboros workflows.
- If using opencode locally for this repo, copy/adapt `graphify.js` into `.opencode/plugins/` and generate `graphify-out/` as needed.
- Continue incremental catalog/mechanism adoption: enrich `/v1/models` with source/verification hints where observable, and further tune GUI/status presentation of readiness/fallback reasons.
- Keep OmniRoute/fallback observability first-class: maintain smoke probes, status fields, and UI degraded indicators.
- Periodically re-port only materially improved, non-sensitive upstream assets and update `SOURCES.md`.
