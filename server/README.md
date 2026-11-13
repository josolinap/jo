# Jo Web Chat Backend

HTTP backend for the GitHub Pages GUI (`gui/`).

## Endpoints
- `POST /v1/chat` `{ "message": "...", "history"?: [{"role","content"}], "session_id"?: "..." }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` same body → SSE events (`delta`, `done`, `error`)
- `GET /health` / `GET /v1/status` → provider/model/config + reachability status

CORS is enabled for the web GUI.

## Provider priority (web chat)
`server/app.py` is optimized for GitHub-hosted web chat and **prioritizes OmniRoute** as the main source while keeping fallbacks so responses stay reliable:

1. **OmniRoute** (`OMNIROUTE_BASE_URL`) — **primary** gateway for routed/free/connected models (`OMNIROUTE_MODEL=auto` by default). Reachability is probed, but the server **still attempts OmniRoute** even if the probe is flaky; available models are auto-discovered from `/v1/models` when possible.
2. **Local OpenAI-compatible server** (`LOCAL_BASE_URL`, e.g. Ollama/llama.cpp)
3. **Direct provider fallbacks** via Jo LLM stack/keys (OpenRouter, NVIDIA NIM, Doubleword) as safety nets if upstream paths fail
4. **Public free fallback endpoints** (best-effort, no key)

Bad/quota/HTML provider responses are filtered so they are not returned as real replies. `/health` reports effective `provider`/`model`, `omniroute_reachable`, `local_reachable`, and key/config flags so the GUI can show real status.

## Run locally
```bash
pip install -r requirements.txt
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```
Then set the GUI **Backend → API base URL** to `http://127.0.0.1:8000` (or your deployed URL).

## Enable real replies (recommended: OmniRoute)
Configure env vars and restart (see `.env.example`):

```bash
LLM_PROVIDER=omniroute
OMNIROUTE_BASE_URL=http://127.0.0.1:20128/v1
OMNIROUTE_MODEL=auto
OMNIROUTE_API_KEY=omniroute-local
```

Keep local/direct provider keys configured as fallbacks where possible.

Without a configured/reachable provider the backend still responds with a clear setup/status message so the GUI remains functional.

## Full agent workflow
Set `JO_WEB_USE_AGENT=1` to route chat through the direct-chat agent path (`supervisor.workers._get_chat_agent` → `agent.handle_task`). Default is the lighter LLM path for robustness and OmniRoute-first behavior.
