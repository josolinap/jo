import pathlib
import pytest
from ouroboros.tools.registry import ToolRegistry


@pytest.fixture
def registry():
    return ToolRegistry(repo_dir=pathlib.Path("."), drive_root=pathlib.Path.home() / ".jo_data")


class TestToolValidation:
    def test_valid_args(self, registry):
        result = registry.execute("switch_model", {"effort": "high"})
        assert "OK" in result or "switching" in result

    def test_unknown_argument(self, registry):
        result = registry.execute("switch_model", {"unknown_param": "value"})
        assert "Unknown arguments" in result
        assert "unknown_param" in result

    def test_missing_required(self, registry):
        result = registry.execute("get_task_result", {})
        assert "Missing required" in result
        assert "task_id" in result

    def test_invalid_enum(self, registry):
        result = registry.execute("switch_model", {"effort": "invalid_effort"})
        assert "Invalid value" in result
        assert "effort" in result

    def test_type_mismatch_string(self, registry):
        result = registry.execute("switch_model", {"model": 123})
        assert "Invalid type" in result
        assert "model" in result

    def test_type_mismatch_boolean(self, registry):
        result = registry.execute("switch_model", {"model": True})
        assert "Invalid type" in result

    def test_valid_enum(self, registry):
        for effort in ["low", "medium", "high", "xhigh"]:
            result = registry.execute("switch_model", {"effort": effort})
            assert "OK" in result or "switching" in result

    def test_no_args(self, registry):
        result = registry.execute("switch_model", {})
        assert "OK" in result or "switching" in result or "Current" in result
