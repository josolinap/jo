# Jo Web GUI (GitHub Pages)

Static Nod-inspired chat interface for Jo, served from `gui/`.

## Backend integration
This GUI talks to **your Jo web backend** (`server/app.py`), not a third-party service.

- **Hosted (recommended):** `.github/workflows/web-backend.yml` starts OmniRoute + backend, creates a tunnel, writes `gui/backend.json`, and deploys the GUI to GitHub Pages with auto-discovered API base.
- **Local test:** run `python -m uvicorn server.app:app --host 127.0.0.1 --port 8000` (repo root), serve/open `gui/`, and set **Backend → API base URL** to `http://127.0.0.1:8000` if not auto-discovered.
- Check `GET <API_BASE>/health` — sidebar/header show reachability, effective provider/model, and OmniRoute/local status.

For real AI replies, run/configure **OmniRoute** as the primary source on the backend (see `../server/README.md` and `../.env.example`), with local/direct providers as fallbacks.

## Features
- Configurable backend URL (persisted), auto-discovery via `./backend.json`
- Streaming chat (`/v1/chat/stream`) with fallback to `/v1/chat`
- Multi-session local history (history sent to backend), stop/copy, markdown rendering, light/dark theme
- Backend health/provider/model status display and connection diagnostics

## Backend contract
- `POST /v1/chat` `{ "message", "history"?, "session_id"? }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` (SSE `delta`/`done`/`error`)
- `GET /health`, `GET /v1/status`

## GitHub workflows
- `web-backend.yml`: **deploys Pages + live backend** (owns `gui/backend.json` and Pages environment `pages-api`) — primary path when leveraging GitHub for the web app
- `pages.yml`: validates static GUI/assets on PRs/pushes (no Pages deploy) to avoid overwriting backend-integrated deployment
