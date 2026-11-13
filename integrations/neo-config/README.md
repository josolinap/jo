# Neo Config Integrations (ported references)

This directory vendors **curated, purpose-driven** references from:
- [`josolinap/neo-config`](https://github.com/josolinap/neo-config) (Neo configuration/knowledge store)
- [`josolinap/arch-neo-config`](https://github.com/josolinap/arch-neo-config) (Arch-Neo autonomous agent config & tooling)

The goal is to **wire useful patterns into Jo** (this repo: Ouroboros agent + GitHub Pages GUI + Actions/tunnel backend) without copying unrelated or unsafe material.

## What is ported and why

| Ported asset | Source | Purpose in Jo |
|---|---|---|
| `neo-config/agent/jo.md` | neo-config | Guardian/supervisor persona reference aligned with Jo’s verification/evidence-first role; informs review/ops behavior and future agent wiring. |
| `neo-config/agent/neo.md` | neo-config | Execution-first Neo agent reference; informs autonomous task execution patterns and constitution-aligned behavior. |
| `arch-neo-config/agent/neo.md` | arch-neo-config | Complementary Neo agent definition (graphify/dual-graph awareness, tool-first habits) for cross-environment consistency. |
| `arch-neo-config/plugins/graphify.js` | arch-neo-config | OpenCode plugin pattern that nudges graph-aware queries before shell exploration; reusable/reference for opencode-based workflows. |
| `arch-neo-config/knowledge/tools/free-model-catalog.md` | arch-neo-config | Reverse-engineered reference for aggregating/verifying/prioritizing free-model sources (OmniRoute + mirrors/benches) — informs Jo backend model discovery, ranking, fallback, and diagnostics. |
| `arch-neo-config/knowledge/infrastructure/omniroute-free-model-mechanism.md` | arch-neo-config | Operational reference on OmniRoute free-model mechanisms, validation behavior, and gateway resilience — informs `server/app.py` routing/status and `web-backend.yml` ops. |
| `docs/PORTING_NOTES.md` | this integration | How these assets map to Jo’s architecture (GUI, `server/app.py`, workflows, `.jo_rules`, `.jo_skills`) and what to adopt next. |

## What is intentionally **not** ported

- Offensive/security-arsenal tooling, exploit chains, malware/backdoor samples, or credential-harvesting material present upstream.
- Host-specific systemd units, machine-local state, secrets, caches, or environment-bound binaries.
- Large knowledge/vault dumps not directly wired into Jo’s runtime.

## How this is wired into Jo

- **Web/backend (OmniRoute-first):** Jo’s `server/app.py` and `.github/workflows/web-backend.yml` already implement OmniRoute-prioritized routing with fallbacks and discoverable `gui/backend.json`; upstream Neo configs reinforce the same “OmniRoute primary, resilient fallbacks” strategy.
- **GUI:** `gui/` consumes `/health`, `/v1/status`, `/v1/models`, `/v1/chat`, `/v1/chat/stream`, auto-discovers `backend.json`, and surfaces provider/model/latency + degraded states.
- **Agent guidance:** see `docs/PORTING_NOTES.md` for recommended adoption into `.jo_rules/`, `.jo_skills/`, and operator runbooks.
- **Provenance:** see `SOURCES.md`.

## Maintenance

- Treat this as a **curated snapshot/reference**. When upstream changes materially (agent protocols, OmniRoute behavior, verified-safe plugins), re-port the specific files and update `SOURCES.md`.
- Prefer wiring via docs/rules/skills or small adapters over bulk vendoring.
