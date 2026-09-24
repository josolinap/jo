# Jo + OpenAI hybrid migration

This branch keeps Jo's existing supervisor, Ouroboros loop, memory, vault,
Git evolution system, and Python ToolRegistry. OpenAI is added as a first-class
model provider without replacing the working runtime.

## Model provider

Set:

LLM_PROVIDER=openai
OPENAI_API_KEY=<key>
OPENAI_MODEL=gpt-5.6-sol
OPENAI_MODEL_CODE=gpt-5.6-sol
OPENAI_MODEL_LIGHT=gpt-5.6-luna

Jo's existing provider choices remain available. Do not remove the OpenRouter,
NVIDIA, Doubleword, or local configuration until the OpenAI path has passed a
real runtime test.

## MCP

The next migration layer is an authenticated remote MCP gateway over Jo's
existing ToolRegistry. It should expose read-only tools first, then mutating
tools only after explicit deployment configuration.

Do not expose Jo's raw shell, repository push, restart, credential, or
self-evolution controls to an internet-facing endpoint by default.

## 24/7 operation

ChatGPT is the human-facing control plane. Jo's supervisor remains the
persistent runtime. The two must not depend on the same process staying alive.

Target:

ChatGPT -> MCP gateway -> Jo tools
                         |
                         +-> supervisor
                         +-> memory/vault
                         +-> Git/evolution
                         +-> external plugins

## Deployment sequence

1. Configure OPENAI_API_KEY on the Jo host.
2. Run the normal Jo test suite with LLM_PROVIDER=openai.
3. Run one real task using the existing tool loop.
4. Enable the MCP gateway in read-only mode.
5. Connect ChatGPT to the authenticated remote MCP endpoint.
6. Verify tool discovery and audit logging.
7. Enable selected write tools.
8. Only then enable unattended evolution.

## Secrets

Never commit API keys or MCP bearer tokens. Use the existing Colab secret
mechanism, environment variables, or the deployment secret manager.

## Rollback

Set LLM_PROVIDER back to openrouter (or another existing provider) and restart
Jo. The existing runtime remains intact.
