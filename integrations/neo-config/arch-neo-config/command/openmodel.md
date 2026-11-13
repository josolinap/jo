---
description: "Multi-model AI collab (NIP v3) + hallucination verify — FREE via Z.AI Direct (glm-4.5-flash)."
---

# /openmodel — NIP v3 Collab + Verify

**Wired up.** Routes to `tools/openmodel_dispatch.py` via neo-kit plugin handler.
Supports **free models** via Z.AI Direct (glm-4.5-flash) — no NVIDIA API key needed.

NOTE: vault, memory, code analysis, and web tool subcommands have been removed
from this command. Use the dedicated LLM tools instead:
- `vault_create` / `vault_read` / `vault_search` / `vault_graph`
- `memory_store` / `memory_recall`
- `impact_analysis` / `codebase_scan`
- `websearch` / `webfetch`

## Quick Usage

```
/openmodel "task"                    # NIP v3 collab (auto-detect provider)
/openmodel nip "task"                # Multi-model AI collab (8 GLM models)
/openmodel nip "task" --provider zai-direct  # Use Z.AI Direct (free, default)
/openmodel verify "text"                     # Hallucination check
```

## Model Providers

| Provider | Command | API Key | Cost |
|----------|---------|---------|------|
| **Z.AI Direct** (default) | `--provider zai-direct` | Built-in | Free (glm-4.5-flash) |
| **GLM Bridge** | `--provider glm-bridge` | Built-in | ❌ Tunnel down |

**Auto-detect:** Defaults to Z.AI Direct (glm-4.5-flash free model).

## Implementation

- **Plugin handler**: `/root/.opencode/plugins/neo-kit/index.js` — `command.execute.before`
- **Python dispatch**: `/root/.opencode/tools/openmodel_dispatch.py`
- **Default provider**: `zai-direct` (was `glm-bridge` — tunnel is down since Jul 2026)
