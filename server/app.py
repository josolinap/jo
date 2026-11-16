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
    model: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    elapsed_ms: Optional[int] = None


def _env(name: str) -> str:
    return os.environ.get(name, "").strip()


# Backend is OmniRoute-only by design (local/direct/public fallbacks removed).


def _probe_http_ok(urls, headers_list, timeout=2):
    try:
        import urllib.request as _ur
    except Exception:
        return False
    for _hp in urls:
        for _hdrs in headers_list:
            try:
                _hr = _ur.Request(_hp, headers=_hdrs or {})
                with _ur.urlopen(_hr, timeout=timeout) as _hresp:
                    if 200 <= getattr(_hresp, "status", 200) < 500:
                        return True
            except Exception:
                continue
    return False


def _omni_probe_urls(base: str):
    b = (base or "").rstrip("/")
    root = b.rsplit("/v1", 1)[0] if b.endswith("/v1") else b
    urls = [b + "/models", root + "/health", b + "/health", root + "/v1/models", root + "/"]
    seen = set()
    out = []
    for u in urls:
        if u and u not in seen:
            seen.add(u)
            out.append(u)
    return out


_omni_models_cache: Dict[str, Any] = {"ts": 0.0, "base": "", "models": [], "ok_url": "", "error": ""}
_omni_model_probe_cache: Dict[str, Dict[str, Any]] = {}
_OMNI_MODEL_PROBE_TTL = 300.0
_OMNI_MODEL_PROBE_TIMEOUT = 8  # seconds (kept short for stability)


def _is_free_model_entry(model: Any) -> bool:
    """Heuristic: detect free/zero-cost models dynamically from OmniRoute model IDs/metadata."""
    if isinstance(model, dict):
        mid = str(model.get("id") or model.get("name") or model.get("model") or "").strip()
        obj = model
    else:
        mid = str(model or "").strip()
        obj = {}
    ml = mid.lower()
    if not mid:
        return False
    # explicit id hints
    if ":free" in ml or ml.endswith("/free") or "/free" in ml or ml.endswith("-free"):
        return True
    # metadata hints (best-effort, schema varies by gateway/provider)
    for k in ("free", "is_free", "isFree"):
        v = obj.get(k)
        if v is True:
            return True
        if isinstance(v, str) and v.lower() in ("true", "1", "yes", "free"):
            return True
    pricing = obj.get("pricing") or obj.get("cost") or obj.get("price")
    if isinstance(pricing, dict):
        vals = []
        for pk, pv in pricing.items():
            if isinstance(pv, (int, float)):
                vals.append(float(pv))
            elif isinstance(pv, str):
                try:
                    vals.append(float(pv))
                except Exception:
                    pass
        if vals and all(v == 0 for v in vals):
            return True
    # some providers tag tiers
    tags = obj.get("tags") or obj.get("capabilities") or []
    if isinstance(tags, list) and any(str(t).lower() in ("free", "tier:free") for t in tags):
        return True
    return False


def _fetch_omniroute_models(base: str, timeout: int = 5, use_cache: bool = True) -> tuple[list[Any], Dict[str, Any]]:
    import time as _time

    b = (base or "").rstrip("/")
    if not b:
        return [], {"reachable": False, "model_count": 0, "base": b, "ok_url": "", "error": "no_base"}
    now = _time.time()
    if use_cache and _omni_models_cache.get("base") == b and (now - float(_omni_models_cache.get("ts") or 0)) < 20:
        cached = list(_omni_models_cache.get("models") or [])
        return cached, {
            "reachable": bool(_omni_models_cache.get("ok_url")) or bool(cached),
            "model_count": len(cached),
            "base": b,
            "ok_url": _omni_models_cache.get("ok_url") or "",
            "error": _omni_models_cache.get("error") or "",
            "cached": True,
        }
    try:
        import urllib.request as _ur, json as _json
    except Exception as e:
        return [], {"reachable": False, "model_count": 0, "base": b, "ok_url": "", "error": f"import:{e}"}
    _murls = [b + "/models", (b.rsplit("/v1", 1)[0] + "/v1/models")]
    _seen_murls = set()
    _murls = [u for u in _murls if not (u in _seen_murls or _seen_murls.add(u))]
    md = None
    ok_url = ""
    last_err = ""
    for _mu in _murls:
        for _mh in _omni_auth_header_variants():
            try:
                mreq = _ur.Request(_mu, headers=_mh or {})
                with _ur.urlopen(mreq, timeout=timeout) as mr:
                    status = getattr(mr, "status", 200)
                    if 200 <= status < 500:
                        md = _json.loads(mr.read().decode("utf-8", "replace"))
                        ok_url = _mu
                        break
            except Exception as e:
                last_err = f"{type(e).__name__}: {e}"
                md = None
                continue
        if md is not None:
            break
    models: list[Any] = []
    seen_ids: set[str] = set()
    if isinstance(md, dict):
        for item in md.get("data") or md.get("models") or []:
            if isinstance(item, dict):
                mid = (item.get("id") or item.get("name") or item.get("model") or "")
                mid = str(mid).strip()
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                models.append(item)
            else:
                mid = str(item or "").strip()
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                models.append(mid)
    info = {
        "reachable": bool(ok_url) or md is not None or bool(models),
        "model_count": len(models),
        "base": b,
        "ok_url": ok_url,
        "error": "" if (ok_url or md is not None or models) else (last_err or "unreachable"),
        "cached": False,
    }
    _omni_models_cache.update({"ts": now, "base": b, "models": models, "ok_url": ok_url, "error": info["error"]})
    return models, info


