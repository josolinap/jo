# Jo Environment Variables Reference

All model and behavior configuration is done via **environment variables** or `.env` secrets.
Jo reads these automatically at startup — no code changes needed.

## 🤖 Model Selection

| Variable | Purpose | Example |
|----------|---------|---------|
| `OUROBOROS_MODEL` | Primary model for all tasks | `google/gemini-2.0-flash-exp:free` |
| `OUROBOROS_MODEL_CODE` | Code-specific model override | `qwen/qwen-2.5-coder-32b-instruct:free` |
| `OUROBOROS_MODEL_LIGHT` | Lightweight model for summaries | `meta-llama/llama-3.3-70b-instruct:free` |
| `OUROBOROS_MODEL_FALLBACK_LIST` | Comma-separated fallback chain | `arcee-ai/trinity-large-preview:free,qwen/qwen-2.5-72b-instruct:free` |

## 🔑 API Keys

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | Required for OpenRouter (cloud) models |
| `LOCAL_BASE_URL` | Local Ollama endpoint (default: `http://localhost:11434/v1`) |
| `LOCAL_API_KEY` | Local API key (default: `EMPTY`) |

## 🧠 Provider Selection

| Variable | Values | Default |
|----------|--------|---------|
| `LLM_PROVIDER` | `openrouter` or `local` | `openrouter` |
| `OUROBOROS_MODEL` | Any model ID | `openrouter/free` |

## 💰 Budget

| Variable | Purpose |
|----------|---------|
| `TOTAL_BUDGET` | Session spending limit in USD |

## ⚙️ Behavior

| Variable | Purpose |
|----------|---------|
| `OUROBOROS_SUPPRESS_PROGRESS` | `true` to hide progress messages |
| `OUROBOROS_SPICE_INTERVAL` | How often personality injections fire (default: `5` rounds) |
| `OUROBOROS_USE_PIPELINE` | `1` to enable structured planning pipeline |

## ✅ Recommended Free Setup

```bash
OPENROUTER_API_KEY=sk-or-...
OUROBOROS_MODEL=google/gemini-2.0-flash-exp:free
OUROBOROS_MODEL_CODE=qwen/qwen-2.5-coder-32b-instruct:free
OUROBOROS_MODEL_LIGHT=meta-llama/llama-3.3-70b-instruct:free
OUROBOROS_MODEL_FALLBACK_LIST=arcee-ai/trinity-large-preview:free,meta-llama/llama-3.3-70b-instruct:free
```
