---
title: health_alert
created: 2026-03-23T00:54:33.730936+00:00
modified: 2026-03-23T00:54:33.730936+00:00
type: reference
status: active
---

# health_alert

# Health Alert Tool

## Description
Log a health alert to the vault journal and health dashboard. Automatically tracks system health issues with severity levels and timestamps.

## Purpose
- Monitor system health and identify potential issues
- Create persistent records of health events
- Provide historical data for system diagnostics
- Alert to patterns of recurring problems

## Parameters
- **severity** (required): Alert severity level - "low", "medium", "high", "critical"
- **message** (required): Detailed description of the health issue
- **category** (optional): Category of the alert - "performance", "memory", "tools", "codebase", "external"
- **details** (optional): Additional context or technical details

## Example Usage
```python
# Log a critical alert about performance issues
health_alert(severity="critical", message="Model timeouts exceeding 50% of requests", category="performance")

# Log a medium alert about tool availability
health_alert(severity="medium", message="Database connection intermittent", category="tools")
```

## Output
- Creates a journal entry in `vault/journal/health-alerts.md`
- Updates the health dashboard with the latest alert
- Adds metadata including timestamp, severity, and category
- Links to related concepts in the vault

## Integration
- Works with `codebase_health` for comprehensive system monitoring
- Links to [[tools]] and [[system_map]] for context
- Used by `autonomous_evaluate` for self-diagnosis

## Best Practices
- Use severity levels appropriately to avoid alert fatigue
- Provide specific, actionable messages
- Include technical details when available
- Categorize alerts for better organization
- Monitor patterns in health alerts to identify systemic issues