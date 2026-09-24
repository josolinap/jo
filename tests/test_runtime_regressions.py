"""Regression tests for the ChatGPT -> Jo mailbox and free-only model routing."""

from __future__ import annotations

import json

import pytest

from ouroboros.auto_system import get_model_for_task
from ouroboros.github_inbox import GitHubInbox
from ouroboros.llm import LLMClient


def _enable_inbox(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    monkeypatch.setenv("GITHUB_USER", "josolinap")
    monkeypatch.setenv("GITHUB_REPO", "jo")
    monkeypatch.setenv("JO_GITHUB_INBOX_ENABLED", "1")


def test_github_inbox_marks_evolve_issue_as_evolution(tmp_path, monkeypatch):
    _enable_inbox(monkeypatch)
    inbox = GitHubInbox(tmp_path)

    class Response:
        def json(self):
            return [{
                "number": 15,
                "title": "[JO] Evolve",
                "body": "Improve yourself.",
                "user": {"login": "josolinap"},
                "html_url": "https://github.com/josolinap/jo/issues/15",
            }]

    inbox._request = lambda method, path, **kwargs: Response()
    tasks = inbox.poll()

    assert len(tasks) == 1
    assert tasks[0]["type"] == "evolution"
    assert tasks[0]["id"].startswith("ghf-")
    assert len(tasks[0]["id"]) == 12


def test_github_inbox_keeps_claim_when_close_fails(tmp_path, monkeypatch):
    _enable_inbox(monkeypatch)
    inbox = GitHubInbox(tmp_path)
    inbox._state["claims"] = {
        "15": {"task_id": "ghf-abcdef12", "claimed_at": 1, "title": "[JO] Evolve"}
    }
    inbox._save_state()

    calls = []

    class Response:
        pass

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return Response() if method == "POST" else None

    inbox._request = request
    assert inbox.complete("ghf-abc12345", "done") is False
    assert "15" in inbox._state["claims"]
    assert inbox._state["claims"]["15"]["status"] == "pending_close"
    assert inbox._state["claims"]["15"]["completion_posted"] is True
    assert calls[0][0] == "POST"

    def retry_request(method, path, **kwargs):
        if method == "GET":
            class GetResponse:
                def json(self):
                    return [{
                        "number": 15,
                        "title": "[JO] Evolve",
                        "body": "Improve yourself.",
                        "user": {"login": "josolinap"},
                        "html_url": "https://github.com/josolinap/jo/issues/15",
                    }]
            return GetResponse()
        class Response:
            pass
        return Response()

    inbox._request = retry_request
    inbox.poll()
    assert "15" not in inbox._state["claims"]


def test_github_inbox_removes_claim_after_comment_and_close(tmp_path, monkeypatch):
    _enable_inbox(monkeypatch)
    inbox = GitHubInbox(tmp_path)
    inbox._state["claims"] = {
        "15": {"task_id": "ghf", "claimed_at": 1, "title": "[JO] Evolve"}
    }

    class Response:
        pass

    inbox._request = lambda method, path, **kwargs: Response()
    assert inbox.complete("ghf-abcdef12", "done") is True
    assert "15" not in inbox._state["claims"]


def test_free_model_router_never_selects_paid_models():
    for text in ("inspect architecture", "debug and optimize the codebase", "evolution review"):
        model, _ = get_model_for_task(text, 10)
        assert ":free" in model or model == "openrouter/free"


def test_llm_records_provider_error(tmp_path, monkeypatch):
    client = LLMClient(api_key="test-key")

    def fail(*args, **kwargs):
        raise RuntimeError("simulated upstream failure")

    monkeypatch.setattr(client, "_chat_openrouter", fail)
    monkeypatch.delenv("DOUBLEWORD_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_BASE_URL", raising=False)

    with pytest.raises(RuntimeError):
        client.chat([{"role": "user", "content": "test"}], "openrouter/free")

    assert "simulated upstream failure" in client.last_error
    assert client.last_error.startswith("RuntimeError:")


def test_llm_detects_empty_provider_response(monkeypatch):
    client = LLMClient(api_key="test-key")

    monkeypatch.setattr(client, "_chat_openrouter", lambda *args, **kwargs: ({}, {}))
    monkeypatch.delenv("DOUBLEWORD_API_KEY", raising=False)
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    monkeypatch.delenv("LOCAL_BASE_URL", raising=False)

    with pytest.raises(ValueError):
        client.chat([{"role": "user", "content": "test"}], "openrouter/free")

    assert "empty response" in client.last_error.lower()


def test_budget_router_defaults_are_free():
    from ouroboros.budget_router import BudgetAwareRouter, ModelTier

    router = BudgetAwareRouter(__import__("pathlib").Path("."))
    assert router._default_model == "openrouter/free"
    assert router._model_map[ModelTier.FAST] == "openrouter/free"
    assert router._model_map[ModelTier.BALANCED].endswith(":free")
    assert router._model_map[ModelTier.DEEP].endswith(":free")


def test_complexity_router_defaults_are_free(monkeypatch):
    monkeypatch.delenv("OUROBOROS_MODEL_LIGHT", raising=False)
    monkeypatch.delenv("OUROBOROS_MODEL", raising=False)
    monkeypatch.delenv("OUROBOROS_MODEL_CODE", raising=False)

    from ouroboros.complexity_router import ModelRouter, ComplexityTier

    router = ModelRouter()
    for tier in ComplexityTier:
        model = router._models[tier].name
        assert model == "openrouter/free" or model.endswith(":free")


def test_switch_model_blocks_paid_override(monkeypatch):
    from unittest.mock import MagicMock
    from ouroboros.tools.control import _switch_model
    from ouroboros.llm import LLMClient

    monkeypatch.setattr(LLMClient, "available_models", lambda self: [
        "openrouter/free",
        "poolside/laguna-s-2.1:free",
    ])
    ctx = MagicMock()
    assert "paid/non-free model blocked" in _switch_model(ctx, model="anthropic/claude-sonnet-4")


def test_multi_model_review_blocks_paid_models():
    import asyncio
    from ouroboros.tools.review import _multi_model_review_async

    result = asyncio.run(
        _multi_model_review_async(
            content="print('ok')",
            prompt="Find errors",
            models=["anthropic/claude-sonnet-4"],
            ctx=None,
        )
    )
    assert "non-free review models" in result["error"]


def test_multi_model_review_accepts_free_models_without_network(monkeypatch):
    import asyncio
    from ouroboros.tools.review import _multi_model_review_async

    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    result = asyncio.run(
        _multi_model_review_async(
            content="print('ok')",
            prompt="Find errors",
            models=["openrouter/free"],
            ctx=None,
        )
    )
    assert "OPENROUTER_API_KEY not set" in result["error"]


def test_default_vision_model_is_free():
    from ouroboros.tools import vision

    assert vision._DEFAULT_VLM_MODEL == "inclusionai/ling-3.0-flash-vl:free"


def test_no_placeholder_python_stubs():
    from pathlib import Path

    suspicious = []
    for path in Path('.').rglob('*.py'):
        if any(part in {'.git', 'archive', '__pycache__'} for part in path.parts):
            continue
        try:
            text = path.read_text(encoding='utf-8').lstrip()
        except UnicodeDecodeError:
            continue
        if text.startswith('```') or text in {'New file content', 'Added a brief summary at the start'}:
            suspicious.append(str(path))
    assert not suspicious, f'Placeholder/non-Python Python files found: {suspicious}'
