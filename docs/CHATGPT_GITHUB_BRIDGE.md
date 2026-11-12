# ChatGPT -> Jo over GitHub Actions

Jo currently runs on free GitHub-hosted Actions. Public repositories can use
standard GitHub-hosted runners free and unlimited, so this design keeps the
runtime within the user's free-only requirement.

## How ChatGPT talks to Jo

There is no permanent MCP HTTP server on the Actions runner. GitHub-hosted
runners are ephemeral VMs that are decommissioned when a job ends, so hosting a
persistent MCP endpoint there would be the wrong fit.

Instead, GitHub Issues become the control bus:

1. ChatGPT creates an issue in this repository with a title starting with [JO].
2. The issue body is the task.
3. Jo's Actions runner polls open issues roughly every 30 seconds.
4. Jo validates that the issue author is an allowed GitHub user.
5. Jo executes the task through the existing supervisor and tool loop.
6. Jo comments the result on the issue.
7. Jo closes the issue.

Example:

Title: [JO] inspect the latest workflow failures and explain the root cause
Body: Look at the last failed Actions run, inspect the logs, and summarize
what should be fixed.

## Why this works with the free deployment

No OpenAI API key is required for the bridge.

No permanent server, VPS, tunnel, paid plugin, or external inference API is
introduced.

GitHub's standard hosted runners are free for public repositories. Scheduled
workflows can run as frequently as every five minutes, while the current Jo
workflow also has a self-restart path.

## What ChatGPT can do

Using the GitHub connection, ChatGPT can create a [JO] issue to give Jo a
task, read the completed result, and continue the conversation.

This makes GitHub behave as Jo's durable mailbox and audit trail.

## Security

Only users listed in JO_GITHUB_ALLOWED_USERS are accepted. The workflow sets
the default to the repository owner.

The mailbox does not expose an HTTP endpoint to the public internet.

The existing Jo tool permissions and protected-file/evolution controls remain
in force.

## Limitation

This gives ChatGPT <-> Jo communication, but it does not make a ChatGPT
conversation itself an always-running model process. Jo can stay alive and do
deterministic/background work on GitHub Actions; model-driven unattended work
still depends on a model execution service.

For the user's free-only requirement, the practical model-driven interaction
is therefore initiated from ChatGPT through the GitHub mailbox.