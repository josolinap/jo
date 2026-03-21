# analyze_screenshot

**Type:** Tool
**Category:** See system_map

## Description

Analyze the last browser screenshot using a Vision LLM. Must call browse_page(output='screenshot') or browser_action(action='screenshot') first. Returns a text description and analysis of the screenshot. Use this to verify UI, check for visual errors, or understand page layout.

## Parameters

- `prompt` (string): What to look for or analyze in the screenshot (default: general description)
- `model` (string): VLM model to use (default: current OUROBOROS_MODEL)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_