def _omni_auth_header_variants():
    key = (_env("OMNIROUTE_API_KEY") or _env("OPENAI_API_KEY") or "omniroute").strip() or "omniroute"
    variants = []
    for k in [key, "omniroute-local", "omniroute", "sk-local", "dummy"]:
        if k:
            variants.append({"Authorization": "Bearer " + k})
    variants.append({})
    uniq = []
    seen = set()
    for v in variants:
        t = tuple(sorted(v.items()))
        if t not in seen:
            seen.add(t)
            uniq.append(v)
    return uniq


def _probe_omniroute_model(base: str, model_id: str, timeout: int = _OMNI_MODEL_PROBE_TIMEOUT, use_cache: bool = True) -> Dict[str, Any]:
    """Lightweight chat-completion probe to determine if a model is actually usable."""
    import time as _time
    import json as _json
    import urllib.request as _ur
    import urllib.error as _ue

    b = (base or "").rstrip("/")
    mid = str(model_id or "").strip() or "auto"
    cache_key = f"{b}::{mid}"
    now = _time.time()
    if use_cache:
        cached = _omni_model_probe_cache.get(cache_key)
        if cached and (now - float(cached.get("checked_at_ts") or 0)) < _OMNI_MODEL_PROBE_TTL:
            out = dict(cached)
            out["cached"] = True
            return out

    if not b:
        result = {
            "ok": False, "model": mid, "latency_ms": None, "error": "omniroute_base_not_configured",
            "checked_at": int(now), "checked_at_ts": now, "cached": False,
        }
        _omni_model_probe_cache[cache_key] = dict(result)
        return result

    payload = _json.dumps({
        "model": mid,
        "messages": [{"role": "user", "content": "Reply with OK"}],
        "max_tokens": 4,
        "temperature": 0,
        "stream": False,
    }).encode("utf-8")
    urls = [b + "/chat/completions", b.rstrip("/") + "/v1/chat/completions"]
    seen_u = set(); urls = [u for u in urls if not (u in seen_u or seen_u.add(u))]
    last_err = "no_response"
    ok = False
    latency_ms = None
    used_url = ""
    for url in urls:
        for hdrs in _omni_auth_header_variants():
            headers = {"Content-Type": "application/json"}
            headers.update(hdrs or {})
            start = _time.time()
            try:
                req = _ur.Request(url, data=payload, headers=headers, method="POST")
                with _ur.urlopen(req, timeout=timeout) as resp:
                    latency_ms = int((_time.time() - start) * 1000)
                    raw = resp.read().decode("utf-8", "replace")
                    try:
                        data = _json.loads(raw) if raw else {}
                    except Exception:
                        data = {}
                    if isinstance(data, dict) and data.get("error"):
                        err_obj = data.get("error")
                        if isinstance(err_obj, dict):
                            last_err = str(err_obj.get("code") or err_obj.get("message") or err_obj)[:160]
                        else:
                            last_err = str(err_obj)[:160]
                        continue
                    choices = (data or {}).get("choices") if isinstance(data, dict) else None
                    msg = ((choices or [{}])[0] or {}).get("message") if isinstance(choices, list) and choices else {}
                    text = _extract_text(msg) if isinstance(msg, dict) else ""
                    if text and not _looks_bad_response(text):
                        ok = True
                        used_url = url
                        last_err = ""
                        break
                    last_err = "empty_or_bad_response"
            except _ue.HTTPError as e:
                latency_ms = int((_time.time() - start) * 1000)
                try:
                    body = e.read().decode("utf-8", "replace")[:180]
                except Exception:
                    body = ""
                last_err = f"HTTP_{e.code}" + (f": {body}" if body else "")
            except Exception as e:
                latency_ms = int((_time.time() - start) * 1000)
                last_err = f"{type(e).__name__}: {e}"[:160]
        if ok:
            break
    result = {
        "ok": ok,
        "model": mid,
        "latency_ms": latency_ms,
        "error": "" if ok else last_err,
        "url": used_url,
        "checked_at": int(now),
        "checked_at_ts": now,
        "cached": False,
    }
    _omni_model_probe_cache[cache_key] = dict(result)
    return result


