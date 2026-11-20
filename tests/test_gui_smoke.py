"""End-to-end smoke test for the Jo Web GUI ↔ backend wiring.

Starts a real uvicorn backend (server/app.py) and serves gui/ with
`python -m http.server`, then drives a real Chromium through Playwright:

- opens the GUI, sets the API base in Settings to the real backend,
- stubs the backend contract via page routes (health + models + SSE stream),
- sends a chat message and asserts the GUI renders the backend's reply,
- asserts the status card surfaces the backend's web chat mode/tools flags.
"""

from __future__ import annotations

import importlib
import os
import pathlib
import subprocess
import sys
import time
import urllib.request

import pytest

pytest.importorskip("playwright")
sync_playwright = importlib.import_module("playwright.sync_api").sync_playwright

ROOT = pathlib.Path(__file__).resolve().parents[1]
GUI_DIR = ROOT / "gui"
GUI_PORT = 8136
BACKEND_PORT = 8137
BACKEND_URL = f"http://127.0.0.1:{BACKEND_PORT}"
GUI_URL = f"http://127.0.0.1:{GUI_PORT}"
STUB_REPLY = "Hello from the stub backend!"


def _wait_url(url: str, timeout: float = 40.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return
        except Exception:
            pass
        time.sleep(0.5)
    raise AssertionError(f"timed out waiting for {url}")


@pytest.fixture(scope="module")
def servers():
    env = dict(os.environ)
    env["PYTHONUNBUFFERED"] = "1"
    env["PYTHONPATH"] = str(ROOT) + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    for var in ("OMNIROUTE_BASE_URL", "OMNIROUTE_MODEL", "OMNIROUTE_API_KEY", "JO_WEB_USE_AGENT"):
        env.pop(var, None)
    procs = [
        subprocess.Popen(
            [sys.executable, "-m", "http.server", str(GUI_PORT), "--directory", str(GUI_DIR)],
            env=env,
        ),
        subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "server.app:app", "--host", "127.0.0.1", "--port", str(BACKEND_PORT)],
            cwd=ROOT,
            env=env,
        ),
    ]
    try:
        _wait_url(f"{GUI_URL}/index.html")
        _wait_url(f"{BACKEND_URL}/health")
        yield
    finally:
        for p in procs:
            p.terminate()
        for p in procs:
            try:
                p.wait(timeout=10)
            except Exception:
                p.kill()


def _stub_health(web_chat_path: str, tools_exposed: bool) -> dict:
    note = (
        "Agent chat path enabled (Jo tools may be available via agent workflow)."
        if tools_exposed
        else "Lightweight chat path: model calls do not include Jo tool schemas; selected models have no direct tool access in this mode."
    )
    return {
        "status": "ok",
        "provider": "omniroute",
        "model": "auto",
        "configured": True,
        "keys": {"omniroute_configured": True, "omniroute": True},
        "omniroute_reachable": True,
        "reasons": ["omniroute_available"],
        "model_probe": {"ok": True, "model": "test-model", "latency_ms": 5, "cached": True},
        "omniroute": {
            "configured": True,
            "reachable": True,
            "base_url": "http://stub",
            "model_count": 1,
            "models_sample": ["test-model"],
        },
        "web_agent_mode": tools_exposed,
        "web_chat_path": web_chat_path,
        "tools_exposed_to_model": tools_exposed,
        "tools_note": note,
    }


def _install_routes(page, web_chat_path: str = "llm", tools_exposed: bool = False):
    def handler(route):
        url = route.request.url
        if "/v1/chat/stream" in url:
            body = (
                'data: {"delta": "Hello ", "session_id": "web_stub1"}\n\n'
                'data: {"delta": "from the stub backend!"}\n\n'
                'data: {"done": true, "response": "' + STUB_REPLY + '", '
                '"session_id": "web_stub1", "provider": "omniroute", "model": "auto", "elapsed_ms": 12}\n\n'
            )
            route.fulfill(status=200, headers={"Content-Type": "text/event-stream"}, body=body)
        elif url.endswith("/v1/models"):
            route.fulfill(
                json={
                    "models": [{"id": "auto", "provider": "auto", "label": "Auto (recommended)"}],
                    "default": "auto",
                    "diagnostics": {},
                }
            )
        elif url.endswith("/health") or url.endswith("/v1/status"):
            route.fulfill(json=_stub_health(web_chat_path, tools_exposed))
        elif "/v1/chat" in url:
            route.fulfill(
                json={
                    "response": STUB_REPLY,
                    "session_id": "web_stub1",
                    "provider": "omniroute",
                    "model": "auto",
                    "elapsed_ms": 12,
                }
            )
        else:
            route.fallback()

    page.route("**/*", handler)


def _bubble_has_reply() -> str:
    return (
        "() => {"
        " const el = document.querySelector('#chat-collection .message-assistant .bubble');"
        " return !!el && el.textContent.includes('" + STUB_REPLY + "');"
        "}"
    )


def test_gui_chat_roundtrip_through_backend(servers):
    """GUI posts to the real backend contract; the stubbed stream reply renders in the UI."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        requested = []
        page.on("request", lambda req: requested.append(req.url))
        _install_routes(page, web_chat_path="llm", tools_exposed=False)
        try:
            page.goto(GUI_URL + "/", wait_until="load")
            page.wait_for_selector("#chat-input", timeout=15000)

            # Open Settings (Ctrl+, is the GUI's shortcut — see gui/app.js keydown handler)
            # and point it at the real backend.
            page.keyboard.down("Control")
            page.keyboard.press(",")
            page.keyboard.up("Control")
            page.wait_for_selector("#api-base", state="visible", timeout=15000)
            # The settings panel surfaces the Floorplan map link.
            page.wait_for_selector("#floorplan-link", state="visible", timeout=15000)
            assert "floorplan" in (page.locator("#floorplan-link").get_attribute("href") or "")
            page.fill("#api-base", BACKEND_URL)
            page.click("#settings-refresh")
            page.wait_for_function(
                "document.getElementById('backend-status').textContent.includes('Status: online') && "
                "document.getElementById('backend-status').textContent.includes('llm (text only)')",
                timeout=15000,
            )
            page.click("#settings-close")

            # Send a chat message through the wired transport.
            page.fill("#chat-input", "Hello from the GUI smoke test")
            page.click("#chat-send")
            page.wait_for_function(_bubble_has_reply(), timeout=15000)

            assert any("/v1/chat/stream" in u for u in requested)
        finally:
            browser.close()


def test_gui_surfaces_web_chat_mode_and_tools_flags(servers):
    """The status card shows the backend's web chat mode (llm/agent) and tools exposure."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        _install_routes(page, web_chat_path="agent", tools_exposed=True)
        try:
            page.goto(GUI_URL + "/", wait_until="load")
            page.wait_for_selector("#chat-input", timeout=15000)
            page.keyboard.down("Control")
            page.keyboard.press(",")
            page.keyboard.up("Control")
            page.wait_for_selector("#api-base", state="visible", timeout=15000)
            page.fill("#api-base", BACKEND_URL)
            page.click("#settings-refresh")
            page.wait_for_function(
                "document.getElementById('backend-status').textContent.includes('Status: online') && "
                "document.getElementById('backend-status').textContent.includes('agent (Jo tools enabled)')",
                timeout=15000,
            )
            meta = page.locator("#backend-meta").inner_text()
            assert "web chat: agent" in meta
            assert "tools exposed: yes" in meta
        finally:
            browser.close()
