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
    assert tasks[0]["id"] == "ghf"


def test_github_inbox_keeps_claim_when_close_fails(tmp_path, monkeypatch):
    _enable_inbox(monkeypatch)
    inbox = GitHubInbox(tmp_path)
    inbox._state["claims"] = {
        "15": {"task_id": "ghf", "claimed_at": 1, "title": "[JO] Evolve"}
    }
    inbox._save_state()

    calls = []

    class Response:
        pass

    def request(method, path, **kwargs):
        calls.append((method, path, kwargs))
        return Response() if method == "POST" else None

    inbox._request = request
    assert inbox.complete("ghf", "done") is False
    assert "15" in inbox._state["claims"]
    assert calls[0][0] == "POST"


def test_github_inbox_removes_claim_after_comment_and_close(tmp_path, monkeypatch):
    _enable_inbox(monkeypatch)
    inbox = GitHubInbox(tmp_path)
    inbox._state["claims"] = {
        "15": {"task_id": "ghf", "claimed_at": 1, "title": "[JO] Evolve"}
    }

    class Response:
        pass

    inbox._request = lambda method, path, **kwargs: Response()
    assert inbox.complete("ghf", "done") is True
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
