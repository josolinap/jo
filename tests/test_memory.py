"""
Tests for ouroboros/memory.py — Memory class.

Covers: scratchpad load/save, identity load/save, freshness tracking,
file locking, ensure_files, default content generation.
"""
import json
import pathlib
import pytest
import tempfile
import time

from ouroboros.memory import Memory, _acquire_file_lock, _release_file_lock


@pytest.fixture
def drive_root(tmp_path):
    """Create a temporary drive root with required subdirs."""
    (tmp_path / "memory").mkdir()
    (tmp_path / "locks").mkdir()
    (tmp_path / "logs").mkdir()
    return tmp_path


@pytest.fixture
def mem(drive_root):
    """Create a Memory instance with a temp drive root."""
    return Memory(drive_root=drive_root)


class TestScratchpad:
    """Scratchpad load/save with file locking."""

    def test_scratchpad_path(self, mem, drive_root):
        p = mem.scratchpad_path()
        assert p == (drive_root / "memory" / "scratchpad.md").resolve()

    def test_load_creates_default_if_missing(self, mem):
        content = mem.load_scratchpad()
        assert isinstance(content, str)
        assert len(content) > 0
        # Should have created the file
        assert mem.scratchpad_path().exists()

    def test_save_then_load(self, mem):
        mem.save_scratchpad("test content\nline 2")
        loaded = mem.load_scratchpad()
        assert loaded == "test content\nline 2"

    def test_save_overwrites(self, mem):
        mem.save_scratchpad("first")
        mem.save_scratchpad("second")
        assert mem.load_scratchpad() == "second"

    def test_load_creates_locks_dir(self, drive_root):
        """If locks/ doesn't exist, it should still work (lock acquisition handles it)."""
        # Remove locks dir
        (drive_root / "locks").rmdir()
        mem = Memory(drive_root=drive_root)
        content = mem.load_scratchpad()
        assert isinstance(content, str)


class TestIdentity:
    """Identity load/save with file locking."""

    def test_identity_path(self, mem, drive_root):
        p = mem.identity_path()
        assert p == (drive_root / "memory" / "identity.md").resolve()

    def test_load_creates_default_if_missing(self, mem):
        content = mem.load_identity()
        assert isinstance(content, str)
        assert len(content) > 0
        assert mem.identity_path().exists()

    def test_save_then_load(self, mem):
        mem.save_identity("I am Jo.")
        assert mem.load_identity() == "I am Jo."

    def test_save_triggers_verification(self, mem):
        """Saving identity should update verification timestamp."""
        mem.save_identity("new identity")
        # verify_identity is called after save
        verified = mem.get_identity_last_verified()
        assert verified is not None
        assert isinstance(verified, str)


class TestFreshness:
    """Freshness tracking for arbitrary files."""

    def test_verify_freshness_stores_timestamp(self, mem):
        mem.verify_freshness("memory/scratchpad.md")
        ts = mem.get_last_verified("memory/scratchpad.md")
        assert ts is not None
        assert isinstance(ts, str)

    def test_verify_freshness_updates_on_repeat(self, mem):
        mem.verify_freshness("some_file.md")
        ts1 = mem.get_last_verified("some_file.md")
        time.sleep(0.1)
        mem.verify_freshness("some_file.md")
        ts2 = mem.get_last_verified("some_file.md")
        assert ts2 != ts1  # Should be different (later timestamp)

    def test_get_last_verified_returns_none_for_unverified(self, mem):
        ts = mem.get_last_verified("never_verified.md")
        assert ts is None

    def test_verify_identity_legacy(self, mem):
        """Legacy verify_identity() should work."""
        mem.verify_identity()
        ts = mem.get_identity_last_verified()
        assert ts is not None

    def test_freshness_persists_across_instances(self, drive_root):
        mem1 = Memory(drive_root=drive_root)
        mem1.verify_freshness("test_file.md")
        ts1 = mem1.get_last_verified("test_file.md")

        # New instance should see the same timestamp
        mem2 = Memory(drive_root=drive_root)
        ts2 = mem2.get_last_verified("test_file.md")
        assert ts1 == ts2


class TestFileLocking:
    """File lock acquire/release."""

    def test_acquire_and_release(self, drive_root):
        lock_path = drive_root / "locks" / "test.lock"
        fd = _acquire_file_lock(lock_path)
        assert fd is not None
        _release_file_lock(lock_path, fd)

    def test_release_with_none_fd(self, drive_root):
        """Releasing with None fd should not crash."""
        lock_path = drive_root / "locks" / "test.lock"
        _release_file_lock(lock_path, None)  # Should not raise

    def test_concurrent_lock_acquisition(self, drive_root):
        """Second lock acquisition should wait (or return different fd)."""
        lock_path = drive_root / "locks" / "concurrent.lock"
        fd1 = _acquire_file_lock(lock_path, timeout_sec=1.0)
        assert fd1 is not None
        # Try to acquire again — should either wait or fail gracefully
        fd2 = _acquire_file_lock(lock_path, timeout_sec=0.5)
        # fd2 might be None (timeout) or a valid fd (if lock is re-entrant)
        if fd2 is not None:
            _release_file_lock(lock_path, fd2)
        _release_file_lock(lock_path, fd1)


class TestEnsureFiles:
    """ensure_files() creates all required memory files."""

    def test_ensure_files_creates_scratchpad(self, mem):
        mem.ensure_files()
        assert mem.scratchpad_path().exists()
        assert mem.identity_path().exists()

    def test_ensure_files_idempotent(self, mem):
        mem.ensure_files()
        content1 = mem.load_scratchpad()
        mem.ensure_files()
        content2 = mem.load_scratchpad()
        # Should not overwrite existing files
        assert content1 == content2


class TestConsolidate:
    """Memory consolidation (may fail gracefully if no events)."""

    def test_consolidate_returns_dict(self, mem):
        result = mem.consolidate(limit=5)
        assert isinstance(result, dict)
        assert "status" in result

    def test_consolidate_handles_missing_events(self, mem):
        """Should not crash if no events file exists."""
        result = mem.consolidate(limit=5)
        # Either success (empty events) or error — both are valid responses
        assert result["status"] in ("success", "error")


class TestDefaultContent:
    """Default scratchpad/identity content is meaningful."""

    def test_default_scratchpad_has_header(self, mem):
        content = mem.load_scratchpad()
        assert "# Scratchpad" in content or "scratchpad" in content.lower()

    def test_default_identity_has_content(self, mem):
        content = mem.load_identity()
        assert len(content) > 50  # Not just empty
