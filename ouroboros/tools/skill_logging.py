"""Skill logging — activation/outcome tracking and vault export.

Extracted from skills.py to reduce module size (Principle 5: Minimalism).
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from ouroboros.tools.skill_definitions import SKILL_LOG_PATH, Skill

log = logging.getLogger(__name__)


def _get_skill_log_path() -> Path:
    """Get the skill log file path, expanding ~ to home directory."""
    return Path(SKILL_LOG_PATH).expanduser()


def log_skill_activation(skill: Skill, matched_triggers: List[str], user_input: str = "") -> None:
    """Log skill activation for analysis and evolution tracking."""
    log_entry = {
        "timestamp": datetime.now().isoformat(),
        "skill_name": skill.name,
        "skill_version": skill.version,
        "matched_triggers": matched_triggers,
        "user_input": user_input[:500] if user_input else "",
        "type": "activation",
    }

    try:
        log_path = _get_skill_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text())
            except json.JSONDecodeError:
                existing = []

        existing.append(log_entry)
        if len(existing) > 1000:
            existing = existing[-1000:]

        log_path.write_text(json.dumps(existing, indent=2))
        log.debug(f"Logged skill activation: {skill.name}")
    except Exception as e:
        log.warning(f"Failed to log skill activation: {e}")


def log_skill_outcome(
    skill_name: str,
    task: str,
    success: bool,
    score: float = 0.0,
    metadata: Optional[Dict[str, Any]] = None,
) -> None:
    """Track skill outcome for learning (inspired by VikaasLoop's win_rate tracking)."""
    outcome_entry = {
        "timestamp": datetime.now().isoformat(),
        "skill_name": skill_name,
        "task": task[:200] if task else "",
        "success": success,
        "score": score,
        "metadata": metadata or {},
        "type": "outcome",
    }

    try:
        log_path = _get_skill_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)

        existing = []
        if log_path.exists():
            try:
                existing = json.loads(log_path.read_text())
            except json.JSONDecodeError:
                existing = []

        existing.append(outcome_entry)
        if len(existing) > 1000:
            existing = existing[-1000:]

        log_path.write_text(json.dumps(existing, indent=2))
        log.debug(f"Logged skill outcome: {skill_name} success={success} score={score:.2f}")
    except Exception as e:
        log.warning(f"Failed to log skill outcome: {e}")


def get_skill_success_rates() -> Dict[str, Dict[str, float]]:
    """Get success rates for all skills from historical outcomes."""
    try:
        log_path = _get_skill_log_path()
        if not log_path.exists():
            return {}

        entries = json.loads(log_path.read_text())
        outcomes = [e for e in entries if e.get("type") == "outcome"]

        if not outcomes:
            return {}

        skill_data: Dict[str, Dict[str, Any]] = {}
        for entry in outcomes:
            name = entry.get("skill_name", "")
            if not name:
                continue

            if name not in skill_data:
                skill_data[name] = {
                    "successes": 0,
                    "total": 0,
                    "scores": [],
                    "last_used": entry.get("timestamp", ""),
                }

            skill_data[name]["total"] += 1
            if entry.get("success", False):
                skill_data[name]["successes"] += 1
            skill_data[name]["scores"].append(entry.get("score", 0.0))
            skill_data[name]["last_used"] = entry.get("timestamp", skill_data[name]["last_used"])

        result = {}
        for name, data in skill_data.items():
            total = data["total"]
            if total > 0:
                result[name] = {
                    "success_rate": data["successes"] / total,
                    "avg_score": sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0.0,
                    "total_uses": total,
                    "last_used": data["last_used"],
                }

        return result
    except Exception as e:
        log.warning(f"Failed to calculate skill success rates: {e}")
        return {}


def export_skill_outcomes_to_vault(repo_dir: Optional[Path] = None) -> str:
    """Export skill outcome summary to vault for institutional memory."""
    if repo_dir is None:
        repo_dir = Path(os.environ.get("REPO_DIR", "."))

    vault_path = repo_dir / "vault" / "concepts" / "skill_outcomes.md"

    try:
        success_rates = get_skill_success_rates()

        if not success_rates:
            return "No skill outcomes recorded yet."

        sorted_skills = sorted(
            success_rates.items(),
            key=lambda x: x[1]["success_rate"],
            reverse=True,
        )

        lines = [
            "# Skill Outcomes Report",
            "",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Summary",
            "",
        ]

        top_performers = [s for s in sorted_skills if s[1]["success_rate"] >= 0.7]
        if top_performers:
            lines.append("### Top Performing Skills")
            lines.append("")
            for name, data in top_performers:
                lines.append(
                    f"- **{name}**: {data['success_rate']:.0%} success ({data['total_uses']} uses, avg score: {data['avg_score']:.2f})"
                )
            lines.append("")

        needs_work = [s for s in sorted_skills if s[1]["success_rate"] < 0.5 and s[1]["total_uses"] >= 3]
        if needs_work:
            lines.append("### Skills Needing Improvement")
            lines.append("")
            for name, data in needs_work:
                lines.append(f"- **{name}**: {data['success_rate']:.0%} success ({data['total_uses']} uses)")
            lines.append("")

        lines.append("### All Skills Performance")
        lines.append("")
        lines.append("| Skill | Success Rate | Uses | Avg Score | Last Used |")
        lines.append("|-------|--------------|------|-----------|-----------|")

        for name, data in sorted_skills:
            rate = f"{data['success_rate']:.0%}"
            uses = str(data["total_uses"])
            score = f"{data['avg_score']:.2f}"
            last = data["last_used"][:10] if data["last_used"] else "N/A"
            lines.append(f"| {name} | {rate} | {uses} | {score} | {last} |")

        lines.append("")
        lines.append("---")
        lines.append("*Auto-generated by Jo's skill learning system*")

        content = "\n".join(lines)
        vault_path.parent.mkdir(parents=True, exist_ok=True)
        vault_path.write_text(content, encoding="utf-8")

        return f"Exported skill outcomes to vault ({len(sorted_skills)} skills)"

    except Exception as e:
        log.error(f"Failed to export skill outcomes to vault: {e}")
        return f"Export failed: {e}"


def get_skill_stats() -> Dict[str, Any]:
    """Get skill activation statistics for analysis."""
    try:
        log_path = _get_skill_log_path()
        if not log_path.exists():
            return {"total_activations": 0, "message": "No activations logged yet"}

        activations = json.loads(log_path.read_text())

        skill_counts: Dict[str, int] = {}
        trigger_counts: Dict[str, int] = {}

        for entry in activations:
            skill_counts[entry["skill_name"]] = skill_counts.get(entry["skill_name"], 0) + 1
            for trigger in entry.get("matched_triggers", []):
                trigger_counts[trigger] = trigger_counts.get(trigger, 0) + 1

        return {
            "total_activations": len(activations),
            "by_skill": dict(sorted(skill_counts.items(), key=lambda x: -x[1])),
            "top_triggers": dict(sorted(trigger_counts.items(), key=lambda x: -x[1])[:20]),
            "recent": activations[-10:] if activations else [],
        }
    except Exception as e:
        log.warning(f"Failed to get skill stats: {e}")
        return {"error": str(e)}
