# browser_action

**Type:** Tool
**Category:** See system_map

## Description

Perform action on current browser page. Actions: click (selector), fill (selector + value), select (selector + value), screenshot (base64 PNG), evaluate (JS code in value), scroll (value: up/down/top/bottom).

## Parameters

- `action` (string): Action to perform
- `selector` (string): CSS selector for click/fill/select
- `value` (string): Value for fill/select, JS for evaluate, direction for scroll
- `timeout` (integer): Action timeout in ms (default: 5000)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_
