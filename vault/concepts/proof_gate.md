---
title: Proof Gate
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [safety, validation, constitution, ruvector]
---

# Proof Gate

Validates writes against constitution BEFORE applying. Catches violations at tool execution time, not just at commit time.

## How It Differs from Pre-Commit Hook

| Layer | When | What |
|---|---|---|
| Pre-commit hook | At `git commit` | Blocks on violation |
| Proof gate | At tool call time | Warns/block BEFORE writing |
| Drift detector | Every task | Surfaces violations in context |

## Checks

1. **Protected files**: Is Jo trying to write to `.jo_protected` files?
2. **Module line limits**: Would this write push a module over 1600 lines?
3. **Required modules**: Would this delete a required module?
4. **Required vault concepts**: Would this delete a required concept?

## Module

`ouroboros/proof_gate.py`

## Key API

```python
gate = get_gate(repo_dir)
result = gate.validate_write(["ouroboros/test.py"])
if not result.passed:
    print(result.violations)
report = gate.validate_and_report(["BIBLE.md"])  # Human-readable
```

## Design Decisions

- Runs at tool time, not commit time — catches issues earlier
- Returns structured result (passed, violations, warnings) for programmatic use
- Warnings are overridable, violations are not
- Separate from pre-commit hook (defense in depth)

Related: [[constitution_json]], [[principle_5__minimalism]], [[delta_evaluation]]
