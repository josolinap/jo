---
title: vlm_query
created: 2026-03-25
category: tools
tags:  []

---

# vlm_query

**Type:** Tool
**Category:** See system_map

## Description

Analyze any image using a Vision LLM. Provide either image_url (public URL) or image_base64 (base64-encoded PNG/JPEG). Use for: analyzing charts, reading diagrams, understanding screenshots, checking UI.

## Parameters

- `prompt` (string): What to analyze or describe about the image
- `image_url` (string): Public URL of the image to analyze
- `image_base64` (string): Base64-encoded image data
- `image_mime` (string): MIME type for base64 image (default: image/png)
- `model` (string): VLM model to use (default: current OUROBOROS_MODEL)

## Usage

Called automatically when needed. Use `system_map` tool to see full tool list.

## Related

_Add related tools and concepts here_

---
## Related

- [[analyze_screenshot]]
