# Jo Web Chat Backend

HTTP backend for the GitHub Pages GUI (`gui/`).

## Endpoints
- `POST /v1/chat` `{ "message": "...", "history"?: [{"role","content"}], "session_id"?: "..." }` → `{ "response", "session_id", "provider", "model" }`
- `POST /v1/chat/stream` same body → SSE events (`delta`, `done`, `error`)
- `GET /health` / `GET /v1/status` → provider/model/config status

CORS is enabled for the web GUI.

## Run locally
```bash
pip install -r ../requirements.txt  # or ensure fastapi uvicorn openai pydantic requests
python -m uvicorn server.app:app --host 127.0.0.1 --port 8000
```
Then set the GUI **Backend → API base URL** to `http://127.0.0.1:8000` (or your deployed URL).

## Enable real replies (free providers)
Configure env vars and restart (see `.env.example`). The LLM stack (`ouroboros/llm.py`) supports OpenRouter `:free` models, NVIDIA NIM, Doubleword, and local Ollama with fallback. Keep `:free` suffixes and resolve models from env (see `.jo_rules/free_models.md`).

Without a configured provider the backend still responds with a clear setup/status message so the GUI remains functional.

## Full agent workflow
Set `JO_WEB_USE_AGENT=1` to route chat through the direct-chat agent path (`supervisor.workers._get_chat_agent` → `agent.handle_task`). Default is the lighter LLM path for robustness.
