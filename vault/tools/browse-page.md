---
title: browse_page
created: 2026-03-25
category: tools
tags:  []

---

# browse_page

**Type:** Tool
**Category:** See system_map

## Description

Open a URL in headless browser. Returns page content as text, html, markdown, or screenshot (base64 PNG). Browser persists across calls within a task. For screenshots: use send_photo tool to deliver the image to owner.

## Parameters

- `url` (string): URL to open
- `output` (string): Output format (default: text)
- `wait_for` (string): CSS selector to wait for before extraction
- `timeout` (integer): Page load timeout in ms (default: 30000)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[tools]] - main tool categorization and architecture
- [[analyze_screenshot]] - analyze browser screenshots
- [[browser_action]] - perform actions on browser pages
- [[web_search]] - search the web for information
- [[web_fetch]] - fetch full content from URLs [[tool_categories]]
