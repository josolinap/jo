# Jo Web GUI (GitHub Pages)

Static Nod-inspired chat interface for Jo, deployed from `gui/` to GitHub Pages by `.github/workflows/pages.yml`.

## Setup (our own backend)
This GUI talks to **your Jo web backend** (`server/app.py`), not a third-party service.

- **Hosted Pages:** deploy `server.app:app` to a reachable **HTTPS** endpoint, then set sidebar **Backend → API base URL** to it.
- **Local test:** run `python -m uvicorn server.app:app --host 127.0.0.1 --port 8000` (from repo root) and open/serve `gui/`, then set API base to `http://127.0.0.1:8000`.
- Check `GET <API_BASE>/health` — the sidebar shows online/reachable/model status.

For real AI replies, configure a free provider on the backend (`LLM_PROVIDER`, `OUROBOROS_MODEL` + keys or local Ollama; see `../server/README.md`).

## Features
- Configurable backend URL (persisted), streaming chat (`/v1/chat/stream`) with fallback to `/v1/chat`
- Multi-session local history (with history sent to backend), stop/copy, markdown rendering, light/dark theme
- Backend health/model/status display and connection diagnostics

## Backend contract
- `POST /v1/chat` `{ "message", "history"?, "session_id"? }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` (SSE `delta`/`done`)
- `GET /health`
