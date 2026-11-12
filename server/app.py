"""Jo web chat backend.

Exposes the chat contract used by the GitHub Pages GUI:

    POST /v1/chat         {"message": "..."}  ->  {"response": "..."}
    POST /v1/chat/stream  {"message": "..."}  ->  SSE: data: {"delta"|"done"|"error"}

The endpoint reuses Jo's direct-chat agent path when available, and falls
back to a direct LLM call when the full agent workflow cannot run.
"""

from __future__ import annotations

import asyncio
import json
import os
import traceback
import uuid
from typing import Any, Dict, Iterator, Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

app = FastAPI(title="Jo", version="6.5.1")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str


class ChatResponse(BaseModel):
    response: str


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _provider_status() -> Dict[str, Any]:
    provider = _env("LLM_PROVIDER") or "openrouter"
    keys = {
        "openrouter": bool(_env("OPENROUTER_API_KEY")),
        "nvidia": bool(_env("NVIDIA_API_KEY")),
        "doubleword": bool(_env("DOUBLEWORD_API_KEY")),
        "local": bool(_env("LOCAL_BASE_URL") or _env("LOCAL_API_KEY") or _env("OLLAMA_HOST")),
    }
    model = _env("OUROBOROS_MODEL") or "openrouter/free"
    configured = any(keys.values()) or provider == "local"
    return {
        "provider": provider,
        "model": model,
        "keys": keys,
        "configured": configured,
    }


def _run_via_agent(message: str) -> str:
    from supervisor.workers import _get_chat_agent

    agent = _get_chat_agent()
    task: Dict[str, Any] = {
        "id": "web_" + uuid.uuid4().hex[:8],
        "type": "task",
        "chat_id": 0,
        "_is_direct_chat": True,
        "text": message,
    }
    events = agent.handle_task(task) or []
    parts = []
    for event in events:
        if isinstance(event, dict) and event.get("type") == "send_message":
            text = event.get("text")
            if text:
                parts.append(str(text))
    if parts:
        return "\n\n".join(parts).strip()
    # Some paths may return content differently; last resort serialize useful events
    for event in reversed(events):
        if isinstance(event, dict):
            for k in ("content", "message", "response", "text"):
                if event.get(k):
                    return str(event[k]).strip()
    return ""


def _run_via_llm(message: str) -> str:
    from ouroboros.llm import LLMClient

    client = LLMClient()
    model = client.default_model()
    msg, usage = client.chat(
        messages=[
            {
                "role": "system",
                "content": "You are Jo, a self-creating AI agent speaking through the web GUI. Be direct, helpful, and authentic.",
            },
            {"role": "user", "content": message},
        ],
        model=model,
        tools=None,
        reasoning_effort="medium",
        max_tokens=2048,
        _skip_trivial=False,
    )
    content = (msg or {}).get("content") or ""
    if isinstance(content, list):
        # some providers return content parts
        content = "".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in content
        )
    content = str(content).strip()
    return content


def _fallback_response(message: str, err: Optional[str] = None) -> str:
    st = _provider_status()
    lines = []
    lines.append("Jo web backend is reachable, but no LLM provider is currently available to generate a full response.")
    lines.append("")
    lines.append(f"Provider: {st['provider']} | Model: {st['model']}")
    lines.append("Configured credentials: " + (", ".join(k for k, v in st["keys"].items() if v) or "none"))
    if err:
        short = err.strip().splitlines()[-1]
        if len(short) > 300:
            short = short[:300] + "…"
        lines.append("")
        lines.append("Last error: " + short)
    lines.append("")
    lines.append("To make chat fully functional, configure a free provider on the backend and restart:")
    lines.append("- OpenRouter: set LLM_PROVIDER=openrouter, OPENROUTER_API_KEY, OUROBOROS_MODEL=openrouter/free (or another :free model)")
    lines.append("- NVIDIA NIM: set NVIDIA_API_KEY (and optional NVIDIA_FALLBACK_MODEL) — used as fallback/provider")
    lines.append("- Doubleword: set DOUBLEWORD_API_KEY")
    lines.append("- Local (Ollama): set LLM_PROVIDER=local and LOCAL_BASE_URL (default http://localhost:11434/v1) with a pulled model")
    lines.append("")
    preview = (message or "").strip()
    if len(preview) > 200:
        preview = preview[:200] + "…"
    if preview:
        lines.append("Your message was received: " + preview)
    return "\n".join(lines)


def generate_response(message: str) -> str:
    message = (message or "").strip()
    if not message:
        return "Send a message to start chatting with Jo."

    errors = []
    # Prefer lightweight direct LLM path (robust in minimal environments)
    try:
        text = _run_via_llm(message)
        if text:
            return text
        errors.append("llm returned empty content")
    except Exception as e:
        errors.append(f"llm: {e}")

    # Optional: try full agent workflow if explicitly enabled
    if _env("JO_WEB_USE_AGENT") == "1":
        try:
            text = _run_via_agent(message)
            if text:
                return text
            errors.append("agent returned no message")
        except Exception as e:
            errors.append(f"agent: {e}")

    detail = " | ".join(errors) if errors else None
    return _fallback_response(message, detail)


def _chunk_text(text: str, size: int = 80) -> Iterator[str]:
    if not text:
        return
    # stream by paragraphs/lines for nicer feel
    buf = ""
    for ch in text:
        buf += ch
        if len(buf) >= size and ch in "\n. ":
            yield buf
            buf = ""
    if buf:
        yield buf


def _sse(data: Dict[str, Any]) -> str:
    return "data: " + json.dumps(data, ensure_ascii=False) + "\n\n"


@app.post("/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    try:
        response = await asyncio.to_thread(generate_response, req.message)
    except Exception as e:
        response = _fallback_response(req.message, str(e))
    return ChatResponse(response=response or "")


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    async def gen():
        try:
            response = await asyncio.to_thread(generate_response, req.message)
        except Exception as e:
            yield _sse({"error": str(e)})
            response = _fallback_response(req.message, str(e))
        response = response or ""
        for part in _chunk_text(response, 120):
            yield _sse({"delta": part})
            await asyncio.sleep(0)
        yield _sse({"done": True, "response": response})

    headers = {
        "Cache-Control": "no-cache",
        "Connection": "keep-alive",
        "X-Accel-Buffering": "no",
    }
    return StreamingResponse(gen(), media_type="text/event-stream", headers=headers)


@app.get("/health")
async def health() -> Dict[str, Any]:
    st = _provider_status()
    st["status"] = "ok"
    st["version"] = "6.5.1"
    st["endpoints"] = ["/v1/chat", "/v1/chat/stream", "/health", "/v1/status"]
    return st


@app.get("/v1/status")
async def status() -> Dict[str, Any]:
    st = _provider_status()
    st["status"] = "ok"
    return st

