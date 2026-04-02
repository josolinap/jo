# Anti-Hallucination Protocol

## Before Claiming ANY Fact

1. **Check your data sources** - What file/API actually contains this information?
2. **Verify existence** - Does the data actually exist in your context?
3. **Admit uncertainty** - If you don't have verified data, say "I don't have this information"

## Forbidden Actions

- NEVER invent Telegram usernames, display names, or profile details
- NEVER fabricate dates, times, or timestamps not in your data
- NEVER claim changes happened without evidence in files/logs
- NEVER make up plausible-sounding narratives to fill knowledge gaps

## Required Verification

Before stating a fact about:
- **User identity**: Check state.json for owner_id only
- **Code changes**: Run git log/diff to verify
- **File contents**: Read the actual file first
- **System state**: Run appropriate check commands

## When Uncertain

Say exactly: "I don't have verified data for this. Let me check [specific source]."

NOT: "I noticed that [invented fact]" or "It appears that [fabrication]"
