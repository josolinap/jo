"""Jo web chat backend.

Exposes the chat contract used by the GitHub Pages GUI:

    POST /v1/chat         {"message": "..."}  ->  {"response": "..."}
    POST /v1/chat/stream  {"message": "..."}  ->  SSE: data: {"delta"|"done"|"error"}
    GET /v1/floorplan     ->  the app's Floorplan map data (floorplan/graph.json + architecture summary)

The web chat system prompt includes a summary of the app's Floorplan map
(parts, connections, project summary) so the model can reference how the app
is put together. The endpoint reuses Jo's direct-chat agent path when
available, and falls back to a direct LLM call when the full agent workflow
cannot run.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from pathlib import Path
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


def _env_truthy(name: str) -> bool:
    return (_env(name) or "").strip().lower() in ("1", "true", "yes", "on")


def _is_headless_bridge_route(ml: str) -> bool:
    s = (ml or "").lower()
    return (
        s.startswith("cfp/")
        or s.startswith("dva/")
        or "cloudflare playground" in s
        or "playwright" in s
        or "devin agentic bridge" in s
    )


def _exclude_headless_bridge_route(ml: str, explicit: bool = False) -> bool:
    """Whether to exclude routes that are commonly unusable in headless/CI OmniRoute setups.

    Default preserves prior behavior (exclude). Set JO_WEB_OMNIROUTE_INCLUDE_HEADLESS_BRIDGE_ROUTES=1
    to include them when they are actually available in your environment.
    """
    if explicit:
        return False
    if _env_truthy("JO_WEB_OMNIROUTE_INCLUDE_HEADLESS_BRIDGE_ROUTES"):
        return False
    return _is_headless_bridge_route(ml)


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
    if ":free" in ml or ml.endswith("/free") or "/free" in ml or ml.endswith("-free") or "free-tier" in ml:
        return True
    # metadata hints (best-effort, schema varies by gateway/provider)
    for k in ("free", "is_free", "isFree"):
        v = obj.get(k)
        if v is True:
            return True
        if isinstance(v, str) and v.lower() in ("true", "1", "yes", "free"):
            return True
    for k in ("tier", "plan", "pricing_tier", "access_tier"):
        v = obj.get(k)
        if isinstance(v, str) and v.strip().lower() in ("free", "tier:free", "free-tier"):
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
    if isinstance(tags, list):
        norm_tags = {str(t).strip().lower() for t in tags if t is not None}
        if norm_tags & {"free", "tier:free", "free-tier", "pricing:free"}:
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
                mid = item.get("id") or item.get("name") or item.get("model") or ""
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


def _probe_omniroute_model(
    base: str, model_id: str, timeout: int = _OMNI_MODEL_PROBE_TIMEOUT, use_cache: bool = True
) -> Dict[str, Any]:
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
            "ok": False,
            "model": mid,
            "latency_ms": None,
            "error": "omniroute_base_not_configured",
            "checked_at": int(now),
            "checked_at_ts": now,
            "cached": False,
        }
        _omni_model_probe_cache[cache_key] = dict(result)
        return result

    payload = _json.dumps(
        {
            "model": mid,
            "messages": [{"role": "user", "content": "Reply with OK"}],
            "max_tokens": 4,
            "temperature": 0,
            "stream": False,
        }
    ).encode("utf-8")
    urls = [b + "/chat/completions", b.rstrip("/") + "/v1/chat/completions"]
    seen_u = set()
    urls = [u for u in urls if not (u in seen_u or seen_u.add(u))]
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
        # Prefer dynamically discovered free concrete models for probing; fall back to free auto-routes, then auto.
        for entry in discovered:
            if isinstance(entry, dict):
                mid = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
            else:
                mid = str(entry or "").strip()
            ml = mid.lower()
            if not mid or ml == "auto" or ml.startswith("auto/") or ml.startswith("auto-"):
                continue
            if _exclude_headless_bridge_route(ml):
                continue
            if _is_free_model_entry(entry if isinstance(entry, dict) else mid):
                return mid
        for entry in discovered:
            if isinstance(entry, dict):
                mid = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
            else:
                mid = str(entry or "").strip()
            ml = mid.lower()
            if not mid or ml == "auto":
                continue
            if not (ml.startswith("auto/") or ml.startswith("auto-")):
                continue
            if _exclude_headless_bridge_route(ml):
                continue
            if _is_free_model_entry(entry if isinstance(entry, dict) else mid):
                return mid
    except Exception:
        pass
    return "auto"


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
            for _m in _omni_models_raw or []:
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
            model_probe = _probe_omniroute_model(
                omni_base, probe_model, timeout=_OMNI_MODEL_PROBE_TIMEOUT, use_cache=True
            )
        except Exception as e:
            model_probe = {
                "ok": False,
                "model": _env("OMNIROUTE_MODEL") or "auto",
                "error": f"probe_exception: {e}",
                "cached": False,
            }
    elif _env("JO_WEB_ENABLE_MODEL_PROBE") == "0":
        model_probe = {"ok": None, "skipped": True, "reason": "disabled_by_env"}
    elif omni_base and not omni_reachable:
        model_probe = {
            "ok": False,
            "model": _env("OMNIROUTE_MODEL") or "auto",
            "error": omni_info.get("error") or "omniroute_unreachable",
            "cached": False,
        }

    if model_probe is not None:
        if model_probe.get("ok") is True:
            reasons.append("default_model_probe_ok")
        elif model_probe.get("ok") is False:
            reasons.append("default_model_probe_failed")

    web_agent_mode = _env("JO_WEB_USE_AGENT") == "1"
    tools_exposed_to_model = web_agent_mode  # llm path sends plain chat (no tool schemas); agent path can use tools
    web_chat_path = "agent" if web_agent_mode else "llm"
    tools_note = (
        "Agent chat path enabled (Jo tools may be available via agent workflow)."
        if web_agent_mode
        else "Lightweight chat path: model calls do not include Jo tool schemas; selected models have no direct tool access in this mode."
    )

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
        "web_agent_mode": web_agent_mode,
        "web_chat_path": web_chat_path,
        "tools_exposed_to_model": tools_exposed_to_model,
        "tools_note": tools_note,
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


_FLOORPLAN_DIR = Path(__file__).resolve().parents[1] / "floorplan"


def _floorplan_json(name: str) -> Dict[str, Any]:
    """Read a JSON file from the floorplan/ map folder (empty dict when missing or invalid)."""
    try:
        return json.loads((_FLOORPLAN_DIR / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def _floorplan_summary() -> Dict[str, Any]:
    """Summary of the app's Floorplan map: project summary, parts and connections."""
    graph = _floorplan_json("graph.json")
    architecture = _floorplan_json("architecture.json")
    parts = [
        {
            "id": n.get("id"),
            "label": n.get("label"),
            "kind": n.get("kind"),
            "summary": n.get("summary", ""),
        }
        for n in graph.get("nodes", [])
    ]
    connections = [
        {
            "from": e.get("from"),
            "to": e.get("to"),
            "kind": e.get("kind"),
            "label": e.get("label", ""),
            "description": e.get("description", ""),
        }
        for e in graph.get("edges", [])
    ]
    return {
        "summary": (
            (architecture.get("project") or {}).get("summary")
            or (graph.get("project") or {}).get("summary")
            or ""
        ),
        "parts": parts,
        "connections": connections,
        "graph": graph,
        "architecture": architecture,
        "generatedAt": graph.get("generatedAt"),
    }


