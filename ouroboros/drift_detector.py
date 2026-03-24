"""Drift detector — checks current state against constitution and baseline.

Detects:
- Version desync
- Module growth beyond thresholds
- Missing required modules/concepts
- Identity core statement removal
- Protected file modifications
- Modules over line limits
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)


class DriftDetector:
    """Detect drift from constitution and baseline."""

    def __init__(self, repo_dir: Path, drive_root: Optional[Path] = None):
        self.repo_dir = Path(repo_dir)
        self.drive_root = Path(drive_root) if drive_root else self.repo_dir / ".jo_data"
        self.constitution = self._load_json("constitution.json")
        self.baseline = self._load_json("drift_baseline.json")

    def _load_json(self, filename: str) -> Dict[str, Any]:
        path = self.repo_dir / filename
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("Failed to load %s: %s", filename, e)
        return {}

    def run_all_checks(self) -> List[Dict[str, Any]]:
        """Run all drift checks and return violations."""
        violations = []
        violations.extend(self._check_version_sync())
        violations.extend(self._check_identity_freshness())
        violations.extend(self._check_identity_core_statements())
        violations.extend(self._check_module_line_limits())
        violations.extend(self._check_module_growth())
        violations.extend(self._check_required_modules())
        violations.extend(self._check_required_vault_concepts())
        violations.extend(self._check_protected_files())
        return violations

    def get_report(self) -> str:
        """Get human-readable drift report."""
        violations = self.run_all_checks()
        if not violations:
            return "OK: No drift detected — all constitution checks pass"

        lines = ["## Drift Detection Report\n"]
        critical = [v for v in violations if v["severity"] == "critical"]
        high = [v for v in violations if v["severity"] == "high"]
        medium = [v for v in violations if v["severity"] == "medium"]
        low = [v for v in violations if v["severity"] == "low"]

        if critical:
            lines.append(f"CRITICAL ({len(critical)}):")
            for v in critical:
                lines.append(f"  - {v['rule']}: {v['detail']}")
        if high:
            lines.append(f"HIGH ({len(high)}):")
            for v in high:
                lines.append(f"  - {v['rule']}: {v['detail']}")
        if medium:
            lines.append(f"MEDIUM ({len(medium)}):")
            for v in medium:
                lines.append(f"  - {v['rule']}: {v['detail']}")

        return "\n".join(lines)

    # --- Individual checks ---

    def _check_version_sync(self) -> List[Dict[str, Any]]:
        """Check VERSION == git tag == pyproject.toml version."""
        violations = []
        try:
            import re as _re

            version = (self.repo_dir / "VERSION").read_text(encoding="utf-8").strip()

            result = subprocess.run(
                ["git", "describe", "--tags", "--abbrev=0"],
                cwd=str(self.repo_dir),
                capture_output=True,
                text=True,
                timeout=5,
            )
            git_tag = result.stdout.strip().lstrip("v") if result.returncode == 0 else ""

            if git_tag and version != git_tag:
                violations.append(
                    {
                        "rule": "version_sync",
                        "severity": "critical",
                        "detail": f"VERSION={version} but git tag={git_tag}",
                        "action": "block_commit",
                    }
                )

            # Check pyproject.toml
            pyproject = self.repo_dir / "pyproject.toml"
            if pyproject.exists():
                content = pyproject.read_text(encoding="utf-8")
                match = _re.search(r'version\s*=\s*"([^"]+)"', content)
                if match:
                    pp_version = match.group(1)
                    if pp_version != version:
                        violations.append(
                            {
                                "rule": "version_sync",
                                "severity": "critical",
                                "detail": f"VERSION={version} but pyproject.toml={pp_version}",
                                "action": "block_commit",
                            }
                        )
        except Exception:
            pass
        return violations

    def _check_identity_freshness(self) -> List[Dict[str, Any]]:
        """Check identity.md is recent."""
        violations = []
        try:
            max_age = self.constitution.get("principles", {}).get("1_continuity", {}).get("max_identity_age_hours", 8)
            identity_path = self.drive_root / "memory" / "identity.md"
            if identity_path.exists():
                age_hours = (time.time() - identity_path.stat().st_mtime) / 3600
                if age_hours > max_age:
                    violations.append(
                        {
                            "rule": "identity_fresh",
                            "severity": "high",
                            "detail": f"identity.md is {age_hours:.0f}h old (max {max_age}h)",
                        }
                    )
            else:
                violations.append(
                    {
                        "rule": "identity_fresh",
                        "severity": "high",
                        "detail": "identity.md does not exist",
                    }
                )
        except Exception:
            pass
        return violations

    def _check_identity_core_statements(self) -> List[Dict[str, Any]]:
        """Check that identity core statements haven't been removed."""
        violations = []
        try:
            identity_path = self.drive_root / "memory" / "identity.md"
            if not identity_path.exists():
                return violations

            content = identity_path.read_text(encoding="utf-8", errors="ignore").lower()
            core = self.baseline.get("identity_core_statements", [])
            for statement in core:
                if statement.lower() not in content:
                    violations.append(
                        {
                            "rule": "identity_core",
                            "severity": "critical",
                            "detail": f'Core identity statement missing: "{statement}"',
                        }
                    )
        except Exception:
            pass
        return violations

    def _check_module_line_limits(self) -> List[Dict[str, Any]]:
        """Check modules under line limit."""
        violations = []
        max_lines = self.constitution.get("principles", {}).get("5_minimalism", {}).get("max_module_lines", 1000)
        for module_dir in ["ouroboros", "supervisor"]:
            dir_path = self.repo_dir / module_dir
            if not dir_path.exists():
                continue
            for py_file in dir_path.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                try:
                    lines = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
                    if lines > max_lines:
                        violations.append(
                            {
                                "rule": "module_line_limit",
                                "severity": "high",
                                "detail": f"{py_file.relative_to(self.repo_dir)} has {lines} lines (max {max_lines})",
                            }
                        )
                except Exception:
                    pass
        return violations

    def _check_module_growth(self) -> List[Dict[str, Any]]:
        """Check module count hasn't grown beyond threshold."""
        violations = []
        try:
            thresholds = self.constitution.get("drift_thresholds", {})
            max_growth_pct = thresholds.get("max_module_growth_pct", 20)
            baseline_count = self.baseline.get("module_count", 0)

            current_count = 0
            for module_dir in ["ouroboros", "supervisor"]:
                dir_path = self.repo_dir / module_dir
                if dir_path.exists():
                    current_count += len([f for f in dir_path.rglob("*.py") if "__pycache__" not in str(f)])

            if baseline_count > 0:
                growth_pct = ((current_count - baseline_count) / baseline_count) * 100
                if growth_pct > max_growth_pct:
                    violations.append(
                        {
                            "rule": "module_growth",
                            "severity": "high",
                            "detail": f"Module count grew {growth_pct:.0f}% ({baseline_count} → {current_count}, max {max_growth_pct}%)",
                        }
                    )
        except Exception:
            pass
        return violations

    def _check_required_modules(self) -> List[Dict[str, Any]]:
        """Check that required modules still exist."""
        violations = []
        for module in self.baseline.get("required_modules", []):
            if not (self.repo_dir / module).exists():
                violations.append(
                    {
                        "rule": "required_module",
                        "severity": "critical",
                        "detail": f"Required module missing: {module}",
                    }
                )
        return violations

    def _check_required_vault_concepts(self) -> List[Dict[str, Any]]:
        """Check that required vault concepts still exist."""
        violations = []
        vault_dir = self.repo_dir / "vault" / "concepts"
        if not vault_dir.exists():
            return violations
        for concept in self.baseline.get("required_vault_concepts", []):
            if not (vault_dir / f"{concept}.md").exists():
                violations.append(
                    {
                        "rule": "required_concept",
                        "severity": "high",
                        "detail": f"Required vault concept missing: {concept}.md",
                    }
                )
        return violations

    def _check_protected_files(self) -> List[Dict[str, Any]]:
        """Check that constitution and baseline files haven't been modified."""
        violations = []
        immutable = self.constitution.get("invariants", {}).get("protected_files", {}).get("immutable_files", [])
        for filename in immutable:
            filepath = self.repo_dir / filename
            if not filepath.exists():
                violations.append(
                    {
                        "rule": "protected_file",
                        "severity": "critical",
                        "detail": f"Immutable file missing: {filename}",
                    }
                )
        return violations


def run_drift_check(repo_dir: Path, drive_root: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Convenience function to run drift detection."""
    detector = DriftDetector(repo_dir=repo_dir, drive_root=drive_root)
    return detector.run_all_checks()
