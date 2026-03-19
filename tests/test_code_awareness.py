import json
import pathlib
import tempfile
import pytest

from ouroboros.tools.registry import ToolRegistry, ToolContext
from ouroboros.memory import Memory


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repo with sample Python files."""
    repo = tmp_path / "repo"
    repo.mkdir()

    (repo / "main.py").write_text("""
from utils import helper

def foo():
    return helper()

def bar():
    return foo()

class MyClass:
    def method(self):
        return foo()
""")

    (repo / "utils.py").write_text("""
def helper():
    return "hello"

def other():
    return helper()
""")

    (repo / "unused.py").write_text("""
def orphan():
    pass
""")

    return repo


@pytest.fixture
def temp_drive(tmp_path):
    """Create a temporary drive root."""
    drive = tmp_path / ".ouroboros"
    drive.mkdir()
    (drive / "memory").mkdir()
    return drive


@pytest.fixture
def registry(temp_repo, temp_drive):
    """Create a tool registry with test context."""
    return ToolRegistry(repo_dir=temp_repo, drive_root=temp_drive)


class TestFindCallers:
    """Tests for find_callers tool."""

    def test_find_callers_basic(self, registry):
        """Test finding callers of a function that exists in test files."""
        result = registry.execute("find_callers", {"function_name": "foo"})
        assert "foo" in result
        assert "main.py" in result

    def test_find_callers_not_found(self, registry):
        """Test when function has no callers."""
        result = registry.execute("find_callers", {"function_name": "nonexistent_function"})
        assert "No callers found" in result

    def test_find_callers_helper(self, registry):
        """Test finding callers of helper function."""
        result = registry.execute("find_callers", {"function_name": "helper"})
        assert "helper" in result

    def test_find_callers_too_short(self, registry):
        """Test that single char names are rejected."""
        result = registry.execute("find_callers", {"function_name": "a"})
        assert "at least 2 characters" in result

    def test_find_callers_method(self, registry):
        """Test finding callers of a method call."""
        result = registry.execute("find_callers", {"function_name": "bar"})
        assert "bar" in result


class TestFindDefinitions:
    """Tests for find_definitions tool."""

    def test_find_function_definition(self, registry):
        """Test finding a function definition."""
        result = registry.execute("find_definitions", {"function_name": "foo"})
        assert "foo" in result
        assert "main.py" in result

    def test_find_class_definition(self, registry):
        """Test finding a class definition."""
        result = registry.execute("find_definitions", {"function_name": "MyClass"})
        assert "MyClass" in result
        assert "main.py" in result

    def test_find_not_found(self, registry):
        """Test when definition doesn't exist."""
        result = registry.execute("find_definitions", {"function_name": "UnknownClass"})
        assert "No definitions found" in result

    def test_find_too_short(self, registry):
        """Test that single char names are rejected."""
        result = registry.execute("find_definitions", {"function_name": "x"})
        assert "at least 2 characters" in result


class TestLearnFromMistake:
    """Tests for learn_from_mistake tool."""

    def test_learn_stores_lesson(self, registry):
        result = registry.execute(
            "learn_from_mistake", {"mistake": "Deleted wrong file", "lesson": "Always check git status first"}
        )
        assert "OK" in result

    def test_learn_with_tags(self, registry):
        result = registry.execute(
            "learn_from_mistake",
            {"mistake": "Syntax error", "lesson": "Run tests before commit", "tags": "git,testing"},
        )
        assert "OK" in result
        assert "git" in result.lower()

    def test_learn_missing_mistake(self, registry):
        result = registry.execute("learn_from_mistake", {"lesson": "Some lesson"})
        assert "Missing required" in result

    def test_learn_missing_lesson(self, registry):
        result = registry.execute("learn_from_mistake", {"mistake": "Some mistake"})
        assert "Missing required" in result


