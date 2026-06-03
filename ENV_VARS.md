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
| `OUROBOROS_DETERMINISTIC` | `1` to disable spice, learning, fallback, auto-model-select, self-reflection, memory extraction | `1` |
| `OUROBOROS_LLM_TEMPERATURE` | LLM temperature (0 = deterministic) | `0.0` |
| `OUROBOROS_TOOL_LEARNING` | `1` to enable temporal tool learning | `1` |

## 🔑 API Keys

| Variable | Purpose |
|----------|---------|
| `OPENROUTER_API_KEY` | Required for OpenRouter (cloud) models |
| `DOUBLEWORD_API_KEY` | Doubleword.ai key for efficient model pool fallback |
| `NVIDIA_API_KEY` | NVIDIA NIM key for free-tier fallback |
| `LOCAL_BASE_URL` | Local Ollama endpoint (default: `http://localhost:11434/v1`) |
| `LOCAL_API_KEY` | Local API key (default: `EMPTY`) |

## 🧠 Provider Selection

| Variable | Values | Default |
|----------|--------|---------|
| `LLM_PROVIDER` | `openrouter`, `doubleword`, `nvidia`, or `local` | `openrouter` |
| `DOUBLEWORD_BASE_URL` | Any OpenAI-compatible endpoint | `https://api.doubleword.ai/v1` |
| `DOUBLEWORD_MODEL` | Default model ID for Doubleword | `deepseek-ai/DeepSeek-V4-Flash` |
| `DOUBLEWORD_FALLBACK_MODEL` | First candidate in Doubleword fallback pool | empty |
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
OUROBOROS_DETERMINISTIC=1
OUROBOROS_LLM_TEMPERATURE=0
```
