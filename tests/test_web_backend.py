"""Tests for the Jo web backend contract (server/app.py).

Exercises /health, /v1/status, /v1/models, /v1/chat and /v1/chat/stream via
FastAPI's TestClient. The LLM path is stubbed with monkeypatch so the tests
run without OmniRoute, network access, or environment configuration.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from server import app as server_app


@pytest.fixture()
def client() -> TestClient:
    return TestClient(server_app.app)


@pytest.fixture(autouse=True)
def _no_omniroute_env(monkeypatch):
    for var in (
        "OMNIROUTE_BASE_URL",
        "OMNIROUTE_MODEL",
        "OMNIROUTE_API_KEY",
        "JO_WEB_USE_AGENT",
        "JO_WEB_ENABLE_MODEL_PROBE",
    ):
        monkeypatch.delenv(var, raising=False)


def _stub_llm(monkeypatch, text="Hello from Jo!", provider="omniroute", model="test-model"):
    def fake_run(message, history=None, requested_model=None):
        return text, {"provider": provider, "model": model}

    monkeypatch.setattr(server_app, "_run_via_llm", fake_run)


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert "version" in d
    assert set(d.get("endpoints", [])) >= {"/v1/chat", "/v1/chat/stream", "/health", "/v1/status"}


def test_status_reports_web_chat_mode(client):
    d = client.get("/v1/status").json()
    assert d["status"] == "ok"
    assert d.get("provider") == "omniroute"
    assert isinstance(d.get("web_agent_mode"), bool)
    assert d.get("web_chat_path") in ("agent", "llm")
    assert isinstance(d.get("tools_exposed_to_model"), bool)
    assert d.get("web_agent_mode") == d.get("tools_exposed_to_model")
    assert isinstance(d.get("tools_note"), str) and d.get("tools_note")


def test_models_includes_auto(client):
    d = client.get("/v1/models").json()
    ids = [m["id"] for m in d["models"]]
    assert ids and ids[0] == "auto"
    assert "default" in d and "diagnostics" in d


def test_chat_empty_message(client):
    r = client.post("/v1/chat", json={"message": "   "})
    assert r.status_code == 200
    assert "Send a message" in r.json()["response"]


def test_chat_uses_llm_path_and_records_session(client, monkeypatch):
    _stub_llm(monkeypatch)
    r = client.post("/v1/chat", json={"message": "hi there"})
    assert r.status_code == 200
    d = r.json()
    assert d["response"] == "Hello from Jo!"
    assert d["provider"] == "omniroute"
    assert d["model"] == "test-model"
    assert d["session_id"].startswith("web_")
    sess = server_app._SESSIONS[d["session_id"]]
    assert len(sess) == 2  # user + assistant recorded


def test_chat_accepts_history_and_model(client, monkeypatch):
    seen = {}

    def fake_run(message, history=None, requested_model=None):
        seen["history"] = history
        seen["requested_model"] = requested_model
        return "ok", {"provider": "omniroute", "model": "m"}

    monkeypatch.setattr(server_app, "_run_via_llm", fake_run)
    hist = [
        {"role": "user", "content": "earlier question"},
        {"role": "assistant", "content": "earlier answer"},
    ]
    r = client.post(
        "/v1/chat",
        json={"message": "next", "history": hist, "model": "auto", "session_id": "web_custom"},
    )
    assert r.status_code == 200
    assert r.json()["response"] == "ok"
    assert seen["requested_model"] == "auto"
    assert any(m.get("content") == "earlier question" for m in seen["history"])


def test_chat_fallback_when_no_provider(client):
    r = client.post("/v1/chat", json={"message": "hello?"})
    assert r.status_code == 200
    resp = r.json()["response"]
    assert resp
    assert "OmniRoute" in resp
    assert r.json()["provider"] == "fallback"


def test_chat_stream_sse_shape(client, monkeypatch):
    _stub_llm(monkeypatch, text="streaming words here")
    events = []
    with client.stream("POST", "/v1/chat/stream", json={"message": "hi", "session_id": "web_stream1"}) as r:
        assert r.status_code == 200
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[len("data: "):]))
    assert any(e.get("delta") for e in events)
    done = [e for e in events if e.get("done")]
    assert len(done) == 1
    assert done[0]["response"] == "streaming words here"
    assert done[0]["session_id"] == "web_stream1"


def test_stream_error_event_when_generate_raises(client, monkeypatch):
    with mock.patch.object(server_app, "generate_response", side_effect=RuntimeError("boom")):
        with client.stream("POST", "/v1/chat/stream", json={"message": "hi"}) as r:
            events = [
                json.loads(line[len("data: "):])
                for line in r.iter_lines()
                if line.startswith("data: ")
            ]
    assert any(e.get("error") for e in events)


def test_floorplan_endpoint(client):
    d = client.get("/v1/floorplan").json()
    assert set(d) >= {"summary", "parts", "connections", "graph", "architecture", "generatedAt"}
    ids = {p["id"] for p in d["parts"]}
    labels = {p["label"] for p in d["parts"]}
    assert {"gui", "server", "ouroboros"} <= ids
    assert {"Jo Web GUI", "Jo Web Backend", "Ouroboros — Jo's agent core"} <= labels
    assert d["connections"], "expected graph connections"
    assert d["summary"], "expected a project summary"


def test_chat_system_prompt_includes_floorplan_map(client):
    msgs = server_app._build_messages("hello", [])
    assert msgs[0]["role"] == "system"
    assert "Floorplan" in msgs[0]["content"]
    assert any(p in msgs[0]["content"] for p in ("Jo Web GUI", "Jo Web Backend", "Ouroboros"))
