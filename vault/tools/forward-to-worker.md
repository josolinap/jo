# forward_to_worker

**Type:** Tool
**Category:** See system_map

## Description

Forward a message to a running worker task's mailbox. Use when the owner sends a message during your active conversation that is relevant to a specific running background task. The worker will see it as [Owner message during task] on its next LLM round.

## Parameters

- `task_id` (string): ID of the running task to forward to
- `message` (string): Message text to forward

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_
