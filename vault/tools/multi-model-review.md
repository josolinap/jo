---
title: multi_model_review
created: 2026-03-25
category: tools
tags:  []

---

# multi_model_review

**Type:** Tool
**Category:** See system_map

## Description

Send code or text to multiple LLM models for review/consensus. Each model reviews independently. Returns structured verdicts. Choose diverse models yourself. Budget is tracked automatically.

## Parameters

- `content` (string): The code or text to review
- `prompt` (string): Review instructions — what to check for. Fully specified by the LLM at call time.
- `models` (array): OpenRouter model identifiers to query (e.g. 3 diverse models for good coverage)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[enable_tools]]
