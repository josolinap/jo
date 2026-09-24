# ChatGPT + Jo: MCP-first, free-only architecture

## Important distinction

Jo cannot use the model running inside this conversation as a private,
unattended inference API. A ChatGPT conversation is not a service endpoint
that an external daemon can continuously call.

Instead, the free-first architecture is:

ChatGPT
  -> Jo MCP app
  -> existing Jo ToolRegistry
  -> supervisor / memory / vault / Git / external systems

ChatGPT supplies the intelligence interactively. Jo supplies the persistent
tools and runtime state.

OpenAI's current ChatGPT developer mode supports custom remote MCP apps.
ChatGPT connects to the MCP server's remote endpoint and can call its tools.
Full write/modify MCP is currently limited to Business and Enterprise/Edu,
while Pro supports MCP with read/fetch permissions. Check the current
ChatGPT plan/rollout before deployment.

## No OpenAI API dependency

This architecture intentionally does not require OPENAI_API_KEY in Jo.

The key may exist in your environment, but Jo does not use it for model
inference in this design.

## Free-only policy

JO_FREE_ONLY=1 should remain the default policy for all unattended work.

No paid model endpoint, paid plugin, or paid API should be enabled silently.
When an integration requires payment, stop and ask the owner.

## MCP gateway

Run:

python -m ouroboros.chatgpt_mcp

Environment:

JO_MCP_REPO_DIR=/path/to/jo
JO_MCP_DATA_ROOT=/path/to/jo-data
JO_MCP_HOST=127.0.0.1
JO_MCP_PORT=8000
JO_MCP_AUTH_TOKEN=<random-long-secret>
JO_MCP_ALLOW_ANONYMOUS=0
JO_MCP_ALLOW_WRITE=0

The endpoint is:

https://<public-or-tunnel-host>/mcp

Read-only tools are exposed by default. Mutating tools require
JO_MCP_ALLOW_WRITE=1 or an explicit JO_MCP_TOOL_ALLOWLIST.

## 24/7 behavior

The MCP process is not the 24/7 brain.

The Jo supervisor remains responsible for:
- worker lifecycle
- task queue
- scheduled jobs
- background consciousness
- memory/vault
- Git evolution
- health checks
- restart/rollback

When ChatGPT is actively connected, it can inspect and operate Jo through MCP.
For fully unattended model-driven work, a model execution service is still
required; ChatGPT itself cannot be repurposed as an external inference daemon.

## Recommended next step

Connect this MCP endpoint to ChatGPT Developer Mode / custom Apps.

For private infrastructure, use a supported secure tunnel instead of exposing
Jo's MCP endpoint directly to the public internet.
