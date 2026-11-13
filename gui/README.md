# Jo Web GUI (GitHub Pages)

Polished chat interface for Jo (Claude/ChatGPT-inspired UX), served from `gui/`.

## Backend integration
This GUI talks to **your Jo web backend** (`server/app.py`), not a third-party service.

- **Hosted (recommended):** `.github/workflows/web-backend.yml` starts OmniRoute + backend, creates a tunnel, writes `gui/backend.json`, and deploys the GUI to GitHub Pages with auto-discovered API base.
- **Local test:** run `python -m uvicorn server.app:app --host 127.0.0.1 --port 8000` (repo root), serve/open `gui/`, and open **Settings** to set the API base URL to `http://127.0.0.1:8000` if not auto-discovered.
- Check `GET <API_BASE>/health` — sidebar/header show reachability, effective provider/model, and OmniRoute/local status.

For real AI replies, run/configure **OmniRoute** as the primary source on the backend (see `../server/README.md` and `../.env.example`), with local/direct providers as fallbacks.

## Features
- **Settings modal:** configure API base URL, view connection/health status, choose chat model, toggle theme, clear saved backend URL
- **Model selection:** selectable model (Auto/OmniRoute-first or specific discovered models) via `GET /v1/models`, sent with chat requests
- **Chat UX:** streaming responses with fallback, multi-session local history/search/rename/delete, regenerate/edit-resend, copy, markdown + code blocks, timestamps, scroll-to-bottom, suggestion prompts
- **Connection awareness:** auto-discovery via `./backend.json` (when no saved base), live backend health/provider/model/status indicators, mobile/desktop responsive layout with sidebar drawer

## Backend contract
- `POST /v1/chat` `{ "message", "history"?, "session_id"?, "model"? }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` (SSE `delta`/`done`/`error`)
- `GET /health`, `GET /v1/status`, `GET /v1/models`

## GitHub workflows
- `web-backend.yml`: **deploys Pages + live backend** (owns `gui/backend.json` and Pages environment `pages-api`) — primary path when leveraging GitHub for the web app
- `pages.yml`: validates static GUI/assets on PRs/pushes (no Pages deploy) to avoid overwriting backend-integrated deployment
