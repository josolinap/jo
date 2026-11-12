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


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: Optional[list[ChatMessage]] = None
    session_id: Optional[str] = None
    stream: Optional[bool] = None


class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _local_reachable() -> bool:
    base = _env("LOCAL_BASE_URL")
    if not base:
        return False
    try:
        import urllib.request
        candidates = [base.rstrip("/") + "/models", base.rstrip("/").rsplit("/v1", 1)[0] + "/health", base.rstrip("/") + "/health"]
        for url in candidates:
            for headers in ({}, {"Authorization": "Bearer " + (_env("LOCAL_API_KEY") or "sk-local")}):
                try:
                    req = urllib.request.Request(url, headers=headers)
                    with urllib.request.urlopen(req, timeout=2) as r:
                        if 200 <= getattr(r, "status", 200) < 500:
                            return True
                except Exception:
                    continue
        return False
    except Exception:
        return False


def _detect_local_model(base: str) -> str:
    try:
        import urllib.request, json as _json
        url = base.rstrip("/") + "/models"
        for headers in ({}, {"Authorization": "Bearer " + (_env("LOCAL_API_KEY") or "sk-local")}):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=3) as r:
                    data = _json.loads(r.read().decode("utf-8", "replace"))
                models = data.get("data") or data.get("models") or []
                if isinstance(models, list) and models:
                    m0 = models[0]
                    if isinstance(m0, dict):
                        mid = m0.get("id") or m0.get("name") or ""
                        if mid:
                            return str(mid)
                    elif isinstance(m0, str):
                        return m0
            except Exception:
                continue
    except Exception:
        pass
    return "local-model"