def _build_messages(message: str, history: Optional[list[Dict[str, str]]] = None) -> list[Dict[str, str]]:
    msgs: list[Dict[str, str]] = [
        {
            "role": "system",
            "content": "You are Jo, a self-creating AI agent speaking through the web GUI. Be direct, helpful, and authentic. Use conversation history when provided.",
        }
    ]
    # Include the app's Floorplan map summary so the model can reference how the app is put together.
    try:
        fp = _floorplan_summary()
        parts_label = ", ".join((p.get("label") or str(p.get("id") or "")) for p in fp.get("parts", [])[:20])
        extra = f"\n\nThe app's Floorplan map (interactive: floorplan/index.html): {fp.get('summary', '')}"
        if parts_label:
            extra += f"\nParts: {parts_label}."
        msgs[0]["content"] += extra
    except Exception:
        pass
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
            req_model = (requested_model or "").strip()
            env_model = (_env("OMNIROUTE_MODEL") or "").strip()

            req_is_explicit = bool(req_model and req_model.lower() != "auto")
            req_ml = (req_model or "").lower()
            # Auto-route/alias selections (e.g. auto/coding:free, auto/best-*) are not concrete models;
            # allow resilient fallback to working concrete OmniRoute models if the route is unusable in this env.
            req_is_auto_route = req_is_explicit and (
                req_ml.startswith("auto/") or req_ml.startswith("auto-") or req_ml == "auto"
            )
            strict_explicit = req_is_explicit and not req_is_auto_route

            # Discover models dynamically from OmniRoute (IDs + metadata) so free models can change over time.
            discovered_entries: list[Any] = []
            try:
                discovered_entries, _ = _fetch_omniroute_models(omni_base, timeout=6, use_cache=True)
            except Exception:
                discovered_entries = []

            # Fallback: minimal ID-only discovery if rich fetch failed
            if not discovered_entries:
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
                            if isinstance(item, dict):
                                mid = str(item.get("id") or item.get("name") or item.get("model") or "").strip()
                                if mid:
                                    discovered_entries.append(item)
                            else:
                                mid = str(item or "").strip()
                                if mid:
                                    discovered_entries.append(mid)
                except Exception:
                    pass

            def _skip_in_ci(ml: str, explicit: bool = False) -> bool:
                if explicit:
                    return False
                # Known unusable in headless CI OmniRoute unless explicitly allowed.
                return _exclude_headless_bridge_route(ml, explicit=False)

            def _entry_id(entry: Any) -> str:
                if isinstance(entry, dict):
                    return str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
                return str(entry or "").strip()

            def _entry_is_free(entry: Any, mid: str) -> bool:
                try:
                    if _is_free_model_entry(entry if isinstance(entry, dict) else mid):
                        return True
                except Exception:
                    pass
                ml = (mid or "").lower()
                return ":free" in ml or ml.endswith("/free") or "/free" in ml

            def _family_rank(mid: str) -> int:
                ml = (mid or "").lower()
                return 0 if any(
                    k in ml
                    for k in (
                        "llama", "qwen", "gemma", "mistral", "gpt-oss", "deepseek",
                        "glm", "kimi", "minimax", "phi", "smol",
                    )
                ) else 1

            def _is_auto_alias(mid: str) -> bool:
                ml = (mid or "").lower()
                return ml == "auto" or ml.startswith("auto/") or ml.startswith("auto-")

            # Build dynamic candidate pools from discovered models (free-first, no hardcoded model IDs).
            free_concrete: list[str] = []
            free_auto: list[str] = []
            other_concrete: list[str] = []
            other_auto: list[str] = []
            seen_disc: set[str] = set()
            for entry in discovered_entries:
                mid = _entry_id(entry)
                if not mid:
                    continue
                ml = mid.lower()
                if ml in seen_disc:
                    continue
                seen_disc.add(ml)
                if _skip_in_ci(ml):
                    continue
                is_auto = _is_auto_alias(ml)
                is_free = _entry_is_free(entry, mid)
                if is_free and is_auto:
                    free_auto.append(mid)
                elif is_free:
                    free_concrete.append(mid)
                elif is_auto:
                    other_auto.append(mid)
                else:
                    other_concrete.append(mid)

            free_concrete.sort(key=lambda m: (_family_rank(m), m.lower()))
            other_concrete.sort(key=lambda m: (_family_rank(m), m.lower()))
            # Prefer explicit "free" auto-routes first, then generic auto aliases.
            free_auto.sort(key=lambda m: (0 if ":free" in m.lower() or m.lower().endswith("/free") else 1, m.lower()))
            other_auto.sort(key=lambda m: m.lower())

            candidates: list[str] = []

            def _add_candidate(mid: str):
                if not mid:
                    return
                ml = mid.lower()
                if mid in candidates:
                    return
                explicit_same = (requested_model or "").strip().lower() == ml
                if _skip_in_ci(ml, explicit=explicit_same):
                    # don't hard-block explicit auto-routes here; let runtime try once then fallback
                    if not (req_is_auto_route and explicit_same):
                        return
                candidates.append(mid)

            # 1) explicit request (if any) — try selected model/route first
            if req_is_explicit:
                _add_candidate(req_model)
            # 2) explicit env model preference (if different)
            if env_model and env_model.lower() != "auto" and env_model not in candidates:
                _add_candidate(env_model)
            elif env_model and env_model.lower() == "auto" and not req_is_explicit:
                # if env requests auto, prioritize auto router after dynamic free models below
                pass

            # 3) dynamically discovered free models (update-anytime via OmniRoute)
            for m in free_concrete:
                _add_candidate(m)
            for m in free_auto:
                _add_candidate(m)

            # 4) generic auto router (dynamic gateway routing), useful when no specific free model responded
            if (not req_is_explicit) or req_is_auto_route or not any(not _is_auto_alias(c) for c in candidates):
                _add_candidate(env_model if (env_model and env_model.lower() == "auto") else "auto")

            # 5) if still sparse, allow other discovered non-free/non-auto models as last resort (best-effort)
            if not strict_explicit and (len(candidates) <= 1 or req_is_auto_route):
                for m in other_concrete[:10]:
                    _add_candidate(m)
                for m in other_auto:
                    _add_candidate(m)

            # 6) absolute fallback (no hardcoded free model ID)
            if not candidates:
                _add_candidate(env_model or "auto")
                _add_candidate("auto")

            # Strict explicit concrete model: preserve selection semantics (no silent fallback).
            # Explicit auto-routes keep fallbacks because the route itself may resolve to unusable upstreams.
            if strict_explicit:
                candidates = [req_model] if req_model else candidates[:1]

            tried = 0
            saw_env_error = False
            max_tries = 1 if strict_explicit else 20
            for om in candidates:
                if tried >= max_tries:
                    break
                oml = om.lower()
                explicit_same = (requested_model or "").strip().lower() == oml
                if _skip_in_ci(oml, explicit=explicit_same) and not (req_is_auto_route and explicit_same):
                    if strict_explicit:
                        errors.append(f"omniroute({om}): model unavailable in this environment")
                        break
                    continue
                if (
                    saw_env_error
                    and oml.startswith("auto")
                    and not strict_explicit
                    and not req_is_auto_route
                    and (env_model or "").lower() != oml
                ):
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
                    if strict_explicit:
                        break
                except Exception as oe:
                    last_oe = oe
                    emsg = str(oe)
                    errors.append(f"omniroute({om}): {oe}")
                    if strict_explicit:
                        break
                    low_emsg = emsg.lower()
                    # If provider/route is unavailable due to CI env/runtime config, keep trying others
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
    req_model = (requested_model or "").strip()
    req_ml = (req_model or "").lower()
    strict_explicit = bool(req_model and req_model.lower() != "auto") and not (
        req_ml.startswith("auto/") or req_ml.startswith("auto-") or req_ml == "auto"
    )
    if strict_explicit:
        # Preserve explicit concrete model selection semantics: do not hide which model failed.
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


