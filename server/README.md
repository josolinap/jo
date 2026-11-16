# Jo Web Chat Backend

HTTP backend for the GitHub Pages GUI (`gui/`).

## Endpoints

- `POST /v1/chat` `{ "message": "...", "history"?: [{"role","content"}], "session_id"?: "...", "model"?: "..." }` → `{ "response", "session_id", "provider", "model", "elapsed_ms" }`
- `POST /v1/chat/stream` same body → SSE events (`delta`, `done`, `error`)
- `GET /health` / `GET /v1/status` → provider/model/config + OmniRoute reachability/status, model probe results, and readiness reasons
- `GET /v1/models` → discovered/selectable models exposed by this backend (OmniRoute-derived; see policy below)

CORS is enabled for the web GUI.

## Provider mode (OmniRoute-only)

`server/app.py` is configured for **OmniRoute-only** generation:

1. **OmniRoute** (`OMNIROUTE_BASE_URL`) is the sole model source/gateway (`OMNIROUTE_MODEL=auto` by default).
2. Available models are discovered from OmniRoute `/v1/models` when possible.
3. Local/direct/public provider fallbacks are **not** used by this backend.

`/health` and `/v1/status` report OmniRoute reachability, discovered model counts/samples, selected/default model, probe results, and readiness reasons so the GUI can show real status.

## Model listing policy (`GET /v1/models`, web UI)

To keep the hosted experience reliable, the backend intentionally exposes a **curated subset**:

- Always includes `auto` (recommended).
- Includes **discovered OmniRoute models** that are classified as **free by heuristic** (e.g. `:free` suffix, zero-cost pricing metadata, or free tags when present).
- **Excludes** routes known to be unusable in headless/CI-hosted environments, including routes starting with `cfp/` or `dva/` and any model metadata mentioning `playwright`, `cloudflare playground`, or “Devin agentic bridge”.
- Attachments may include cached probe metadata per model when available (best-effort, for UI/debugging).

This means the UI may show fewer models than OmniRoute exposes overall. If you need a different policy, change the backend logic explicitly (do not assume the upstream OmniRoute catalog is mirrored 1:1).

## Hosted (GitHub Actions) notes (important)

- The web backend runs behind an **ephemeral Cloudflare tunnel** with a keep-alive job; availability depends on the active `Web Backend (Pages API)` run and a fresh published `gui/backend.json`.
- OmniRoute runs **headless** in CI. Some upstream OmniRoute routes can resolve to providers that require a browser/runtime (Playwright/Chromium, Cloudflare Playground, Devin bridge). These are **skipped** for safety; if a user explicitly selects such a route, requests will report an error explaining why.
- **Auto-route aliases** like `auto/coding:free`, `auto/best-*`, etc. may resolve to unusable upstreams in this environment. The backend will try the selected alias once, then **fall back to working concrete/discovered models** when appropriate. **Explicit concrete model IDs** keep strict semantics (no silent fallback) so failures are explicit.
- Default recommendation: use **Auto** or pick a concrete discovered model from the refreshed list when possible.

## Run locally

```bash
pip install -r requirements.txt
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```

Then set the GUI **Backend → API base URL** to `http://127.0.0.1:8000` (or your deployed URL).

## Enable real replies (OmniRoute)

Configure env vars and restart (see `.env.example`):

```bash
LLM_PROVIDER=omniroute
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_MODEL=auto
OMNIROUTE_API_KEY=omniroute-local
```

If OmniRoute is unreachable or has no working upstream provider/model, the backend remains reachable but chat responses will return a clear OmniRoute-only setup/status message (including guidance if an explicit selection failed).

## Full agent workflow

Set `JO_WEB_USE_AGENT=1` to route chat through the direct-chat agent path (`supervisor.workers._get_chat_agent` → `agent.handle_task`). Default is the lighter LLM path for robustness and OmniRoute-only behavior.
