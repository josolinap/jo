# Jo Web GUI (GitHub Pages)

Polished chat interface for Jo, served from `gui/`.

## Backend integration

This GUI talks to **your Jo web backend** (`server/app.py`), not a third-party service.

- **Hosted (recommended):** `.github/workflows/web-backend.yml` starts OmniRoute + backend, creates a tunnel, writes `gui/backend.json`, and deploys the GUI to GitHub Pages with auto-discovered API base.
- **Local test:** run `python -m uvicorn server.app:app --host 127.0.0.1 --port 8000` (repo root), serve/open `gui/`, and open **Settings** to set the API base URL to `http://127.0.0.1:8000` if not auto-discovered.
- Check `GET <API_BASE>/health` — sidebar/header show reachability, effective provider/model, OmniRoute status, and model probe/readiness hints when available.

For real AI replies, run/configure **OmniRoute** as the model source on the backend (see `../server/README.md` and `../.env.example`).

## Features

- **Settings modal:** API base auto-discovery/manual override, connection/health/readiness + model probe status, model selection (search + refresh), theme toggle, clear saved API base, export/import chats, copy diagnostics
- **Model selection:** selectable model via `GET /v1/models` (auto + backend-discovered OmniRoute models). In hosted/GitHub Actions environments some **`auto/*` route aliases** (e.g. `auto/coding:free`) may resolve to upstream providers that require a browser runtime and can fail; the backend may attempt fallbacks in that case. **Explicit concrete model IDs** fail explicitly if unusable. Prefer **Auto** or a concrete discovered model when you want maximum reliability.
- **Chat UX:** streaming responses, multi-session local history/search/rename/delete, regenerate/edit-resend, copy, markdown + code blocks, timestamps, scroll-to-bottom, reconnect/status awareness
- **Connection awareness:** auto-discovery via `./backend.json`, live status indicators, stale-backend warnings, mobile/desktop responsive layout with sidebar drawer

## Backend contract

- `POST /v1/chat` `{ "message", "history"?, "session_id"?, "model"? }` → `{ "response", "session_id", "provider", "model", "elapsed_ms" }`
- `POST /v1/chat/stream` (SSE `delta`/`done`/`error`)
- `GET /health`, `GET /v1/status`, `GET /v1/models`

## GitHub workflows

- `web-backend.yml`: **deploys Pages + live backend** (owns `gui/backend.json` and Pages environment `pages-api`) — primary path when leveraging GitHub for the web app
- `pages.yml`: validates static GUI/assets on PRs/pushes (no Pages deploy) to avoid overwriting backend-integrated deployment
