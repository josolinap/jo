# Jo Web Chat Backend

HTTP backend for the GitHub Pages GUI (`gui/`).

## Endpoints
- `POST /v1/chat` `{ "message": "...", "history"?: [{"role","content"}], "session_id"?: "...", "model"?: "..." }` → `{ "response", "session_id", "provider", "model", "elapsed_ms" }`
- `POST /v1/chat/stream` same body → SSE events (`delta`, `done`, `error`)
- `GET /health` / `GET /v1/status` → provider/model/config + OmniRoute reachability/status
- `GET /v1/models` → discovered/selectable models (OmniRoute)

CORS is enabled for the web GUI.

## Provider mode (OmniRoute-only)
`server/app.py` is configured for **OmniRoute-only** generation:

1. **OmniRoute** (`OMNIROUTE_BASE_URL`) is the sole model source/gateway (`OMNIROUTE_MODEL=auto` by default).
2. Available models are discovered from OmniRoute `/v1/models` when possible.
3. Local/direct/public provider fallbacks are not used by this backend.

`/health` and `/v1/status` report OmniRoute reachability, discovered model counts/samples, selected model, and readiness reasons so the GUI can show real status.

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

If OmniRoute is unreachable or has no working upstream provider/model, the backend remains reachable but chat responses will return a clear OmniRoute-only setup/status message.

## Full agent workflow
Set `JO_WEB_USE_AGENT=1` to route chat through the direct-chat agent path (`supervisor.workers._get_chat_agent` → `agent.handle_task`). Default is the lighter LLM path for robustness and OmniRoute-only behavior.
