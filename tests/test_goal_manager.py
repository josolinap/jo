"""Tests for ouroboros/goal_manager.py — Goal pursuit and /loop mechanism."""
import json
import pathlib
import pytest
import tempfile

import ouroboros.goal_manager as gm
from ouroboros.goal_manager import (
    Goal, goal_set, goal_resume, goal_check_progress,
    goal_complete_subtask, goal_abandon, goal_status,
)


@pytest.fixture
def temp_memory(tmp_path, monkeypatch):
    """Redirect memory files to temp directory."""
    monkeypatch.setattr(gm, "TASK_FILE", tmp_path / "TASK.md")
    monkeypatch.setattr(gm, "GOAL_HISTORY", tmp_path / "goal_history.jsonl")
    return tmp_path


class TestGoalSet:
    """Setting goals."""

    def test_set_goal_creates_task_file(self, temp_memory):
        result = goal_set(
            description="Fix all bare except blocks",
            done_condition="grep finds 0 bare except: in ouroboros/",
        )
        assert "✓ Goal set" in result
        assert gm.TASK_FILE.exists()

    def test_set_goal_with_subtasks(self, temp_memory):
        result = goal_set(
            description="Improve test coverage",
            done_condition="all core modules have tests",
            subtasks=["test memory.py", "test loop.py", "test agent.py"],
        )
        assert "3" in result  # 3 subtasks

    def test_set_goal_replaces_existing(self, temp_memory):
        goal_set(description="First goal", done_condition="condition 1")
        goal_set(description="Second goal", done_condition="condition 2")
        # Should have abandoned the first
        assert gm.GOAL_HISTORY.exists()
        history = gm.GOAL_HISTORY.read_text()
        assert "First goal" in history
        assert "abandoned" in history

    def test_set_goal_stores_metadata(self, temp_memory):
        goal_set(description="Test goal", done_condition="test condition")
        from ouroboros.goal_manager import _read_task_file
        data = _read_task_file()
        assert data["description"] == "Test goal"
        assert data["done_condition"] == "test condition"
        assert data["status"] == "active"
        assert data["attempts"] == 0


class TestGoalResume:
    """Loading goals at session start."""

    def test_resume_no_goal(self, temp_memory):
        result = goal_resume()
        assert "No active goal" in result

    def test_resume_active_goal(self, temp_memory):
        goal_set(description="Test goal", done_condition="test condition")
        result = goal_resume()
        assert "Test goal" in result
        assert "attempt 1" in result

    def test_resume_increments_attempts(self, temp_memory):
        goal_set(description="Test goal", done_condition="test condition")
        goal_resume()  # attempt 1
        goal_resume()  # attempt 2
        result = goal_resume()  # attempt 3
        assert "attempt 3" in result

    def test_resume_shows_subtasks(self, temp_memory):
        goal_set(
            description="Test goal",
            done_condition="done",
            subtasks=["task 1", "task 2"],
        )
        result = goal_resume()
        assert "task 1" in result
        assert "task 2" in result

    def test_resume_shows_progress_log(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        goal_check_progress("Attempted fix, not done yet")
        result = goal_resume()
        assert "Attempted fix" in result


class TestGoalCheckProgress:
    """Recording progress and checking done-condition."""

    def test_record_progress(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        result = goal_check_progress("Working on it", is_done=False)
        assert "Progress recorded" in result

    def test_complete_goal(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        result = goal_check_progress("All done!", is_done=True)
        assert "completed" in result

    def test_stuck_after_max_attempts(self, temp_memory):
        # Set goal, then manually set max_attempts to 2 via the task file
        goal_set(description="Test goal", done_condition="done")
        from ouroboros.goal_manager import _read_task_file, _write_task_file, Goal
        data = _read_task_file()
        data["max_attempts"] = 2
        goal = Goal(**data)
        _write_task_file(goal)
        
        goal_resume()  # attempt 1
        goal_check_progress("Not done")
        goal_resume()  # attempt 2
        result = goal_check_progress("Still not done")
        assert "stuck" in result.lower()

    def test_progress_logged_to_notes(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        goal_check_progress("First attempt")
        from ouroboros.goal_manager import _read_task_file
        data = _read_task_file()
        assert len(data["notes"]) == 1
        assert "First attempt" in data["notes"][0]


class TestGoalCompleteSubtask:
    """Marking subtasks as done."""

    def test_complete_subtask(self, temp_memory):
        goal_set(
            description="Test goal",
            done_condition="done",
            subtasks=["task 1", "task 2"],
        )
        result = goal_complete_subtask("task 1")
        assert "✓" in result
        assert "1 subtasks remaining" in result

    def test_complete_all_subtasks(self, temp_memory):
        goal_set(
            description="Test goal",
            done_condition="done",
            subtasks=["task 1", "task 2"],
        )
        goal_complete_subtask("task 1")
        goal_complete_subtask("task 2")
        result = goal_status()
        assert "2/2" in result

    def test_complete_nonexistent_subtask(self, temp_memory):
        goal_set(description="Test goal", done_condition="done", subtasks=["task 1"])
        result = goal_complete_subtask("nonexistent")
        # Should still work (idempotent)
        assert "✓" in result


class TestGoalAbandon:
    """Abandoning goals."""

    def test_abandon_goal(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        result = goal_abandon(reason="No longer relevant")
        assert "abandoned" in result
        assert "No longer relevant" in result

    def test_abandon_records_history(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        goal_abandon(reason="Testing")
        history = gm.GOAL_HISTORY.read_text()
        assert "Test goal" in history
        assert "Testing" in history

    def test_abandon_no_goal(self, temp_memory):
        result = goal_abandon(reason="nothing to abandon")
        assert "No active goal" in result


class TestGoalStatus:
    """Checking goal status."""

    def test_status_no_goal(self, temp_memory):
        result = goal_status()
        assert "No active goal" in result

    def test_status_active_goal(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        result = goal_status()
        assert "Test goal" in result
        assert "active" in result

    def test_status_shows_attempt_count(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        goal_resume()
        result = goal_status()
        assert "1/" in result  # 1 attempt out of max

    def test_status_does_not_increment(self, temp_memory):
        """goal_status should NOT increment the attempt counter (unlike goal_resume)."""
        goal_set(description="Test goal", done_condition="done")
        goal_status()
        goal_status()
        from ouroboros.goal_manager import _read_task_file
        data = _read_task_file()
        assert data["attempts"] == 0  # Unchanged


class TestTaskFileFormat:
    """TASK.md file format and persistence."""

    def test_task_file_is_markdown(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        content = gm.TASK_FILE.read_text()
        assert content.startswith("# Active Task")
        assert "## Goal" in content
        assert "## Goal Data (JSON)" in content

    def test_task_file_contains_json(self, temp_memory):
        goal_set(description="Test goal", done_condition="done")
        content = gm.TASK_FILE.read_text()
        assert "```json" in content
        # JSON should be parseable
        import re
        match = re.search(r'```json\n(.*?)\n```', content, re.DOTALL)
        assert match
        data = json.loads(match.group(1))
        assert data["description"] == "Test goal"

    def test_task_file_shows_subtask_status(self, temp_memory):
        goal_set(
            description="Test goal",
            done_condition="done",
            subtasks=["task 1", "task 2"],
        )
        goal_complete_subtask("task 1")
        content = gm.TASK_FILE.read_text()
        assert "✓ task 1" in content
        assert "○ task 2" in content