def _proactive_suggestion(message: str, response: str) -> Optional[str]:
    """OpenDuet-style proactive follow-up suggestion."""
    m = (message or "").lower()
    r = (response or "").lower()
    suggestions = []
    if any(k in m for k in ("fix", "bug", "error", "traceback")) and "test" not in r:
        suggestions.append("Run the relevant tests to confirm the fix.")
    if any(k in m for k in ("add", "implement", "create", "new feature")) and "commit" not in r:
        suggestions.append("Commit and push the change when ready.")
    if any(k in m for k in ("refactor", "cleanup", "optimize")) and "verify" not in r:
        suggestions.append("Run smoke tests to verify nothing broke.")
    if not suggestions:
        return None
    return "💡 Next: " + " ".join(suggestions)


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
    web_agent_mode = _env("JO_WEB_USE_AGENT") == "1"
    tools_exposed_to_model = web_agent_mode

    if not message:
        return "Send a message to start chatting with Jo.", sid, {
            "provider": "system",
            "model": "none",
            "web_agent_mode": web_agent_mode,
            "tools_exposed_to_model": tools_exposed_to_model,
        }

    errors = []
    # Prefer lightweight direct LLM path (robust in minimal environments)
    try:
        text, meta = _run_via_llm(message, merged_history, requested_model=requested_model)
        if text:
            # OpenDuet-style proactive follow-up suggestion
            suggestion = _proactive_suggestion(message, text)
            if suggestion:
                text = text.rstrip() + "\n\n" + suggestion
            sess.append({"role": "user", "content": message})
            sess.append({"role": "assistant", "content": text})
            if len(sess) > _SESSION_MAX:
                del sess[:-_SESSION_MAX]
            _SESSIONS[sid] = sess
            out_meta = dict(meta or {})
            out_meta["web_agent_mode"] = web_agent_mode
            out_meta["tools_exposed_to_model"] = tools_exposed_to_model
            return text, sid, out_meta
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
                return text, sid, {
                    "provider": "agent",
                    "model": "agent",
                    "web_agent_mode": True,
                    "tools_exposed_to_model": True,
                }
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
    return resp, sid, {
        "provider": "fallback",
        "model": "unavailable",
        "web_agent_mode": web_agent_mode,
        "tools_exposed_to_model": tools_exposed_to_model,
    }


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
    web_agent_mode = _env("JO_WEB_USE_AGENT") == "1"
    try:
        response, sid, meta = await asyncio.wait_for(
            asyncio.to_thread(generate_response, req.message, history, req.session_id, req.model),
            timeout=120.0,
        )
    except Exception as e:
        response = _fallback_response(req.message, f"request_timeout_or_error: {e}")
        meta = {
            "provider": "fallback",
            "model": "unavailable",
            "web_agent_mode": web_agent_mode,
            "tools_exposed_to_model": web_agent_mode,
        }
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
        web_agent_mode = _env("JO_WEB_USE_AGENT") == "1"
        try:
            response, sid, meta = await asyncio.wait_for(
                asyncio.to_thread(generate_response, req.message, history, req.session_id, req.model),
                timeout=120.0,
            )
        except Exception as e:
            yield _sse({"error": str(e), "session_id": sid})
            response = _fallback_response(req.message, f"request_timeout_or_error: {e}")
            meta = {
                "provider": "fallback",
                "model": "unavailable",
                "web_agent_mode": web_agent_mode,
                "tools_exposed_to_model": web_agent_mode,
            }
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
                "web_agent_mode": bool((meta or {}).get("web_agent_mode")),
                "tools_exposed_to_model": bool((meta or {}).get("tools_exposed_to_model")),
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


