---
title: simulate_outcome
created: 2026-03-25
category: tools
tags:  []

---

# simulate_outcome

**Type:** Tool
**Category:** See system_map

## Description

Simulate a scenario and predict outcomes BEFORE making changes. Runs SYNCHRONOUSLY - returns results immediately. Does NOT create a background task - do NOT use wait_for_task or get_task_result on this. Use sim_result later to record actual outcomes.

## Parameters

- `scenario` (string): Description of scenario to simulate
- `variables` (string): Optional JSON of variables to consider
- `iterations` (integer): Number of simulation iterations

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[sim_result]]
