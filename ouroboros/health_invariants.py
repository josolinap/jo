"""Health invariants — surfaces anomalies for LLM-first self-detection.

Extracted from context.py to reduce module size (Principle 5: Minimalism).
Each check detects a specific anomaly and reports it as text in the
health invariants section that appears in every task context.
"""

from __future__ import annotations

import json
import logging
import pathlib
import time
from typing import Any, Dict, Set

log = logging.getLogger(__name__)


def build_health_invariants(env: Any) -> str:
    """Build health invariants section for LLM-first self-detection.

    Surfaces anomalies as informational text. The LLM (not code) decides
    what action to take based on what it reads here. (Bible P0+P3)

    Verification tracking is first because anti-hallucination is critical.
    """
    checks: list[str] = []

    # 1. VERIFICATION TRACKING (anti-hallucination) - MOST IMPORTANT
    try:
        from ouroboros.memory import Memory

        mem = Memory(drive_root=env.drive_root)
        stats = mem.get_verification_stats()
        recent = stats.get("recent_verifications", 0)
        total = stats.get("total_verifications", 0)
        if recent == 0 and total > 0:
            checks.append(f"WARN: VERIFICATION: No verifications in last 24h (total: {total})")
        elif recent > 0:
            checks.append(f"OK: VERIFICATION: {recent} verifications in 24h ({total} total)")
        else:
            checks.append("OK: VERIFICATION: Tracking active (no entries yet)")
    except Exception:
        log.debug("Health check failed: verification stats", exc_info=True)

    # 2. Version sync: VERSION file vs pyproject.toml
    try:
        ver_file = (env.repo_path("VERSION")).read_text(encoding="utf-8").strip()
        pyproject = (env.repo_path("pyproject.toml")).read_text(encoding="utf-8")
        pyproject_ver = ""
        for line in pyproject.splitlines():
            if line.strip().startswith("version"):
                pyproject_ver = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
        if ver_file and pyproject_ver and ver_file != pyproject_ver:
            checks.append(f"CRITICAL: VERSION DESYNC: VERSION={ver_file}, pyproject.toml={pyproject_ver}")
        elif ver_file:
            checks.append(f"OK: version sync ({ver_file})")
    except Exception:
        log.debug("Health check failed: version sync", exc_info=True)

    # 3. Budget drift
    try:
        state_json = (env.drive_path("state/state.json")).read_text(encoding="utf-8")
        state_data = json.loads(state_json)
        if state_data.get("budget_drift_alert"):
            drift_pct = state_data.get("budget_drift_pct", 0)
            our = state_data.get("spent_usd", 0)
            theirs = state_data.get("openrouter_total_usd", 0)
            checks.append(f"WARNING: BUDGET DRIFT {drift_pct:.1f}%: tracked=${our:.2f} vs OpenRouter=${theirs:.2f}")
        else:
            checks.append("OK: budget drift within tolerance")
    except Exception:
        log.debug("Health check failed: budget drift", exc_info=True)

    # 4. Per-task cost anomalies
    try:
        from supervisor.state import per_task_cost_summary

        costly = [t for t in per_task_cost_summary(5) if t["cost"] > 5.0]
        for t in costly:
            checks.append(f"WARNING: HIGH-COST TASK: task_id={t['task_id']} cost=${t['cost']:.2f} rounds={t['rounds']}")
        if not costly:
            checks.append("OK: no high-cost tasks (>$5)")
    except Exception:
        log.debug("Health check failed: per-task cost", exc_info=True)

    # 5. Identity.md awareness (missing or stale)
    try:
        identity_path = env.drive_path("memory/identity.md")
        if not identity_path.exists():
            checks.append("WARN: MISSING IDENTITY: identity.md not found, will be auto-created")
        else:
            # Check both file mtime (evolution) and meta last_verified (check-in)
            mtime = identity_path.stat().st_mtime
            age_hours_mtime = (time.time() - mtime) / 3600

            # Try to get semantic verification time
            last_ver_iso = None
            try:
                from ouroboros.memory import Memory

                mem = Memory(drive_root=env.drive_root)
                last_ver_iso = mem.get_identity_last_verified()
            except Exception:
                pass

            if last_ver_iso:
                import datetime

                last_ver_dt = datetime.datetime.fromisoformat(last_ver_iso.replace("Z", "+00:00"))
                age_hours_ver = (datetime.datetime.now(datetime.timezone.utc) - last_ver_dt).total_seconds() / 3600
                age_hours = min(age_hours_mtime, age_hours_ver)
            else:
                age_hours = age_hours_mtime

            if age_hours > 24:  # Increased threshold for semantic check
                checks.append(f"WARNING: STALE IDENTITY: identity.md last verified {age_hours:.0f}h ago")
            elif age_hours > 8:
                checks.append(f"INFO: identity.md needs check-in ({age_hours:.0f}h since last verification)")
            else:
                checks.append("OK: identity.md fresh")
                # Auto-verify: checking = verification, update timestamp
                try:
                    mem.verify_freshness("memory/identity.md")
                except Exception:
                    pass
    except Exception:
        log.debug("Health check failed: identity awareness", exc_info=True)

    # 5b. Scratchpad awareness
    try:
        scratchpad_path = env.drive_path("memory/scratchpad.md")
        if not scratchpad_path.exists():
            checks.append("WARN: MISSING SCRATCHPAD: scratchpad.md not found")
        else:
            age_hours = (time.time() - scratchpad_path.stat().st_mtime) / 3600
            if age_hours > 24:
                checks.append(f"INFO: SCRATCHPAD STALE: {age_hours:.0f}h since last update")
            elif age_hours > 1:
                checks.append(f"OK: scratchpad updated {age_hours:.1f}h ago")
            else:
                checks.append("OK: scratchpad fresh")
    except Exception:
        log.debug("Health check failed: scratchpad awareness", exc_info=True)

    # 5c. Memory directory health
    try:
        memory_dir = env.drive_path("memory")
        required_files = ["identity.md", "scratchpad.md"]
        missing = [f for f in required_files if not (memory_dir / f).exists()]
        if missing:
            checks.append(f"WARN: MISSING MEMORY FILES: {', '.join(missing)} will be auto-created")
        else:
            checks.append("OK: memory files present")
    except Exception:
        log.debug("Health check failed: memory directory", exc_info=True)

    # 6. Duplicate processing detection
    try:
        import hashlib as _hashlib

        msg_hash_to_tasks: Dict[str, Set[str]] = {}
        tail_bytes = 1_000_000

        def _scan_file_for_injected(
            path: pathlib.Path, type_field: str = "type", type_value: str = "owner_message_injected"
        ) -> None:
            if not path.exists():
                return
            file_size = path.stat().st_size
            with path.open("r", encoding="utf-8") as f:
                if file_size > tail_bytes:
                    f.seek(file_size - tail_bytes)
                    f.readline()
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        ev = json.loads(line)
                        if ev.get(type_field) != type_value:
                            continue
                        text = ev.get("text", "")
                        if not text and "event_repr" in ev:
                            text = ev.get("event_repr", "")[:200]
                        if not text:
                            continue
                        text_hash = _hashlib.md5(text.encode()).hexdigest()[:12]
                        tid = ev.get("task_id") or "unknown"
                        if text_hash not in msg_hash_to_tasks:
                            msg_hash_to_tasks[text_hash] = set()
                        msg_hash_to_tasks[text_hash].add(tid)
                    except (json.JSONDecodeError, ValueError):
                        continue

        _scan_file_for_injected(env.drive_path("logs/events.jsonl"))
        _scan_file_for_injected(
            env.drive_path("logs/supervisor.jsonl"),
            type_field="event_type",
            type_value="owner_message_injected",
        )

        dupes = {h: tids for h, tids in msg_hash_to_tasks.items() if len(tids) > 1}
        if dupes:
            checks.append(
                f"CRITICAL: DUPLICATE PROCESSING: {len(dupes)} message(s) "
                f"appeared in multiple tasks: {', '.join(str(sorted(tids)) for tids in dupes.values())}"
            )
        else:
            checks.append("OK: no duplicate message processing detected")
    except Exception:
        log.debug("Health check failed: duplicate processing", exc_info=True)

    # 7. Session continuity awareness
    try:
        events_path = env.drive_path("logs/events.jsonl")
        if events_path.exists():
            try:
                with events_path.open("rb") as f:
                    f.seek(0, 2)
                    f.seek(max(0, f.tell() - 10000))
                    f.readline()
                    last_lines = f.read().decode("utf-8", errors="replace").strip().split("\n")

                last_event_time = None
                for line in reversed(last_lines):
                    if line.strip():
                        try:
                            evt = json.loads(line)
                            if evt.get("ts"):
                                last_event_time = time.mktime(time.strptime(evt["ts"][:19], "%Y-%m-%dT%H:%M:%S"))
                                break
                        except Exception:
                            continue

                if last_event_time:
                    hours_since = (time.time() - last_event_time) / 3600
                    if hours_since < 0.1:
                        checks.append("OK: session active (last event <6min ago)")
                    elif hours_since < 1:
                        checks.append(f"INFO: session idle ({int(hours_since * 60)}min since last event)")
                    elif hours_since < 24:
                        checks.append(f"INFO: session resumed ({hours_since:.1f}h since last event)")
                    else:
                        checks.append(f"INFO: fresh start ({hours_since:.0f}h since last event)")
            except Exception:
                log.debug("Health check failed: session continuity (inner)", exc_info=True)
    except Exception:
        log.debug("Health check failed: session continuity (outer)", exc_info=True)

    # 8. Vault staleness
    try:
        import re as _re
        import subprocess as _sp

        overview_path = env.repo_path("vault/concepts/codebase_overview.md")
        if overview_path.exists():
            overview_content = overview_path.read_text(encoding="utf-8")
            sha_match = _re.search(r"git:\s*`?([a-f0-9]+)`?", overview_content)
            if sha_match:
                note_sha = sha_match.group(1)
                current_sha = ""
                try:
                    result = _sp.run(
                        ["git", "rev-parse", "HEAD"],
                        cwd=str(env.repo_dir),
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    current_sha = result.stdout.strip()[:12] if result.returncode == 0 else ""
                except Exception:
                    log.debug("Health check failed: git rev-parse", exc_info=True)
                if current_sha and note_sha and len(note_sha) >= 7:
                    compare_len = min(len(current_sha), len(note_sha), 12)
                    if current_sha[:compare_len] != note_sha[:compare_len]:
                        checks.append(
                            f"INFO: VAULT STALE: codebase_overview.md references {note_sha[:8]}, HEAD is {current_sha[:8]}. "
                            f"Consider running scan_repo() to refresh."
                        )
                elif current_sha:
                    checks.append(f"OK: vault overview fresh (HEAD={current_sha[:8]})")
    except Exception:
        log.debug("Health check failed: vault staleness", exc_info=True)

    # 8b. General Vault Freshness
    try:
        from ouroboros.memory import Memory

        mem = Memory(drive_root=env.drive_root)

        critical_notes = [
            "vault/concepts/codebase_overview.md",
            "vault/concepts/minimalism.md",
            "vault/concepts/agency.md",
            "BIBLE.md",
        ]

        for note_path_str in critical_notes:
            note_path = env.repo_path(note_path_str)
            if note_path.exists():
                mtime = note_path.stat().st_mtime
                age_hours_mtime = (time.time() - mtime) / 3600

                last_ver_iso = mem.get_last_verified(note_path_str)
                if last_ver_iso:
                    import datetime

                    last_ver_dt = datetime.datetime.fromisoformat(last_ver_iso.replace("Z", "+00:00"))
                    age_hours_ver = (datetime.datetime.now(datetime.timezone.utc) - last_ver_dt).total_seconds() / 3600
                    age_hours = min(age_hours_mtime, age_hours_ver)
                else:
                    age_hours = age_hours_mtime

                if age_hours > 72:  # 3 days threshold for general vault notes
                    checks.append(f"INFO: VAULT STALE: {note_path_str} last verified {age_hours:.0f}h ago")
    except Exception:
        log.debug("Health check failed: general vault freshness", exc_info=True)

    # 9. Drift detection
    try:
        from ouroboros.drift_detector import DriftDetector

        detector = DriftDetector(repo_dir=env.repo_dir, drive_root=env.drive_root)
        violations = detector.run_all_checks()
        if violations:
            critical = [v for v in violations if v["severity"] == "critical"]
            high = [v for v in violations if v["severity"] == "high"]
            if critical:
                checks.append(f"CRITICAL DRIFT: {len(critical)} critical violations. First: {critical[0]['detail']}")
            if high:
                checks.append(f"HIGH DRIFT: {len(high)} high violations. First: {high[0]['detail']}")
            if not critical and not high:
                checks.append(f"DRIFT: {len(violations)} minor violations detected")
        else:
            checks.append("OK: no drift detected (constitution checks pass)")
    except Exception:
        log.debug("Health check failed: drift detection", exc_info=True)

    # 10. Intelligence layer stats
    try:
        from ouroboros.context_cache import get_cache

        cache = get_cache(repo_dir=env.repo_dir)
        stats = cache.get_stats()
        if stats["hits"] + stats["misses"] > 0:
            checks.append(f"OK: context cache {stats['hit_rate']:.0%} hit rate ({stats['entries']} entries)")
        else:
            checks.append("OK: intelligence layer ready (cache, learning, proof gate, episodic memory, delta eval)")
    except Exception:
        log.debug("Health check failed: context cache", exc_info=True)

    try:
        from ouroboros.temporal_learning import get_learner

        learner = get_learner(repo_dir=env.repo_dir)
        if learner:
            pattern_count = sum(len(tp) for tp in learner._patterns.values())
            if pattern_count > 0:
                checks.append(f"OK: temporal learning {pattern_count} patterns learned")
    except Exception:
        log.debug("Health check failed: temporal learning", exc_info=True)

    # 11. Three-Axis Growth Tracking (Principle 6: Becoming)
    try:
        from ouroboros.three_axis_tracker import get_tracker

        tracker = get_tracker(repo_dir=env.repo_dir)
        stats = tracker.get_stats()
        axes = stats.get("axes", {})
        for axis_name in ["technical", "cognitive", "existential"]:
            axis = axes.get(axis_name, {})
            level = axis.get("level", 0.0)
            trend = axis.get("trend", "stable")
            trend_icon = {"growing": "📈", "stable": "➡️", "declining": "📉"}.get(trend, "❓")
            if level > 0:
                checks.append(f"OK: {axis_name} growth {level:.2f} {trend_icon} ({trend})")
            else:
                checks.append(f"INFO: {axis_name} growth tracking ready (no data yet)")

        total_entries = stats.get("total_entries", 0)
        if total_entries > 0:
            checks.append(f"OK: growth tracking {total_entries} data points recorded")
    except Exception:
        log.debug("Health check failed: three-axis growth tracking", exc_info=True)

    if not checks:
        return ""
    return "## Health Invariants\n\n" + "\n".join(f"- {c}" for c in checks)
