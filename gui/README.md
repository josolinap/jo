# Jo Web GUI (GitHub Pages)

Static Nod-inspired chat interface for Jo, deployed from `gui/` to GitHub Pages.

## Features
- Configurable backend (sidebar **Backend → API base URL**, persisted)
- Streaming chat (`/v1/chat/stream`) with fallback to `/v1/chat`
- Multi-session local history, stop/copy, markdown rendering, light/dark theme
- Backend health/model/status display

## Backend contract
- `POST /v1/chat` `{ "message", "history"?, "session_id"? }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` (SSE `delta`/`done`)
- `GET /health`

Run/deploy `server/app.py` (see `../server/README.md`), configure a free provider env (`LLM_PROVIDER`, `OUROBOROS_MODEL`, keys or local Ollama), and point the GUI to that backend. Without a configured provider the backend returns a functional status/setup message.

## Local preview
Open `index.html` in a browser or serve the folder, e.g. `python -m http.server 8080` from `gui/`, then set API base to your backend.
