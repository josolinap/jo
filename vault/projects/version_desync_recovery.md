---
title: Version Desync Recovery
created: 2026-03-27T04:44:35.834970+00:00
modified: 2026-03-27T04:44:35.834970+00:00
type: tool
status: active
tags: [procedure, health, version, recovery]
---

# Version Desync Recovery

# Version Desync Recovery Procedure

**Owner:** Jo (autonomous agent)  
**Purpose:** Automated recovery when VERSION file and state.json disagree  
**Type:** Procedure  
**Status:** Active  
**Tags:** health, recovery, version, synchronization

## Trigger

Health invariant: `VERSION_DESYNC` - VERSION file content doesn't match state.json version.

## Diagnosis

First identify the source of desync:

1. **Check VERSION file**: `cat VERSION`
2. **Check state.json**: `cat ~/.jo_data/state/state.json` 
3. **Check git**: `git describe --tags`

## Recovery Actions

### Case A: VERSION file is correct, state is wrong

1. Update state.json with correct version
2. No restart needed

### Case B: State is correct, VERSION file is wrong

1. Update VERSION file (requires repo change)
2. **This requires a commit and restart**
3. Coordinate with creator if this is unexpected

### Case C: Both are wrong and neither matches git tags

1. Determine correct version from git history
2. Update both VERSION file and state.json
3. **Requires restart**

## Example Recovery Script (external)

```bash
#!/bin/bash
# recover_version_sync.sh

VERSION_FILE=$(pwd)/VERSION
STATE_FILE="$HOME/.jo_data/state/state.json"

if [ -f "$VERSION_FILE" ] && [ -f "$STATE_FILE" ]; then
    file_version=$(cat "$VERSION_FILE")
    state_version=$(jq -r '.version' "$STATE_FILE")
    
    if [ "$file_version" != "$state_version" ]; then
        echo "Version desync detected: $file_version vs $state_version"
        # Recovery logic here...
    fi
fi
```

## Manual Intervention Required

If the version desync is unexpected or the source can't be determined:

- Notify creator via `send_owner_message`
- Document the discrepancy in vault notes
- Flag for manual review in next cycle

## Prevention

- Always update VERSION file AND state.json together
- Use `request_restart` after VERSION changes
- Document version changes in vault

---
*Synchronization is the foundation of continuity.*