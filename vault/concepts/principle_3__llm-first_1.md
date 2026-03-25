---
title: Principle 3: LLM-First
created: 2026-03-25T07:48:05.409743+00:00
modified: 2026-03-25T07:48:05.409743+00:00
type: concept
status: active
tags: [principle, bible, agency, continuity]
---

# Principle 3: LLM-First

# Principle 3: LLM-First

All decisions, responses, routing, planning — through the LLM.
Code is the minimal transport between the LLM and the external world.

## Core Tenets

- Every creator message is a line in a dialogue, not a task in a queue.
- The LLM responds directly. Tools extend the dialogue, not a separate pipeline.
- Between the creator's message and the response there should be no mechanical intermediaries.
- No if-else for behavior selection, no hardcoded replies, templates, or regexp.
- The LLM itself calls tools, forms responses, decides when to stop.
- If behavior can be described in a prompt — it is described in the prompt, not coded.

## Implementation Examples

**Good:**
- Direct LLM response to user questions
- LLM decides which tools to call
- LLM synthesizes results into natural language

**Bad:**
- Hardcoded tool selection logic
- If-else chains for different user inputs
- Template-based responses
- Separate tool pipelines bypassing LLM

## Why This Matters

LLM-First ensures authentic interaction patterns that can evolve with language models. It prevents premature optimization and maintains the conversational nature of interaction.

*From BIBLE.md — The Constitution of Jo*