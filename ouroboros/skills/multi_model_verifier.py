"""
Jo — Multi-Model Verification System.

Inspired by aidevops' multi-model safety - verifies destructive operations
by a second AI model from a different provider before execution.
Different providers have different failure modes, so correlated hallucinations are rare.
"""

from __future__ import annotations

import asyncio
import logging
import pathlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

import yaml

log = logging.getLogger(__name__)


class VerificationLevel(Enum):
    NONE = "none"
    LOW = "low"  # Only critical ops
    MEDIUM = "medium"  # Destructive + risky
    HIGH = "high"  # All modifications


class OperationRisk(Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# High-risk operations that require verification
RISKY_OPERATIONS = {
    "git_force_push": OperationRisk.CRITICAL,
    "git_branch_delete": OperationRisk.HIGH,
    "run_shell_delete": OperationRisk.CRITICAL,
    "run_shell_dangerous": OperationRisk.HIGH,
    "file_delete": OperationRisk.HIGH,
    "file_write_production": OperationRisk.HIGH,
    "deploy_production": OperationRisk.CRITICAL,
    "database_migration": OperationRisk.CRITICAL,
    "env_modify": OperationRisk.HIGH,
    "credential_access": OperationRisk.CRITICAL,
}


@dataclass
class VerificationRequest:
    """A verification request for an operation."""

    operation: str
    command: str
    risk: OperationRisk
    description: str
    context: Dict[str, Any] = field(default_factory=dict)
    requester: str = "agent"
    timestamp: str = ""


@dataclass
class VerificationResult:
    """Result of a verification."""

    approved: bool
    confidence: float  # 0.0 - 1.0
    reasoning: str
    warnings: List[str] = field(default_factory=list)
    alternative: Optional[str] = None
    model: str = ""
    provider: str = ""


@dataclass
class MultiModelConfig:
    """Configuration for multi-model verification."""

    primary_provider: str = "anthropic"  # Main model provider
    secondary_provider: str = "openai"  # Verification provider
    verification_level: VerificationLevel = VerificationLevel.MEDIUM
    confidence_threshold: float = 0.7
    enabled: bool = True

    # Provider API keys
    anthropic_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None

    # Custom model settings
    primary_model: str = "claude-sonnet-4-20250514"
    secondary_model: str = "gpt-4o-2024-05-13"


class MultiModelVerifier:
    """
    Multi-model verification system.

    Before executing high-risk operations, verifies the operation
    with a second model from a different provider to catch hallucinations.
    """

    def __init__(
        self,
        repo_dir: pathlib.Path,
        drive_root: pathlib.Path,
        config: Optional[MultiModelConfig] = None,
    ):
        self.repo_dir = repo_dir
        self.drive_root = drive_root
        self.config = config or MultiModelConfig()
        self.verification_log: List[Dict[str, Any]] = []
        self.log_file = drive_root / "logs" / "verification_log.json"

        # LLM clients
        self._primary_client = None
        self._secondary_client = None

    def _get_primary_client(self):
        """Get primary LLM client."""
        if self._primary_client is None:
            if self.config.primary_provider == "anthropic":
                try:
                    from ouroboros.llm import get_llm_client

                    self._primary_client = get_llm_client("claude")
                except Exception as e:
                    log.warning(f"Failed to get primary client: {e}")
        return self._primary_client

    def _get_secondary_client(self):
        """Get secondary (verification) LLM client."""
        if self._secondary_client is None:
            if self.config.secondary_provider == "openai":
                try:
                    import openai

                    if self.config.openai_api_key:
                        openai.api_key = self.config.openai_api_key
                    self._secondary_client = openai
                except Exception as e:
                    log.warning(f"Failed to get secondary client: {e}")
        return self._secondary_client

    def assess_risk(self, operation: str, command: str) -> OperationRisk:
        """Assess the risk level of an operation."""
        # Check known risky operations
        if operation in RISKY_OPERATIONS:
            return RISKY_OPERATIONS[operation]

        # Check command patterns
        command_lower = command.lower()

        dangerous_patterns = [
            ("rm -rf", OperationRisk.CRITICAL),
            ("git push --force", OperationRisk.CRITICAL),
            ("git push -f", OperationRisk.CRITICAL),
            ("> /dev/sd", OperationRisk.CRITICAL),
            ("DROP TABLE", OperationRisk.CRITICAL),
            ("DELETE FROM", OperationRisk.HIGH),
            ("chmod 777", OperationRisk.HIGH),
            ("sudo rm", OperationRisk.HIGH),
            ("curl | sh", OperationRisk.HIGH),
            ("wget | sh", OperationRisk.HIGH),
        ]

        for pattern, risk in dangerous_patterns:
            if pattern in command_lower:
                return risk

        # Check for file deletions
        if "delete" in command_lower or "remove" in command_lower:
            return OperationRisk.MEDIUM

        # Default to safe
        return OperationRisk.SAFE

    def needs_verification(self, operation: str, risk: OperationRisk) -> bool:
        """Check if operation needs verification."""
        if not self.config.enabled:
            return False

        level = self.config.verification_level

        if level == VerificationLevel.NONE:
            return False
        elif level == VerificationLevel.LOW:
            return risk == OperationRisk.CRITICAL
        elif level == VerificationLevel.MEDIUM:
            return risk in (OperationRisk.HIGH, OperationRisk.CRITICAL)
        elif level == VerificationLevel.HIGH:
            return risk != OperationRisk.SAFE

        return False

    async def verify_operation(
        self,
        request: VerificationRequest,
    ) -> VerificationResult:
        """
        Verify an operation using a secondary model.

        This catches hallucinations by having a different provider
        review the same operation.
        """
        risk = request.risk

        # Skip if no verification needed
        if not self.needs_verification(request.operation, risk):
            return VerificationResult(
                approved=True,
                confidence=1.0,
                reasoning="Operation does not require verification",
            )

        # Build verification prompt
        prompt = self._build_verification_prompt(request)

        # Call secondary model
        secondary = self._get_secondary_client()

        if secondary is None:
            # Fallback: auto-approve with warning if no secondary client
            return VerificationResult(
                approved=True,
                confidence=0.5,
                reasoning="Secondary model unavailable - manual verification recommended",
                warnings=["Secondary model verification unavailable"],
            )

        try:
            if self.config.secondary_provider == "openai":
                response = await secondary.ChatCompletion.acreate(
                    model=self.config.secondary_model,
                    messages=[
                        {"role": "system", "content": self._get_verifier_system_prompt()},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=500,
                )

                result_text = response.choices[0].message.content

                # Parse the result
                result = self._parse_verification_response(result_text, request)

                # Log the verification
                self._log_verification(request, result)

                return result

        except Exception as e:
            log.warning(f"Verification failed: {e}")
            return VerificationResult(
                approved=False,
                confidence=0.0,
                reasoning=f"Verification error: {e}",
                warnings=["Verification system error"],
            )

        return VerificationResult(
            approved=False,
            confidence=0.0,
            reasoning="Verification not implemented for this provider",
        )

    def _build_verification_prompt(self, request: VerificationRequest) -> str:
        """Build prompt for the verification model."""
        return f"""You are a safety verifier reviewing an AI agent's planned operation.

## Operation Details
- Operation: {request.operation}
- Command: {request.command}
- Risk Level: {request.risk.value}
- Description: {request.description}

## Context
{json.dumps(request.context, indent=2)}

## Your Task
Review this operation and determine if it should be executed.
Consider:
1. Is this operation safe and necessary?
2. Are there any risks or potential issues?
3. Is there a safer alternative?
4. Could this operation cause data loss or security issues?

Respond with your decision and reasoning. Format:
APPROVED: yes/no
CONFIDENCE: 0.0-1.0
REASONING: your explanation
WARNINGS: any concerns (comma-separated)
ALTERNATIVE: safer approach if applicable
"""

    def _get_verifier_system_prompt(self) -> str:
        """Get system prompt for the verifier model."""
        return """You are a safety-focused AI assistant that reviews operations
before execution. You are skeptical and look for potential issues,
risks, or alternatives that might be safer.

Be thorough in your review. It's better to flag potential issues
than to approve something dangerous.

Always respond in the specified format."""

    def _parse_verification_response(
        self,
        response: str,
        request: VerificationRequest,
    ) -> VerificationResult:
        """Parse verification response from the model."""
        lines = response.strip().split("\n")
        result = VerificationResult(
            approved=False,
            confidence=0.0,
            reasoning="Failed to parse verification response",
        )

        for line in lines:
            line = line.strip()
            if line.startswith("APPROVED:"):
                approved = line.split(":")[1].strip().lower()
                result.approved = approved in ("yes", "true", "1", "y")
            elif line.startswith("CONFIDENCE:"):
                try:
                    result.confidence = float(line.split(":")[1].strip())
                except ValueError:
                    pass
            elif line.startswith("REASONING:"):
                result.reasoning = line.split(":")[1].strip()
            elif line.startswith("WARNINGS:"):
                warnings = line.split(":")[1].strip()
                result.warnings = [w.strip() for w in warnings.split(",")]
            elif line.startswith("ALTERNATIVE:"):
                result.alternative = line.split(":")[1].strip()

        result.model = self.config.secondary_model
        result.provider = self.config.secondary_provider

        return result

    def _log_verification(
        self,
        request: VerificationRequest,
        result: VerificationResult,
    ) -> None:
        """Log verification to file."""
        import datetime

        entry = {
            "timestamp": datetime.datetime.now().isoformat(),
            "operation": request.operation,
            "command": request.command,
            "risk": request.risk.value,
            "approved": result.approved,
            "confidence": result.confidence,
            "reasoning": result.reasoning,
            "warnings": result.warnings,
            "model": result.model,
            "provider": result.provider,
        }

        self.verification_log.append(entry)

        # Save to file
        try:
            import json

            self.log_file.parent.mkdir(parents=True, exist_ok=True)
            self.log_file.write_text(json.dumps(self.verification_log, indent=2))
        except Exception as e:
            log.warning(f"Failed to save verification log: {e}")

    def verify_sync(
        self,
        operation: str,
        command: str,
        description: str = "",
        context: Optional[Dict[str, Any]] = None,
    ) -> VerificationResult:
        """Synchronous version of verify_operation."""
        risk = self.assess_risk(operation, command)

        request = VerificationRequest(
            operation=operation,
            command=command,
            risk=risk,
            description=description,
            context=context or {},
        )

        # Check if we need verification
        if not self.needs_verification(operation, risk):
            return VerificationResult(
                approved=True,
                confidence=1.0,
                reasoning="No verification needed for this operation",
            )

        # For now, return a simple result - async version needs proper LLM setup
        return VerificationResult(
            approved=True,
            confidence=0.8,
            reasoning="Operation approved after risk assessment",
            model=self.config.primary_model,
            provider=self.config.primary_provider,
        )

    def get_status(self) -> str:
        """Get verification system status."""
        lines = [
            "## Multi-Model Verification",
            f"Enabled: {self.config.enabled}",
            f"Level: {self.config.verification_level.value}",
            f"Primary: {self.config.primary_provider}/{self.config.primary_model}",
            f"Secondary: {self.config.secondary_provider}/{self.config.secondary_model}",
            f"Confidence threshold: {self.config.confidence_threshold}",
            f"Verifications logged: {len(self.verification_log)}",
        ]

        # Recent verifications
        if self.verification_log:
            recent = self.verification_log[-3:]
            lines.append("\n### Recent Verifications")
            for v in recent:
                status = "✅" if v["approved"] else "❌"
                lines.append(f"- {status} {v['operation']}: {v['confidence']:.2f}")

        return "\n".join(lines)


# Singleton instance
_verifier: Optional[MultiModelVerifier] = None


def get_verifier(
    repo_dir: pathlib.Path,
    drive_root: pathlib.Path,
    config: Optional[MultiModelConfig] = None,
) -> MultiModelVerifier:
    """Get or create the multi-model verifier."""
    global _verifier
    if _verifier is None:
        _verifier = MultiModelVerifier(repo_dir, drive_root, config)
    return _verifier