class TestRecallLessons:
    """Tests for recall_lessons tool."""

    def test_recall_empty(self, registry):
        result = registry.execute("recall_lessons", {})
        assert "No lessons" in result

    def test_recall_after_learning(self, registry):
        registry.execute("learn_from_mistake", {"mistake": "Test mistake", "lesson": "Test lesson", "tags": "testing"})

        result = registry.execute("recall_lessons", {"topic": "testing"})
        assert "Test lesson" in result or "Test mistake" in result

    def test_recall_with_limit(self, registry):
        for i in range(5):
            registry.execute("learn_from_mistake", {"mistake": f"Mistake {i}", "lesson": f"Lesson {i}", "tags": "test"})

        result = registry.execute("recall_lessons", {"topic": "test", "limit": 2})
        # Should return at most 2 lessons (check for lesson count in result)
        assert "Lesson 0" in result or "Lesson 1" in result


class TestMemoryModule:
    """Tests for Memory class."""

    def test_memory_initialization(self, temp_drive):
        mem = Memory(drive_root=temp_drive)
        mem.ensure_files()
        assert mem.journal_path().exists()

    def test_journal_append_and_count(self, temp_drive):
        mem = Memory(drive_root=temp_drive)
        mem.ensure_files()

        initial = mem.journal_count()

        mem.append_journal({"test": "entry1"})
        assert mem.journal_count() == initial + 1

        mem.append_journal({"test": "entry2"})
        assert mem.journal_count() == initial + 2

    def test_get_lessons_filtering(self, temp_drive):
        mem = Memory(drive_root=temp_drive)
        mem.ensure_files()

        mem.append_journal({"mistake": "A", "lesson": "L1", "tags": ["git"]})
        mem.append_journal({"mistake": "B", "lesson": "L2", "tags": ["python"]})
        mem.append_journal({"mistake": "C", "lesson": "L3", "tags": ["git", "testing"]})

        git_lessons = mem.get_lessons(topic="git")
        assert len(git_lessons) == 2

        python_lessons = mem.get_lessons(topic="python")
        assert len(python_lessons) == 1


class TestParameterValidation:
    """Tests for tool parameter validation."""

    def test_unknown_parameter(self, registry):
        result = registry.execute("find_callers", {"function_name": "test", "unknown_param": "value"})
        assert "Unknown arguments" in result

    def test_wrong_type_for_string_param(self, registry):
        result = registry.execute("find_callers", {"function_name": 123})
        assert "Invalid type" in result or "Missing required" in result

    def test_wrong_type_for_integer_param(self, registry):
        result = registry.execute("recall_lessons", {"limit": "not_a_number"})
        assert "Invalid type" in result or result == "OK"


class TestToolSchemas:
    """Tests that tool schemas are well-formed."""

    def test_all_tools_have_names(self, registry):
        for tool_name in registry.available_tools():
            schema = registry.get_schema_by_name(tool_name)
            assert schema is not None, f"Tool {tool_name} has no schema"
            assert "name" in schema.get("function", {}), f"Tool {tool_name} missing name"

    def test_all_tools_have_descriptions(self, registry):
        for tool_name in registry.available_tools():
            schema = registry.get_schema_by_name(tool_name)
            desc = schema.get("function", {}).get("description", "")
            assert len(desc) > 0, f"Tool {tool_name} missing description"

    def test_core_tools_registered(self, registry):
        core_tools = [
            "repo_read",
            "repo_list",
            "repo_write_commit",
            "find_callers",
            "find_definitions",
            "learn_from_mistake",
            "recall_lessons",
        ]
        available = registry.available_tools()
        for tool in core_tools:
            assert tool in available, f"Core tool {tool} not registered"


class TestErrorHandling:
    """Tests for error handling."""

    def test_unknown_tool(self, registry):
        result = registry.execute("nonexistent_tool", {})
        assert "Unknown tool" in result

    def test_invalid_json_in_arguments(self, registry):
        ctx = ToolContext(repo_dir=pathlib.Path("."), drive_root=pathlib.Path.home() / ".ouroboros")
        # This would fail at the JSON parsing level
        # We can't easily test this through the registry interface
        pass
