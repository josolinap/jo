"""
Ouroboros — Multi-Model Verification.

Cross-provider verification for high-risk operations.
Inspired by aidevops' multi-model safety pattern.

Different providers have different failure modes, so correlated hallucinations are rare.
Use a second AI model from a different provider to verify destructive operations.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)

HIGH_RISK_KEYWORDS = frozenset(
    {
        "delete",
        "remove",
        "drop",
        "truncate",
        "destroy",
        "purge",
        "force push",
        "reset --hard",
        "rm -rf",
        "format",
        "deploy",
        "publish",
        "release",
        "production",
        "migration",
        "migrate",
        "alter table",
        "revoke",
        "revoke",
        "disable",
        "shutdown",
    }
)


@dataclass
class VerificationResult:
    operation: str
    primary_model: str
    verifier_model: str
    verified: bool
    reason: str
    primary_output: str = ""
    verifier_output: str = ""
    risk_level: str = "low"
    timestamp: str = ""


class MultiVerifier:
    """Cross-provider verification for high-risk operations."""

    def __init__(self):
        self._history: List[VerificationResult] = []
        self._verifier_model = os.environ.get("OUROBOROS_VERIFY_MODEL", "openrouter/google/gemini-2.0-flash-001")
        self._auto_verify = os.environ.get("OUROBOROS_AUTO_VERIFY", "1") == "1"

    def assess_risk(self, operation: str) -> str:
        op_lower = operation.lower()
        high_count = sum(1 for kw in HIGH_RISK_KEYWORDS if kw in op_lower)
        if high_count >= 2:
            return "critical"
        elif high_count >= 1:
            return "high"
        return "low"

    def needs_verification(self, operation: str) -> bool:
        if not self._auto_verify:
            return False
        return self.assess_risk(operation) in ("high", "critical")

    def verify(
        self,
        operation: str,
        primary_output: str,
        verifier_output: str,
        primary_model: str = "",
        verifier_model: str = "",
    ) -> VerificationResult:
        risk = self.assess_risk(operation)
        verified = True
        reason = "Operation verified"

        if risk == "critical":
            primary_lower = primary_output.lower()
            verifier_lower = verifier_output.lower()
            disagree_indicators = ["error", "wrong", "incorrect", "unsafe", "dangerous", "do not", "don't"]
            if any(ind in verifier_lower for ind in disagree_indicators) and not any(
                ind in primary_lower for ind in disagree_indicators
            ):
                verified = False
                reason = "Verifier flagged potential issue"

        result = VerificationResult(
            operation=operation[:100],
            primary_model=primary_model,
            verifier_model=verifier_model or self._verifier_model,
            verified=verified,
            reason=reason,
            primary_output=primary_output[:200],
            verifier_output=verifier_output[:200],
            risk_level=risk,
            timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        )
        self._history.append(result)
        return result

    def get_stats(self) -> Dict[str, Any]:
        if not self._history:
            return {"total": 0}
        verified = sum(1 for r in self._history if r.verified)
        blocked = sum(1 for r in self._history if not r.verified)
        by_risk = {}
        for r in self._history:
            by_risk[r.risk_level] = by_risk.get(r.risk_level, 0) + 1
        return {
            "total": len(self._history),
            "verified": verified,
            "blocked": blocked,
            "by_risk": by_risk,
            "verifier_model": self._verifier_model,
        }

    def summary(self) -> str:
        stats = self.get_stats()
        if stats["total"] == 0:
            return "No verifications performed yet."
        return (
            f"## Multi-Model Verification\n"
            f"- **Total**: {stats['total']}\n"
            f"- **Verified**: {stats['verified']}\n"
            f"- **Blocked**: {stats['blocked']}\n"
            f"- **By risk**: {json.dumps(stats['by_risk'])}\n"
            f"- **Verifier model**: {stats['verifier_model']}"
        )


_verifier: Optional[MultiVerifier] = None


def get_verifier() -> MultiVerifier:
    global _verifier
    if _verifier is None:
        _verifier = MultiVerifier()
    return _verifier


def get_tools():
    from ouroboros.tools.registry import ToolEntry

    def verify_check(ctx, operation: str) -> str:
        risk = get_verifier().assess_risk(operation)
        needs = get_verifier().needs_verification(operation)
        return f"Operation: {operation[:80]}\nRisk: {risk}\nNeeds verification: {needs}"

    def verify_stats(ctx) -> str:
        return get_verifier().summary()

    return [
        ToolEntry(
            "verify_check",
            {
                "name": "verify_check",
                "description": "Check if an operation needs multi-model verification based on risk level.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "operation": {"type": "string", "description": "Operation description to check"},
                    },
                    "required": ["operation"],
                },
            },
            verify_check,
        ),
        ToolEntry(
            "verify_stats",
            {
                "name": "verify_stats",
                "description": "Get multi-model verification statistics.",
                "parameters": {"type": "object", "properties": {}},
            },
            verify_stats,
        ),
    ]
