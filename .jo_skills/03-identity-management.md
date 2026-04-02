# Identity Management Protocol

## Single Source of Truth

Identity is stored in: memory/identity.md

## Rules

1. **Never assume identity details** - Only what's written in identity.md
2. **Check staleness** - If identity.md is >24h old, mention it needs refresh
3. **No fabrication** - Don't invent personality traits, preferences, or history

## Identity Refresh

When identity.md is stale:
1. Say "My identity file is X hours old and may need refresh"
2. Ask permission before modifying
3. Use update_identity tool, not direct file edits

## What Identity Contains

- Core principles from BIBLE.md
- Current focus and capabilities
- Technical state (modules, tests, etc.)

## What Identity Does NOT Contain

- User's personal details beyond owner_id
- Telegram usernames or display names
- Real-time system metrics (check those live)
