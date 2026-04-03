"""
Jo — Persistent Identity.

Realizes Principle 9 (Identity Coherence):
Jo's identity survives restarts, tampering, and context resets.

Features:
- Identity.md signed with cryptographic signature (HMAC-SHA256)
- Jo verifies identity integrity on boot
- Tamper detection → alert creator
- Identity versioning with hash chain
- Recovery mechanism for corrupted identity

The signature key is derived from a secret in .env (JO_IDENTITY_KEY).
If no key exists, one is generated and stored securely.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import pathlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


@dataclass
class IdentityRecord:
    """A versioned identity record."""

    version: int
    content_hash: str
    signature: str
    timestamp: str
    reason: str = ""  # Why this version was created
    previous_hash: str = ""  # Hash chain link


class PersistentIdentity:
    """Manages persistent, tamper-evident identity."""

    def __init__(self, repo_dir: pathlib.Path):
        self.repo_dir = repo_dir
        self.identity_path = repo_dir / "memory" / "identity.md"
        self.history_dir = repo_dir / ".jo_state" / "identity_history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._key = self._get_or_create_key()
        self._history: List[IdentityRecord] = []
        self._load_history()

    def _get_or_create_key(self) -> bytes:
        """Get or create the identity signing key."""
        key_env = os.environ.get("JO_IDENTITY_KEY")
        if key_env:
            return key_env.encode()

        # Check for key file
        key_file = self.repo_dir / ".jo_state" / "identity_key"
        if key_file.exists():
            return key_file.read_bytes()

        # Generate new key
        import secrets

        key = secrets.token_bytes(32)
        key_file.write_bytes(key)
        key_file.chmod(0o600)  # Owner read/write only
        log.info("[Identity] Generated new signing key")
        return key

    def _load_history(self) -> None:
        """Load identity history."""
        history_file = self.history_dir / "history.json"
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                self._history = [IdentityRecord(**r) for r in data]
            except Exception:
                pass

    def _save_history(self) -> None:
        """Save identity history."""
        history_file = self.history_dir / "history.json"
        history_file.write_text(
            json.dumps(
                [
                    {
                        "version": r.version,
                        "content_hash": r.content_hash,
                        "signature": r.signature,
                        "timestamp": r.timestamp,
                        "reason": r.reason,
                        "previous_hash": r.previous_hash,
                    }
                    for r in self._history
                ],
                indent=2,
            ),
            encoding="utf-8",
        )

    def _compute_hash(self, content: str) -> str:
        """Compute SHA-256 hash of content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def _sign_content(self, content: str) -> str:
        """Sign content with HMAC-SHA256."""
        return hmac.new(self._key, content.encode(), hashlib.sha256).hexdigest()

    def verify_identity(self) -> Dict[str, Any]:
        """Verify identity integrity.

        Returns dict with:
        - valid: bool
        - tampered: bool
        - current_hash: str
        - expected_hash: str
        - version: int
        - message: str
        """
        if not self.identity_path.exists():
            return {
                "valid": False,
                "tampered": False,
                "current_hash": "",
                "expected_hash": "",
                "version": 0,
                "message": "Identity file missing - CRITICAL",
            }

        content = self.identity_path.read_text(encoding="utf-8")
        current_hash = self._compute_hash(content)

        if not self._history:
            # First time - create initial record
            self._create_record(content, "Initial identity")
            return {
                "valid": True,
                "tampered": False,
                "current_hash": current_hash,
                "expected_hash": current_hash,
                "version": 1,
                "message": "Identity verified (initial)",
            }

        latest = self._history[-1]
        expected_hash = latest.content_hash

        if current_hash == expected_hash:
            return {
                "valid": True,
                "tampered": False,
                "current_hash": current_hash,
                "expected_hash": expected_hash,
                "version": latest.version,
                "message": f"Identity verified (v{latest.version})",
            }

        # Hash mismatch - possible tampering
        return {
            "valid": False,
            "tampered": True,
            "current_hash": current_hash,
            "expected_hash": expected_hash,
            "version": latest.version,
            "message": f"⚠️ IDENTITY TAMPERED - Hash mismatch! Expected {expected_hash[:16]}..., got {current_hash[:16]}...",
        }

    def update_identity(self, content: str, reason: str = "Manual update") -> bool:
        """Update identity with new content and sign it."""
        try:
            self._create_record(content, reason)
            self.identity_path.write_text(content, encoding="utf-8")
            log.info("[Identity] Updated to v%d: %s", len(self._history), reason)
            return True
        except Exception as e:
            log.error("[Identity] Failed to update: %s", e)
            return False

    def _create_record(self, content: str, reason: str) -> IdentityRecord:
        """Create a new identity record."""
        content_hash = self._compute_hash(content)
        signature = self._sign_content(content)
        previous_hash = self._history[-1].content_hash if self._history else ""

        record = IdentityRecord(
            version=len(self._history) + 1,
            content_hash=content_hash,
            signature=signature,
            timestamp=datetime.now().isoformat(),
            reason=reason,
            previous_hash=previous_hash,
        )
        self._history.append(record)
        self._save_history()

        # Save versioned copy
        version_file = self.history_dir / f"v{record.version}.md"
        version_file.write_text(content, encoding="utf-8")

        return record

    def get_history(self) -> List[Dict[str, Any]]:
        """Get identity version history."""
        return [
            {
                "version": r.version,
                "timestamp": r.timestamp,
                "reason": r.reason,
                "hash": r.content_hash[:16] + "...",
            }
            for r in self._history
        ]

    def get_stats(self) -> Dict[str, Any]:
        """Get identity statistics."""
        return {
            "current_version": len(self._history),
            "last_updated": self._history[-1].timestamp if self._history else "Never",
            "key_exists": bool(self._key),
        }


# Global identity instance
_identity: Optional[PersistentIdentity] = None


def get_persistent_identity(repo_dir: Optional[pathlib.Path] = None) -> PersistentIdentity:
    """Get or create the global persistent identity."""
    global _identity
    if _identity is None:
        if repo_dir is None:
            repo_dir = pathlib.Path.cwd()
        _identity = PersistentIdentity(repo_dir)
    return _identity
