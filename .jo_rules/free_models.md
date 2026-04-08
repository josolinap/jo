# Free-Model Rules

- **Never reference a paid model by name** in code or prompts (e.g., `anthropic/claude-*`, `openai/gpt-4*`).
- **Always resolve model from `OUROBOROS_MODEL` env var** or `llm.default_model()` — never hardcode.
- **For lightweight sub-tasks** (reflection, summarization, critique), use `active_model` (already in scope in loop.py).
- **Fallback models** must be set in `OUROBOROS_MODEL_FALLBACK_LIST` env var, not hardcoded in code.
- **Free models** on OpenRouter typically end with `:free` suffix — do not strip or modify these suffixes.