def _get_default_probe_model(base: str, preferred: Optional[str] = None) -> str:
    cand = (preferred or _env("OMNIROUTE_MODEL") or "auto").strip() or "auto"
    if cand.lower() != "auto":
        return cand
    try:
        discovered, _ = _fetch_omniroute_models(base, timeout=4, use_cache=True)
        for entry in discovered:
            if isinstance(entry, dict):
                mid = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
            else:
                mid = str(entry or "").strip()
            ml = mid.lower()
            if not mid or ml == "auto" or ml.startswith("auto/") or ml.startswith("auto-"):
                continue
            if ml.startswith("cfp/") or ml.startswith("dva/") or "playwright" in ml or "cloudflare playground" in ml:
                continue
            if _is_free_model_entry(entry if isinstance(entry, dict) else mid):
                return mid
    except Exception:
        pass
    return "openrouter/free"


def _provider_status() -> Dict[str, Any]:
    omni_base = _env("OMNIROUTE_BASE_URL")
    omni_reachable = False
    omni_models: list[str] = []
    omni_info: Dict[str, Any] = {"reachable": False, "model_count": 0, "base": omni_base, "ok_url": "", "error": ""}

    if omni_base:
        omni_reachable = _probe_http_ok(_omni_probe_urls(omni_base), _omni_auth_header_variants(), timeout=2)
        try:
            _omni_models_raw, omni_info = _fetch_omniroute_models(omni_base, timeout=4, use_cache=True)
            omni_models = []
            for _m in (_omni_models_raw or []):
                if isinstance(_m, dict):
                    _mid = str(_m.get("id") or _m.get("name") or _m.get("model") or "").strip()
                else:
                    _mid = str(_m or "").strip()
                if _mid:
                    omni_models.append(_mid)
            if omni_models or omni_info.get("reachable"):
                omni_reachable = True
        except Exception as e:
            omni_info = {
                "reachable": omni_reachable,
                "model_count": 0,
                "base": omni_base,
                "ok_url": "",
                "error": f"{type(e).__name__}: {e}",
            }
            omni_models = []
        omni_info["reachable"] = bool(omni_reachable)

    configured = bool(omni_base)
    reasons = []
    if omni_base and omni_reachable:
        reasons.append("omniroute_available")
    elif omni_base:
        reasons.append("omniroute_configured_but_unreachable")
    else:
        reasons.append("omniroute_not_configured")

    model_probe = None
    if _env("JO_WEB_ENABLE_MODEL_PROBE") != "0" and omni_base and omni_reachable:
        try:
            probe_model = _get_default_probe_model(omni_base, _env("OMNIROUTE_MODEL") or "auto")
            model_probe = _probe_omniroute_model(omni_base, probe_model, timeout=_OMNI_MODEL_PROBE_TIMEOUT, use_cache=True)
        except Exception as e:
            model_probe = {"ok": False, "model": _env("OMNIROUTE_MODEL") or "auto", "error": f"probe_exception: {e}", "cached": False}
    elif _env("JO_WEB_ENABLE_MODEL_PROBE") == "0":
        model_probe = {"ok": None, "skipped": True, "reason": "disabled_by_env"}
    elif omni_base and not omni_reachable:
        model_probe = {"ok": False, "model": _env("OMNIROUTE_MODEL") or "auto", "error": omni_info.get("error") or "omniroute_unreachable", "cached": False}

    if model_probe is not None:
        if model_probe.get("ok") is True:
            reasons.append("default_model_probe_ok")
        elif model_probe.get("ok") is False:
            reasons.append("default_model_probe_failed")

    return {
        "provider": "omniroute",
        "model": _env("OMNIROUTE_MODEL") or "auto",
        "keys": {
            "openrouter": False,
            "nvidia": False,
            "doubleword": False,
            "local": False,
            "omniroute": bool(omni_base) and omni_reachable,
            "omniroute_configured": bool(omni_base),
        },
        "configured": configured,
        "local_reachable": False,
        "omniroute_reachable": omni_reachable,
        "env_provider": "omniroute",
        "reasons": reasons,
        "fallback_active": False,
        "model_source": "omniroute",
        "model_probe": model_probe,
        "omniroute": {
            "configured": bool(omni_base),
            "reachable": bool(omni_reachable),
            "base_url": omni_base,
            "selected_model": _env("OMNIROUTE_MODEL") or "auto",
            "model_count": len(omni_models),
            "models_sample": omni_models[:10],
            "ok_url": omni_info.get("ok_url") or "",
            "error": omni_info.get("error") or "",
        },
        "local": {
            "configured": False,
            "reachable": False,
            "base_url": "",
        },
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


def _run_via_llm(
    message: str, history: Optional[list[Dict[str, str]]] = None, requested_model: Optional[str] = None
) -> tuple[str, Dict[str, Any]]:
    msgs = _build_messages(message, history)
    errors = []

    # Strategy 1 (priority): OmniRoute gateway - aggregate/routed free & connected models
    omni_base = _env("OMNIROUTE_BASE_URL")
    omni_ready = False
    if omni_base:
        try:
            omni_ready = _probe_http_ok(_omni_probe_urls(omni_base), _omni_auth_header_variants(), timeout=3)
        except Exception:
            omni_ready = False
    if omni_base:
        if not omni_ready:
            errors.append("omniroute: probe unreachable (attempting anyway)")
        try:
            from openai import OpenAI

            ocli = OpenAI(
                base_url=omni_base.rstrip("/"),
                api_key=_env("OMNIROUTE_API_KEY") or _env("OPENAI_API_KEY") or "omniroute",
                timeout=30.0,
                max_retries=0,
            )
            last_oe = None
            preferred = []
            req_model = (requested_model or "").strip()
            env_model = (_env("OMNIROUTE_MODEL") or "").strip()
            # If user explicitly selected a model, try it first via OmniRoute (priority path)
            if req_model and req_model.lower() != "auto":
                preferred.append(req_model)
            if env_model and env_model not in preferred:
                preferred.append(env_model)
            # prefer concrete/free models over abstract auto aliases to avoid long hangs
            for m in ("openrouter/free", "auto"):
                if m not in preferred:
                    preferred.append(m)
            discovered = []
            # try to discover available models from OmniRoute (tolerant auth/endpoints)
            try:
                import urllib.request as _ur, json as _json

                _murls = [omni_base.rstrip("/") + "/models", (omni_base.rstrip("/").rsplit("/v1", 1)[0] + "/v1/models")]
                _seen_murls = set()
                _murls = [u for u in _murls if not (u in _seen_murls or _seen_murls.add(u))]
                md = None
                for _mu in _murls:
                    for _mh in _omni_auth_header_variants():
                        try:
                            mreq = _ur.Request(_mu, headers=_mh or {})
                            with _ur.urlopen(mreq, timeout=6) as mr:
                                md = _json.loads(mr.read().decode("utf-8", "replace"))
                            if md is not None:
                                break
                        except Exception:
                            md = None
                            continue
                    if md is not None:
                        break
                if md is not None:
                    for item in md.get("data") or md.get("models") or []:
                        mid = (item or {}).get("id") if isinstance(item, dict) else item
                        if not mid and isinstance(item, dict):
                            mid = item.get("name") or item.get("model")
                        if not mid:
                            continue
                        mid = str(mid).strip()
                        if not mid or mid in preferred or mid in discovered:
                            continue
                        discovered.append(mid)
            except Exception:
                pass

            # prioritize explicit/free/concrete discovered models over many auto aliases, cap attempts
            def _skip_in_ci(ml: str, explicit: bool = False) -> bool:
                if explicit:
                    return False
                # Known unusable in headless CI OmniRoute: browser runtime deps or unconfigured bridges
                return (
                    ml.startswith("cfp/")
                    or ml.startswith("dva/")
                    or "cloudflare playground" in ml
                    or "playwright" in ml
                    or "devin agentic bridge" in ml
                )

            def _omni_rank(mid: str) -> tuple:
                ml = mid.lower()
                broken_env = _skip_in_ci(ml)
                is_free = ":free" in ml or ml.endswith("/free") or "openrouter/free" in ml
                is_auto_alias = ml.startswith("auto")
                is_concrete = ("/" in ml) and not is_auto_alias
                preferred_family = (
                    0
                    if any(
                        k in ml
                        for k in (
                            "llama",
                            "qwen",
                            "gemma",
                            "mistral",
                            "gpt-oss",
                            "deepseek",
                            "glm",
                            "kimi",
                            "minimax",
                            "phi",
                            "smol",
                        )
                    )
                    else 1
                )
                return (
                    9 if broken_env else 0 if is_free else 1 if is_concrete else 4 if is_auto_alias else 3,
                    preferred_family,
                    0 if is_free else 1,
                )

            discovered = sorted(discovered, key=_omni_rank)
            candidates: list[str] = []
            req_is_explicit = bool(req_model and req_model.lower() != "auto")

            def _add_candidate(mid: str):
                if not mid:
                    return
                ml = mid.lower()
                if mid in candidates:
                    return
                if _skip_in_ci(ml, explicit=((requested_model or "").strip().lower() == ml)):
                    return
                candidates.append(mid)

            # 1) explicit request (if any)
            if req_is_explicit:
                _add_candidate(req_model)
            # 2) concrete discovered models (non-auto, preferred families first by sort)
            for m in discovered:
                ml = m.lower()
                if not ml.startswith("auto"):
                    _add_candidate(m)
            # 3) configured env model if concrete
            if env_model and env_model.lower() != "auto":
                _add_candidate(env_model)
            # 4) safe/common fallbacks
            for m in ("openrouter/free",):
                _add_candidate(m)
            # 5) aliases only if explicitly requested or nothing else
            if (not req_is_explicit) or not any(not c.lower().startswith("auto") for c in candidates):
                for m in discovered:
                    if m.lower().startswith("auto"):
                        _add_candidate(m)
                _add_candidate("auto")
            if not candidates:
                candidates = ["openrouter/free", "auto"]

            # If user explicitly selected a specific model, do not silently fall back to other models.
            if req_is_explicit:
                candidates = [req_model] if req_model else candidates[:1]

            tried = 0
            saw_env_error = False
            max_tries = 20 if not req_is_explicit else 1
            for om in candidates:
                if tried >= max_tries:
                    break
                oml = om.lower()
                if _skip_in_ci(oml, explicit=((requested_model or "").strip().lower() == oml)):
                    if req_is_explicit:
                        errors.append(f"omniroute({om}): model unavailable in this environment")
                        break
                    continue
                if saw_env_error and oml.startswith("auto") and not req_is_explicit and (env_model or "").lower() != oml:
                    continue
                try:
                    tried += 1
                    resp = ocli.chat.completions.create(model=om, messages=msgs, temperature=0, max_tokens=512)
                    msg = (resp.model_dump().get("choices") or [{}])[0].get("message") or {}
                    text = _extract_text(msg)
                    if text and not _looks_bad_response(text):
                        return text, {"provider": "omniroute", "model": om}
                    if text:
                        errors.append(f"omniroute({om}): rejected bad response")
                    else:
                        errors.append(f"omniroute({om}): empty response")
                    if req_is_explicit:
                        break
                except Exception as oe:
                    last_oe = oe
                    emsg = str(oe)
                    errors.append(f"omniroute({om}): {oe}")
                    if req_is_explicit:
                        break
                    low_emsg = emsg.lower()
                    # If provider is unavailable due to CI env/runtime config, keep trying others
                    if (
                        "playwright" in low_emsg
                        or "chromium browser" in low_emsg
                        or "cloudflare playground" in low_emsg
                        or "devin agentic bridge" in low_emsg
                        or ("not configured" in low_emsg and ("503" in low_emsg or "502" in low_emsg))
                    ):
                        saw_env_error = True
                        continue
            if last_oe and not any(e.startswith("omniroute:") for e in errors):
                errors.append(f"omniroute: {last_oe}")
        except Exception as e:
            errors.append(f"omniroute: {e}")

    # OmniRoute-only backend: no local/direct/public provider fallbacks.
    if req_model and req_model.lower() != "auto":
        # Preserve explicit selection semantics: do not hide which model failed.
        detail = " | ".join(errors[-6:]) if errors else "no response"
        raise RuntimeError(f"Selected model '{req_model}' failed: {detail}")
    priority = [e for e in errors if e.startswith("omniroute")]
    tail = errors[-8:]
    summary = (
        " | ".join((priority + [x for x in tail if x not in priority])[:12])
        if errors
        else "no omniroute provider response"
    )
    raise RuntimeError(summary)


def _fallback_response(message: str, err: Optional[str] = None) -> str:
    st = _provider_status()
    lines = []
    lines.append("Jo web backend is reachable, but OmniRoute is not currently able to generate a response.")
    lines.append("")
    lines.append(f"Provider: {st.get('provider', 'omniroute')} | Model: {st.get('model', 'auto')}")
    if err:
        short = err.strip().splitlines()[-1]
        if len(short) > 300:
            short = short[:300] + "…"
        lines.append("")
        lines.append("Last error: " + short)
    lines.append("")
    lines.append("This backend is configured for OmniRoute-only operation.")
    lines.append("To make chat fully functional:")
    lines.append("- Ensure OmniRoute is running and reachable at OMNIROUTE_BASE_URL (e.g. http://127.0.0.1:20128/v1)")
    lines.append(
        "- Configure at least one working upstream provider/model inside OmniRoute (and pass required provider keys/secrets to OmniRoute if needed)"
    )
    lines.append("- Set OMNIROUTE_MODEL=auto (recommended) or a model ID available in OmniRoute")
    lines.append("")
    preview = (message or "").strip()
    if len(preview) > 200:
        preview = preview[:200] + "…"
    if preview:
        lines.append("Your message was received: " + preview)
    return "\n".join(lines)


def generate_response(
    message: str,
    history: Optional[list[Dict[str, str]]] = None,
    session_id: Optional[str] = None,
    requested_model: Optional[str] = None,
) -> tuple[str, str, Dict[str, Any]]:
    message = (message or "").strip()
    sid, sess = _get_session(session_id)
    merged_history = list(sess)
    if history:
        # if client provides history, prefer it (but keep reasonable)
        merged_history = [h for h in history if isinstance(h, dict)]
    if not message:
        return "Send a message to start chatting with Jo.", sid, {"provider": "system", "model": "none"}

    errors = []
    # Prefer lightweight direct LLM path (robust in minimal environments)
    try:
        text, meta = _run_via_llm(message, merged_history, requested_model=requested_model)
        if text:
            sess.append({"role": "user", "content": message})
            sess.append({"role": "assistant", "content": text})
            if len(sess) > _SESSION_MAX:
                del sess[:-_SESSION_MAX]
            _SESSIONS[sid] = sess
            return text, sid, (meta or {})
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
                return text, sid, {"provider": "agent", "model": "agent"}
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
    return resp, sid, {"provider": "fallback", "model": "unavailable"}


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
    history = [h.model_dump() for h in (req.history or [])]
    t0 = asyncio.get_running_loop().time()
    meta: Dict[str, Any] = {}
    sid = (req.session_id or "").strip() or ("web_" + uuid.uuid4().hex[:10])
    try:
        response, sid, meta = await asyncio.wait_for(
            asyncio.to_thread(generate_response, req.message, history, req.session_id, req.model),
            timeout=120.0,
        )
    except Exception as e:
        response = _fallback_response(req.message, f"request_timeout_or_error: {e}")
        meta = {"provider": "fallback", "model": "unavailable"}
    elapsed_ms = int((asyncio.get_running_loop().time() - t0) * 1000)
    return ChatResponse(
        response=response or "",
        session_id=sid,
        provider=(meta or {}).get("provider"),
        model=(meta or {}).get("model") or req.model,
        elapsed_ms=elapsed_ms,
    )


@app.post("/v1/chat/stream")
async def chat_stream(req: ChatRequest):
    history = [h.model_dump() for h in (req.history or [])]

    async def gen():
        sid = (req.session_id or "").strip() or ("web_" + uuid.uuid4().hex[:10])
        t0 = asyncio.get_running_loop().time()
        meta: Dict[str, Any] = {}
        try:
            response, sid, meta = await asyncio.wait_for(
                asyncio.to_thread(generate_response, req.message, history, req.session_id, req.model),
                timeout=120.0,
            )
        except Exception as e:
            yield _sse({"error": str(e), "session_id": sid})
            response = _fallback_response(req.message, f"request_timeout_or_error: {e}")
            meta = {"provider": "fallback", "model": "unavailable"}
        response = response or ""
        for part in _chunk_text(response, 120):
            yield _sse({"delta": part, "session_id": sid})
            await asyncio.sleep(0)
        elapsed_ms = int((asyncio.get_running_loop().time() - t0) * 1000)
        yield _sse(
            {
                "done": True,
                "response": response,
                "session_id": sid,
                "provider": (meta or {}).get("provider"),
                "model": (meta or {}).get("model") or req.model,
                "elapsed_ms": elapsed_ms,
            }
        )

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


def _list_models() -> Dict[str, Any]:
    models: list[Dict[str, Any]] = []
    seen: set[str] = set()

    def add(mid: str, provider: str, label: Optional[str] = None, **extra):
        mid = (mid or "").strip()
        if not mid or mid in seen:
            return
        seen.add(mid)
        item = {"id": mid, "provider": provider, "label": label or mid}
        if extra:
            item.update(extra)
        models.append(item)

    auto_probe = None
    if omni_base and _env("JO_WEB_ENABLE_MODEL_PROBE") != "0":
        try:
            probe_model = _get_default_probe_model(omni_base, _env("OMNIROUTE_MODEL") or "auto")
            cached = _omni_model_probe_cache.get(f"{omni_base.rstrip('/')}::{probe_model}")
            if cached:
                auto_probe = {k: cached.get(k) for k in ("ok", "model", "latency_ms", "error", "checked_at", "cached") if k in cached}
        except Exception:
            auto_probe = None
    add("auto", "omniroute", "Auto (recommended)", recommended=True, probe=auto_probe)

    # Dynamically discover and expose all available free models from OmniRoute.
    # "Free" is detected from model IDs and metadata (pricing/tags/flags) when present.
    omni_base = _env("OMNIROUTE_BASE_URL")
    if omni_base:
        try:
            discovered, _ = _fetch_omniroute_models(omni_base, timeout=5, use_cache=True)
            for entry in discovered:
                if isinstance(entry, dict):
                    smid = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
                    meta = entry
                else:
                    smid = str(entry or "").strip()
                    meta = {}
                ml = smid.lower()
                if not smid or ml == "auto":
                    continue
                # Exclude routes known to require browser/runtime bridges in headless CI.
                if ml.startswith("cfp/") or ml.startswith("dva/"):
                    continue
                if "cloudflare playground" in ml or "playwright" in ml or "devin agentic bridge" in ml:
                    continue

                is_free = _is_free_model_entry(meta if meta else smid)
                if not is_free:
                    continue

                extra: Dict[str, Any] = {"dynamic": True, "free": True}
                # Preserve useful metadata if OmniRoute provides it (helps UI/debugging)
                for k in ("owned_by", "provider", "description", "context_length", "pricing", "tags"):
                    if k in meta and meta.get(k) is not None:
                        extra[k] = meta.get(k)
                # Classify auto-combo routes (e.g. auto/coding:free) vs concrete model IDs
                if ml.startswith("auto/") or ml.startswith("auto-"):
                    extra["kind"] = "auto_route"
                    extra["label_hint"] = "auto-route"
                # Attach cached probe info if available (no extra probing here for stability)
                try:
                    cached_probe = _omni_model_probe_cache.get(f"{omni_base.rstrip('/')}::{smid}")
                    if cached_probe:
                        extra["probe"] = {k: cached_probe.get(k) for k in ("ok", "latency_ms", "error", "checked_at", "cached") if k in cached_probe}
                except Exception:
                    pass
                add(smid, "omniroute", label=smid, **extra)
        except Exception:
            pass

    return {"models": models, "default": _env("OMNIROUTE_MODEL") or "auto"}


@app.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    return await asyncio.to_thread(_list_models)
