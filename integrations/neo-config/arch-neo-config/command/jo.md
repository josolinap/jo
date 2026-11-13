---
command: jo
description: "Toggle Jo — Neo's guardian/supervisor ego. When on, every turn emits a [[JO]] guardian channel before [[NEO]], and the duality-enforcer plugin validates each turn (exit 0 compliant / 1 violation / 2 disabled). Jo is read-only and always-on by default (subconscious mode)."
params:
  - name: action
    description: "on | off | status — enable, disable, or show guardian state"
    required: false
---

# /jo — Jo Guardian Toggle

**Plugin-level: executes directly, no LLM involved.**

```
/jo on        # Enable Jo guardian (writes duality/jo_state.json enabled=true)
/jo off       # Disable Jo guardian (enabled=false)
/jo status    # Show current guardian state
```

## What Jo does

- **Every turn** — emits `[[JO]]` (verdict + ledger) before `[[NEO]]`
- **Every turn** — the `duality-enforcer` plugin runs
  `jo_enforcer.py --compliance --json` on the assistant output:
  - `exit 0` compliant, `exit 1` violation, `exit 2` disabled
- **System guard** — the `guardian` cycle (every 10 min) sweeps config drift,
  service health, and coherence; writes `state/guardian_report.json`
- **Trackers** — `jo_loop.py` flags stuck patterns; `jo_redirects.py` follows
  up outstanding REDIRECTs (both advisory, never block)

## Under the hood

```bash
python3 ~/.opencode/duality/jo_bootstrap.py [--on|--off|--status]
python3 ~/.opencode/duality/jo_enforcer.py --self-test
```

State file: `~/.opencode/duality/jo_state.json` (`always_on: true,
mode: subconscious` by default — Jo is engaged at session start and never
disengages unless explicitly turned off).