@app.get("/v1/floorplan")
async def get_floorplan() -> Dict[str, Any]:
    """The app's Floorplan map data (graph + architecture summary) — for models and the GUI."""
    return await asyncio.to_thread(_floorplan_summary)


def _list_models() -> Dict[str, Any]:
    models: list[Dict[str, Any]] = []
    seen: set[str] = set()
    omni_base = _env("OMNIROUTE_BASE_URL")

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
                auto_probe = {
                    k: cached.get(k)
                    for k in ("ok", "model", "latency_ms", "error", "checked_at", "cached")
                    if k in cached
                }
        except Exception:
            auto_probe = None
    add("auto", "omniroute", "Auto (recommended)", recommended=True, probe=auto_probe)

    # Dynamically discover and expose all available free models from OmniRoute.
    # "Free" is detected from model IDs and metadata (pricing/tags/flags) when present.
    diagnostics: Dict[str, Any] = {
        "raw_discovered": 0,
        "free_detected": 0,
        "excluded_headless_bridge": 0,
        "excluded_not_free": 0,
        "exposed_free": 0,
        "include_headless_bridge_routes": _env_truthy("JO_WEB_OMNIROUTE_INCLUDE_HEADLESS_BRIDGE_ROUTES"),
        "excluded_headless_bridge_sample": [],
        "excluded_not_free_sample": [],
    }
    sample_limit = 10
    if omni_base:
        try:
            discovered, info = _fetch_omniroute_models(omni_base, timeout=5, use_cache=True)
            diagnostics["raw_discovered"] = len(discovered or [])
            diagnostics["fetch_reachable"] = bool(info.get("reachable"))
            diagnostics["fetch_cached"] = bool(info.get("cached"))
            if info.get("error"):
                diagnostics["fetch_error"] = info.get("error")
            for entry in discovered or []:
                if isinstance(entry, dict):
                    smid = str(entry.get("id") or entry.get("name") or entry.get("model") or "").strip()
                    meta = entry
                else:
                    smid = str(entry or "").strip()
                    meta = {}
                ml = smid.lower()
                if not smid or ml == "auto":
                    continue

                # Exclude routes commonly unusable in headless/CI unless explicitly allowed.
                if _exclude_headless_bridge_route(ml):
                    diagnostics["excluded_headless_bridge"] += 1
                    if len(diagnostics["excluded_headless_bridge_sample"]) < sample_limit:
                        diagnostics["excluded_headless_bridge_sample"].append(smid)
                    continue

                is_free = _is_free_model_entry(meta if meta else smid)
                if not is_free:
                    diagnostics["excluded_not_free"] += 1
                    if len(diagnostics["excluded_not_free_sample"]) < sample_limit:
                        diagnostics["excluded_not_free_sample"].append(smid)
                    continue
                diagnostics["free_detected"] += 1

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
                        extra["probe"] = {
                            k: cached_probe.get(k)
                            for k in ("ok", "latency_ms", "error", "checked_at", "cached")
                            if k in cached_probe
                        }
                except Exception:
                    pass
                before = len(models)
                add(smid, "omniroute", label=smid, **extra)
                if len(models) > before:
                    diagnostics["exposed_free"] += 1
        except Exception as e:
            diagnostics["error"] = f"{type(e).__name__}: {e}"

    diagnostics["listed"] = len(models)
    return {
        "models": models,
        "default": _env("OMNIROUTE_MODEL") or "auto",
        "diagnostics": diagnostics,
    }


@app.get("/v1/models")
async def list_models() -> Dict[str, Any]:
    return await asyncio.to_thread(_list_models)