def _provider_status() -> Dict[str, Any]:
    provider = _env("LLM_PROVIDER") or "openrouter"
    local_ok = _local_reachable()
    keys = {
        "openrouter": bool(_env("OPENROUTER_API_KEY")),
        "nvidia": bool(_env("NVIDIA_API_KEY")),
        "doubleword": bool(_env("DOUBLEWORD_API_KEY")),
        "local": bool(_env("LOCAL_BASE_URL") or _env("LOCAL_API_KEY") or _env("OLLAMA_HOST")) or local_ok,
        "omniroute": bool(_env("OMNIROUTE_BASE_URL")),
    }
    model = _env("OUROBOROS_MODEL") or "openrouter/free"
    if local_ok:
        model = _detect_local_model(_env("LOCAL_BASE_URL"))
    if _env("OMNIROUTE_BASE_URL"):
        model = _env("OMNIROUTE_MODEL") or "auto"
    configured = any(keys.values()) or provider in ("local", "omniroute") or local_ok
    return {
        "provider": provider,
        "model": model,
        "keys": keys,
        "configured": configured,
        "local_reachable": local_ok,
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


_SESSIONS: Dict[str, list[Dict[str, str]]] = {}
_SESSION_MAX = 40


def _get_session(session_id: Optional[str]) -> tuple[str, list[Dict[str, str]]]:
    sid = (session_id or "").strip() or ("web_" + uuid.uuid4().hex[:10])
    hist = _SESSIONS.setdefault(sid, [])
    return sid, hist


def _build_messages(message: str, history: Optional[list[Dict[str, str]]] = None) -> list[Dict[str, str]]:
    msgs: list[Dict[str, str]] = [
        {
            "role": "system",
            "content": "You are Jo, a self-creating AI agent speaking through the web GUI. Be direct, helpful, and authentic. Use conversation history when provided.",
        }
    ]
    for h in (history or [])[-20:]:
        role = str(h.get("role") or "user")
        content = str(h.get("content") or "")
        if role not in ("user", "assistant", "system"):
            role = "user"
        if content:
            msgs.append({"role": role, "content": content})
    if not msgs or msgs[-1].get("content") != message or msgs[-1].get("role") != "user":
        msgs.append({"role": "user", "content": message})
    return msgs


def _extract_text(msg: Any) -> str:
    content = (msg or {}).get("content") or ""
    if isinstance(content, list):
        content = "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content).strip()


def _looks_bad_response(text: str) -> bool:
    if not text:
        return True
    t = text.strip()
    low = t.lower()
    # reject obvious provider/error/quota banners mistaken as replies
    bad_markers = [
        "api key used for this request has reached its budget",
        "raise the key budget",
        "missing authentication header",
        "error code: 401",
        "error code: 403",
        "error code: 429",
        "rate limit",
        "too many requests",
        "insufficient credits",
        "no llm provider is currently available",
    ]
    if len(t) < 600 and any(m in low for m in bad_markers):
        return True
    if low.startswith("<!doctype html") or low.startswith("<html"):
        return True
    return False


def _run_via_llm(message: str, history: Optional[list[Dict[str, str]]] = None) -> str:
    from ouroboros.llm import LLMClient, NvidiaLLMClient, DoublewordLLMClient

    msgs = _build_messages(message, history)
    errors = []

    # Strategy 1: Local OpenAI-compatible endpoint (Ollama/llama.cpp) — fastest/free in CI
    local_base = _env("LOCAL_BASE_URL") or ("" if not _env("OLLAMA_HOST") else (_env("OLLAMA_HOST").rstrip("/") + "/v1"))
    if local_base:
        try:
            from openai import OpenAI
            local_model = _detect_local_model(local_base)
            lcli = OpenAI(base_url=local_base, api_key=_env("LOCAL_API_KEY") or "sk-local", timeout=180.0, max_retries=0)
            last_le = None
            for lm in [local_model, "local-model", "gpt-3.5-turbo", "model"]:
                try:
                    resp = lcli.chat.completions.create(model=lm, messages=msgs, temperature=0, max_tokens=256)
                    msg = (resp.model_dump().get("choices") or [{}])[0].get("message") or {}
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text
                    if text:
                        errors.append(f"candidate: rejected bad response")
                except Exception as le:
                    last_le = le
            errors.append(f"local({local_model}): {last_le if last_le else 'empty response'}")
        except Exception as e:
            errors.append(f"local: {e}")

    # Strategy 2: OmniRoute (OpenAI-compatible gateway, can aggregate free/connected providers)
    omni_base = _env("OMNIROUTE_BASE_URL")
    if omni_base:
        try:
            from openai import OpenAI
            ocli = OpenAI(base_url=omni_base.rstrip("/"), api_key=_env("OMNIROUTE_API_KEY") or _env("OPENAI_API_KEY") or "omniroute", timeout=120.0, max_retries=0)
            last_oe = None
            for om in [_env("OMNIROUTE_MODEL") or "auto", "auto", "openrouter/free", "gpt-3.5-turbo"]:
                if not om:
                    continue
                try:
                    resp = ocli.chat.completions.create(model=om, messages=msgs, temperature=0, max_tokens=512)
                    msg = (resp.model_dump().get("choices") or [{}])[0].get("message") or {}
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text
                    if text:
                        errors.append(f"candidate: rejected bad response")
                except Exception as oe:
                    last_oe = oe
            errors.append(f"omniroute: {last_oe if last_oe else 'empty response'}")
        except Exception as e:
            errors.append(f"omniroute: {e}")

    # Strategy 3: default configured client (with its internal fallback chain)
    try:
        client = LLMClient()
        model = client.default_model()
        msg, _ = client.chat(messages=msgs, model=model, tools=None, reasoning_effort="medium", max_tokens=2048, _skip_trivial=False)
        text = _extract_text(msg)
        if text:
            return text
        errors.append("default: empty response")
    except Exception as e:
        errors.append(f"default({os.environ.get('LLM_PROVIDER','openrouter')}): {e}")

    # Strategy 4: NVIDIA direct (if key available)
    if _env("NVIDIA_API_KEY"):
        try:
            n = NvidiaLLMClient()
            for m in [n.select_model_for_task("general"), "meta/llama-3.1-8b-instruct", "google/gemma-2-9b-it", "mistralai/mistral-7b-instruct-v0.3"]:
                if not m:
                    continue
                try:
                    msg, _ = n.chat(messages=msgs, model=m, tools=None, reasoning_effort="medium", max_tokens=2048)
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text
                    if text:
                        errors.append(f"candidate: rejected bad response")
                except Exception as e:
                    errors.append(f"nvidia({m}): {e}")
                    n.mark_model_failure(m)
        except Exception as e:
            errors.append(f"nvidia: {e}")

    # Strategy 5: Doubleword direct (if key available)
    if _env("DOUBLEWORD_API_KEY"):
        try:
            d = DoublewordLLMClient()
            for m in [d.default_model(), "deepseek-ai/DeepSeek-V4-Flash", "openai/gpt-oss-20b", "Qwen/Qwen3.5-35B-A3B-FP8"]:
                if not m:
                    continue
                try:
                    msg, _ = d.chat(messages=msgs, model=m, tools=None, reasoning_effort="medium", max_tokens=2048)
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text
                    if text:
                        errors.append(f"candidate: rejected bad response")
                except Exception as e:
                    errors.append(f"doubleword({m}): {e}")
                    d.mark_model_failure(m)
        except Exception as e:
            errors.append(f"doubleword: {e}")

    # Strategy 6: OpenRouter with explicit common :free models
    if _env("OPENROUTER_API_KEY"):
        try:
            os.environ.setdefault("LLM_PROVIDER", "openrouter")
            client = LLMClient()
            for m in [os.environ.get("OUROBOROS_MODEL", ""), "openrouter/free", "meta-llama/llama-3.2-3b-instruct:free", "google/gemma-3-4b-it:free", "qwen/qwen-2.5-7b-instruct:free", "mistralai/mistral-7b-instruct:free"]:
                m = (m or "").strip()
                if not m:
                    continue
                try:
                    msg, _ = client.chat(messages=msgs, model=m, tools=None, reasoning_effort="medium", max_tokens=2048, _skip_trivial=False)
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text
                    if text:
                        errors.append(f"candidate: rejected bad response")
                except Exception as e:
                    errors.append(f"openrouter({m}): {e}")
        except Exception as e:
            errors.append(f"openrouter: {e}")

    # Strategy 7: Public free text endpoints (no key) as last resort
    try:
        import urllib.request as _ur, json as _json
        prompt = message
        # Pollinations OpenAI-compatible
        try:
            payload = _json.dumps({"model": "openai", "messages": msgs, "temperature": 0.2}).encode()
            req = _ur.Request("https://text.pollinations.ai/openai", data=payload, headers={"Content-Type": "application/json"})
            with _ur.urlopen(req, timeout=60) as r:
                data = _json.loads(r.read().decode("utf-8", "replace"))
            text = _extract_text(((data.get("choices") or [{}])[0]).get("message") or {})
            if not text and isinstance(data.get("choices"), list) and data["choices"]:
                text = str((data["choices"][0] or {}).get("text") or "").strip()
            if text and not _looks_bad_response(text):
                return text
            if text:
                errors.append("pollinations: rejected bad response")
        except Exception as pe:
            errors.append(f"pollinations: {pe}")
        # Pollinations simple GET
        try:
            q = _ur.quote(prompt[:2000])
            req = _ur.Request(f"https://text.pollinations.ai/{q}?model=openai", headers={"Accept": "text/plain"})
            with _ur.urlopen(req, timeout=60) as r:
                text = r.read().decode("utf-8", "replace").strip()
            if text and not _looks_bad_response(text) and len(text) < 20000:
                return text
            if text:
                errors.append("pollinations-get: rejected bad response")
        except Exception as pe:
            errors.append(f"pollinations-get: {pe}")
    except Exception as e:
        errors.append(f"public: {e}")

    # summarize with priority on local/omniroute
    priority = [e for e in errors if e.startswith(("local", "omniroute"))]
    tail = errors[-8:]
    summary = " | ".join((priority + [x for x in tail if x not in priority])[:12]) if errors else "no provider response"
    raise RuntimeError(summary)


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
    lines.append("- Local (Ollama/llama.cpp): set LOCAL_BASE_URL (e.g. http://127.0.0.1:11434/v1) to a running OpenAI-compatible local server")
    lines.append("- OmniRoute: set OMNIROUTE_BASE_URL (e.g. http://127.0.0.1:20128/v1) and OMNIROUTE_API_KEY/OMNIROUTE_MODEL=auto to route via OmniRoute's free/connected providers")
    lines.append("")
    preview = (message or "").strip()
    if len(preview) > 200:
        preview = preview[:200] + "…"
    if preview:
        lines.append("Your message was received: " + preview)
    return "\n".join(lines)


def generate_response(message: str, history: Optional[list[Dict[str, str]]] = None, session_id: Optional[str] = None) -> tuple[str, str]:
    message = (message or "").strip()
    sid, sess = _get_session(session_id)
    merged_history = list(sess)
    if history:
        # if client provides history, prefer it (but keep reasonable)
        merged_history = [h for h in history if isinstance(h, dict)]
    if not message:
        return "Send a message to start chatting with Jo.", sid

    errors = []
    # Prefer lightweight direct LLM path (robust in minimal environments)
    try:
        text = _run_via_llm(message, merged_history)
        if text:
            sess.append({"role": "user", "content": message})
            sess.append({"role": "assistant", "content": text})
            if len(sess) > _SESSION_MAX:
                del sess[:-_SESSION_MAX]
            _SESSIONS[sid] = sess
            return text, sid
        errors.append("llm returned empty content")
    except Exception as e:
        errors.append(f"llm: {e}")

    # Optional: try full agent workflow if explicitly enabled
    if _env("JO_WEB_USE_AGENT") == "1":
        try:
            text = _run_via_agent(message)
            if text:
                sess.append({"role": "user", "content": message})
                sess.append({"role": "assistant", "content": text})
                if len(sess) > _SESSION_MAX:
                    del sess[:-_SESSION_MAX]
                _SESSIONS[sid] = sess
                return text, sid
            errors.append("agent returned no message")
        except Exception as e:
            errors.append(f"agent: {e}")

    detail = " | ".join(errors) if errors else None
    resp = _fallback_response(message, detail)
    # still record turn for continuity of UI/session even if fallback
    sess.append({"role": "user", "content": message})
    sess.append({"role": "assistant", "content": resp})
    if len(sess) > _SESSION_MAX:
        del sess[:-_SESSION_MAX]
    _SESSIONS[sid] = sess
    return resp, sid


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
    st = _provider_status()
    history = [h.model_dump() for h in (req.history or [])]
    try:
        response, sid = await asyncio.to_thread(generate_response, req.message, history, req.session_id)
    except Exception as e:
        sid = (req.session_id or "").strip() or ("web_" + uuid.uuid4().hex[:10])
        response = _fallback_response(req.message, str(e))
    return ChatResponse(response=response or "", session_id=sid, provider=st.get("provider"), model=st.get("model"))


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    st = _provider_status()
    history = [h.model_dump() for h in (req.history or [])]

    async def gen():
        sid = (req.session_id or "").strip() or ("web_" + uuid.uuid4().hex[:10])
        try:
            response, sid = await asyncio.to_thread(generate_response, req.message, history, req.session_id)
        except Exception as e:
            yield _sse({"error": str(e), "session_id": sid})
            response = _fallback_response(req.message, str(e))
        response = response or ""
        for part in _chunk_text(response, 120):
            yield _sse({"delta": part, "session_id": sid})
            await asyncio.sleep(0)
        yield _sse({"done": True, "response": response, "session_id": sid, "provider": st.get("provider"), "model": st.get("model")})

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

