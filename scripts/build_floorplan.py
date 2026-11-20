#!/usr/bin/env python3
"""Build and validate the Jo Floorplan map — the interactive app map of this repo.

Floorplan (https://github.com/haydenschmitty/floorplan) maps your app: parts,
files, endpoints, screens and the connections between them. This script
generates the map for Jo:

- ``floorplan/graph.json``          — all data: nodes (parts + files + endpoints
                                      + screens + connections), outside services
                                      and the GUI<->backend wiring it verified.
- ``floorplan/architecture.json``   — the Floorplan-shape spec (nodes, edges,
                                      flows, tour, audience).
- ``floorplan/descriptions/*.json`` — one name/description/files/endpoints file
                                      per part (Floorplan convention).
- ``floorplan/index.html``          — the self-contained interactive map
                                      (search, click-to-zoom into parts, connections).
- ``floorplan/README.md``           — how to open and regenerate the map.

The scan is real: it lists files with ``git ls-files`` (so .gitignore is
respected), extracts the server endpoints from ``server/app.py`` and the GUI's
backend calls from ``gui/app.js``, and validates that every GUI request reaches
a real server endpoint — the "properly wired" check.

Usage:
    python scripts/build_floorplan.py            # regenerate everything
    python scripts/build_floorplan.py --check    # validate artifacts + wiring only
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "floorplan"

# ---------------------------------------------------------------------------
# Part definitions — the parts of the app ("architecture.json" shape)
# ---------------------------------------------------------------------------

NODES: List[Dict[str, Any]] = [
    {
        "id": "gui",
        "label": "Jo Web GUI",
        "kind": "ui",
        "summary": "The Jo Web GUI — a polished chat interface (gui/) served from GitHub Pages. It composes the chat page, streaming messages, the settings and shortcuts modals, and the theme toggle; it discovers the backend via gui/backend.json and polls its health.",
        "paths": ["gui/**"],
        "screens": ["gui/index.html"],
    },
    {
        "id": "gui.chat",
        "label": "Chat page & transport",
        "kind": "feature",
        "parent": "gui",
        "summary": "The main chat screen: the composer and message list. It transports chat via POST /v1/chat/stream (SSE) with POST /v1/chat as fallback; it polls /health; deltas grow the streaming bubble and the done event replaces it with the full response.",
        "paths": ["gui/app.js"],
        "endpoints": [
            {"method": "POST", "path": "/v1/chat/stream"},
            {"method": "POST", "path": "/v1/chat"},
        ],
    },
    {
        "id": "gui.status",
        "label": "Settings & status modals",
        "kind": "feature",
        "parent": "gui",
        "summary": "The Settings modal (API base auto-discovery via gui/backend.json or a manual URL, GET /health + GET /v1/status status card, model selection with search + refresh from GET /v1/models, theme toggle, clear saved base, export/import chats, copy diagnostics) and the shortcuts modal; styles.css, theme-init.js, the 404 page, sitemap/robots and the GUI README.",
        "paths": [
            "gui/index.html",
            "gui/styles.css",
            "gui/theme-init.js",
            "gui/404.html",
            "gui/README.md",
            "gui/robots.txt",
            "gui/sitemap.txt",
        ],
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/v1/models"},
        ],
    },
    {
        "id": "server",
        "label": "Jo Web Backend",
        "kind": "service",
        "summary": "The Jo Web Backend (server/app.py, FastAPI) — the HTTP contract used by the GitHub Pages GUI. Generation is OmniRoute-only for web chat.",
        "paths": ["server/**"],
    },
    {
        "id": "server.chat",
        "label": "Chat endpoints",
        "kind": "feature",
        "parent": "server",
        "summary": "POST /v1/chat (full reply) and POST /v1/chat/stream (SSE: delta / done / error events). Adds OpenDuet-style proactive follow-up suggestions and keeps per-session chat history (max 40 messages). The web GUI is the main caller.",
        "paths": ["server/app.py", "server/run.ps1"],
        "endpoints": [
            {"method": "POST", "path": "/v1/chat"},
            {"method": "POST", "path": "/v1/chat/stream"},
        ],
    },
    {
        "id": "server.status",
        "label": "Status & models endpoints",
        "kind": "feature",
        "parent": "server",
        "summary": "GET /health and GET /v1/status: provider/model, OmniRoute reachability, dynamic model probe results, readiness reasons, and the web chat mode/tools flags (web_agent_mode, web_chat_path, tools_exposed_to_model, tools_note); GET /v1/models: the curated OmniRoute catalog — 'auto' plus dynamically discovered free models, with headless/CI bridge routes excluded.",
        "paths": ["server/app.py"],
        "endpoints": [
            {"method": "GET", "path": "/health"},
            {"method": "GET", "path": "/v1/status"},
            {"method": "GET", "path": "/v1/models"},
            {"method": "GET", "path": "/v1/floorplan"},
        ],
    },
    {
        "id": "ouroboros",
        "label": "Ouroboros — Jo's agent core",
        "kind": "service",
        "summary": "Ouroboros (ouroboros/) is Jo's agent: the direct-chat agent workflow (supervisor.workers._get_chat_agent → OuroborosAgent.handle_task, the LLM tool loop) plus the lightweight LLM path (ouroboros/llm.py). ~115 modules: loop, tools, memory, context, pipeline, evolution, self-healing, tracing, skills, goals, awareness, token ledger, budget router, work checkpoint, ... plus ouroboros/tools/ — the plugin tool registry.",
        "paths": ["ouroboros/**"],
    },
    {
        "id": "ouroboros.tools",
        "label": "Tool registry & modules",
        "kind": "library",
        "parent": "ouroboros",
        "summary": "The Jo tool system: ToolRegistry + ~50 tool modules (file ops, shell, web research, git, github, database, browser, skills, evolution, neural map, vision, dashboard, analytics, ...), schemas + permissions + orchestration.",
        "paths": [
            "ouroboros/tools/**",
            "ouroboros/tool_orchestrator.py",
            "ouroboros/tool_executor.py",
            "ouroboros/tool_router.py",
            "ouroboros/tool_permissions.py",
        ],
    },
    {
        "id": "ouroboros.memory",
        "label": "Memory (episodic + hybrid)",
        "kind": "feature",
        "parent": "ouroboros",
        "summary": "Narrative memory: ouroboros/memory.py, memory_consolidator.py, episodic_memory.py, hybrid_memory.py — Jo remembers experiences across sessions and merges them into durable notes.",
        "paths": [
            "ouroboros/memory.py",
            "ouroboros/memory_consolidator.py",
            "ouroboros/episodic_memory.py",
            "ouroboros/hybrid_memory.py",
        ],
    },
    {
        "id": "ouroboros.identity",
        "label": "Identity & scratchpad",
        "kind": "feature",
        "parent": "ouroboros",
        "summary": "Jo's identity (memory/identity.md, constitution.json, awareness.jsonl) and scratchpad (memory/scratchpad.md, memory/buglog.json) — the stable self plus active working notes.",
        "paths": ["memory/**"],
    },
    {
        "id": "supervisor",
        "label": "Jo Supervisor",
        "kind": "worker",
        "summary": "The Jo Supervisor (supervisor/) manages worker processes, queues, state (supervisor/state.json, workers.py), git/github ops, health monitoring and watchdogs that restart OmniRoute and the backend when they die.",
        "paths": ["supervisor/**"],
    },
    {
        "id": "vault",
        "label": "Vault — narrative memory",
        "kind": "data",
        "summary": "Vault (vault/) is Jo's long-term memory: markdown notes (memories, tasks, journal, concepts, tools, analysis, projects, structures, vision) with integrity checks (vault/.vault) and an auto-vault index.",
        "paths": ["vault/**"],
    },
    {
        "id": "prompts",
        "label": "Prompts",
        "kind": "config",
        "summary": "System & product prompts (prompts/): SYSTEM.md (the Jo persona) and CONSCIOUSNESS.md — what Jo speaks as through the web GUI.",
        "paths": ["prompts/**"],
    },
    {
        "id": "scripts",
        "label": "Scripts",
        "kind": "script",
        "summary": "Dev & ops scripts (scripts/): build_floorplan.py (generates/validates the Floorplan map), check_module_health.py + check_bugs.py + check_principle5.py + self_check.py (health & invariants), health_audit.py + code_health_monitor.py + code_health_analysis.py (code health), watchdog.py + sys_ops.py + debug_check.py (system ops), colab_launcher.py, validate_data_files.py, pre-commit.",
        "paths": ["scripts/**"],
    },
    {
        "id": "config",
        "label": "Config",
        "kind": "config",
        "summary": "Config: the config/ manager (default.yaml, overrides.yaml, check_params.py, health_audit.py), .env.example, pyproject.toml, VERSION, requirements.txt — packaging and environment.",
        "paths": [".jo_state/**", "config/**", ".env.example", "pyproject.toml", "VERSION", "requirements.txt"],
    },
    {
        "id": "infra",
        "label": "GitHub CI & deployment",
        "kind": "infra",
        "summary": "GitHub Actions: pages.yml (GUI validation), web-backend.yml (starts OmniRoute + the backend, opens a cloudflare tunnel, publishes gui/backend.json, deploys Pages, and keeps the backend alive), Dockerfile, docker-compose.yml, Makefile.",
        "paths": [".github/**", "Dockerfile", "docker-compose.yml", "Makefile", ".gitignore", ".jo_protected"],
    },
    {
        "id": "docs",
        "label": "Docs & plans",
        "kind": "library",
        "summary": "Reference material: BIBLE.md (Jo's principles), README.md, AGENTS.md (the development guide), LICENSE, docs/**, .pi/**, .jo_rules/**, .jo_skills/**, floorplan/README.md.",
        "paths": ["BIBLE.md", "README.md", "AGENTS.md", "LICENSE", "docs/**", ".pi/**", ".jo_rules/**", ".jo_skills/**", "floorplan/**"],
    },
    {
        "id": "tests",
        "label": "Tests",
        "kind": "test",
        "summary": "The pytest suite (tests/): smoke tests, the web backend contract (tests/test_web_backend.py), the GUI end-to-end (tests/test_gui_smoke.py), memory, vault, vision, runtime regressions, git-sha fixes.",
        "paths": ["tests/**"],
    },
]

# Architecture-level edges (the scanner can't see these): GUI->backend wiring,
# supervisor->agent, server->providers/memory.
EDGES: List[Dict[str, Any]] = [
    {
        "from": "gui",
        "to": "server",
        "kind": "http",
        "label": "GET /health",
        "description": "gui/app.js checkHealth() polls GET /health (init, 30s loop, refresh toggle); the status card shows reachability, provider/model, OmniRoute, probe and web chat mode/tools flags.",
    },
    {
        "from": "gui",
        "to": "server",
        "kind": "http",
        "label": "GET /v1/models",
        "description": "refreshModels() loads the model select from GET /v1/models (settings + header pill); the GUI shows 'auto' plus discovered OmniRoute free models.",
    },
    {
        "from": "gui",
        "to": "server",
        "kind": "http",
        "label": "POST /v1/chat/stream",
        "description": "sendToJo(): the GUI posts the chat message; the backend streams SSE deltas into the message bubble; the done event stores the full response with provider/model/elapsed_ms.",
    },
    {
        "from": "gui",
        "to": "server",
        "kind": "http",
        "label": "POST /v1/chat",
        "description": "sendToJo(): fallback when /v1/chat/stream is unavailable or not SSE; the GUI reads response/session_id/provider/model/elapsed_ms.",
    },
    {
        "from": "gui",
        "to": "cloudflare-tunnel",
        "kind": "http",
        "label": "backend.json discovery",
        "description": "The hosted GUI reads ./backend.json (auto-discovery of apiBase, updatedAt, commit, runId, workflow) so the browser reaches the backend through the published tunnel URL.",
    },
    {
        "from": "gui",
        "to": "github-pages",
        "kind": "http",
        "label": "Pages host",
        "description": "The GUI is served from GitHub Pages (web-backend.yml owns the deploy); the browser connects to the backend via the tunnel.",
    },
    {
        "from": "server.chat",
        "to": "ouroboros",
        "kind": "call",
        "label": "generate_response → _build_messages + _run_via_llm",
        "description": "The lightweight chat path: builds messages (system prompt + history) and calls OmniRoute chat completions with dynamic model candidates (strict semantics for explicit picks, fallbacks otherwise).",
    },
    {
        "from": "server.chat",
        "to": "supervisor",
        "kind": "call",
        "label": "_run_via_agent → supervisor.workers._get_chat_agent",
        "description": "The agent path (JO_WEB_USE_AGENT=1) runs the direct-chat agent workflow so Jo tools may be used, subject to the selected model.",
    },
    {
        "from": "server.chat",
        "to": "ouroboros.identity",
        "kind": "call",
        "label": "system prompt (persona)",
        "description": "server/app.py _build_messages() opens the chat with the Jo web chat system prompt; prompts/SYSTEM.md is the deeper identity.",
    },
    {
        "from": "server",
        "to": "omniroute",
        "kind": "http",
        "label": "chat.completions",
        "description": "OmniRoute-only backend: server/app.py calls OmniRoute at OMNIROUTE_BASE_URL; /models discovery, /health and usability probes are OmniRoute calls too.",
    },
    {
        "from": "supervisor",
        "to": "ouroboros",
        "kind": "rpc",
        "label": "agent.handle_task",
        "description": "Each worker process owns an OuroborosAgent (supervisor/workers.py _get_chat_agent); handle_task runs tasks through the LLM tool loop (tools, memory, self-evolution).",
    },
    {
        "from": "ouroboros.tools",
        "to": "supervisor",
        "kind": "rpc",
        "label": "tool registration",
        "description": "Tool modules register into the ToolRegistry at agent boot; the supervisor watches workers and restarts them when they die.",
    },
    {
        "from": "ouroboros.memory",
        "to": "vault",
        "kind": "data",
        "label": "vault notes",
        "description": "Ouroboros reads and writes the vault: memories, tasks, journal, concepts, tools, analysis, projects, .vault integrity.",
    },
    {
        "from": "ouroboros.identity",
        "to": "prompts",
        "kind": "config",
        "label": "system prompts",
        "description": "Jo's identity and scratchpad are the stable self; prompts/SYSTEM.md and CONSCIOUSNESS.md are the persona text Jo runs on.",
    },
    {
        "from": "tests",
        "to": "server",
        "kind": "test",
        "label": "backend contract tests",
        "description": "tests/test_web_backend.py: TestClient against the real server/app.py — /v1/chat, /v1/chat/stream (SSE), /health, /v1/status, /v1/models, session history.",
    },
    {
        "from": "tests",
        "to": "gui",
        "kind": "test",
        "label": "GUI e2e smoke tests",
        "description": "tests/test_gui_smoke.py: opens gui/ with a real Chromium, stubs the backend contract, asserts the chat flow renders the backend reply and the status card reflects /health web chat mode.",
    },
]

FLOWS: List[Dict[str, Any]] = [
    {
        "id": "web_chat",
        "title": "Web chat round trip",
        "description": "Browser GUI to Ouroboros (or OmniRoute) and back:",
        "steps": [
            {
                "node": "gui.chat",
                "note": "User types in the composer and sends: sendMessage() posts {message, history, session_id, model} to POST /v1/chat/stream.",
            },
            {
                "node": "server.chat",
                "note": "The backend shares the GUI's session_id; streams SSE deltas back; the GUI appends them to the streaming bubble.",
            },
            {
                "node": "ouroboros",
                "note": "generate_response → _run_via_llm: builds messages, calls OmniRoute chat completions with dynamic candidate models (free models first; strict semantics for explicit picks).",
            },
            {
                "node": "omniroute",
                "note": "OmniRoute returns tokens; the backend relays them as delta events.",
            },
            {
                "node": "gui.chat",
                "note": "On done, the GUI stores the full response (provider, model, elapsed_ms) and shows the provider chip; the message is recorded in the chat history.",
            },
        ],
    },
    {
        "id": "backend_status",
        "title": "Backend discovery & status",
        "description": "How the GUI finds the backend and shows its status:",
        "steps": [
            {
                "node": "gui.status",
                "note": "Open Settings: API base (auto-discovery from gui/backend.json, or a manual URL), Connection status card, model list, theme, export/import chats.",
            },
            {
                "node": "server.status",
                "note": "GET /health + GET /v1/status report provider/model, OmniRoute reachability, model probe results, readiness reasons, and the web chat mode/tools flags.",
            },
            {
                "node": "cloudflare-tunnel",
                "note": "The web-backend workflow publishes gui/backend.json with the tunnel URL each run.",
            },
            {
                "node": "github-pages",
                "note": "The GUI is served from Pages; the tunnel links browser → backend.",
            },
        ],
    },
]

TOUR: List[Dict[str, Any]] = [
    {
        "node": "gui.chat",
        "title": "The chat screen",
        "note": "Jo Web GUI — polished chat UX. No browser extension or third-party account: it talks straight to the Jo backend.",
    },
    {
        "node": "server.chat",
        "title": "The chat endpoints",
        "note": "Jo Web Backend: POST /v1/chat (full reply) and POST /v1/chat/stream (SSE deltas back into the bubble).",
    },
    {
        "node": "ouroboros",
        "title": "The agent brain",
        "note": "Ouroboros runs the agent workflow: LLM tool loop, tools, memory, self-evolution. The lightweight LLM path (ouroboros/llm.py) is the alternative generation route.",
    },
    {
        "node": "vault",
        "title": "The memory (vault)",
        "note": "Narrative memory: memories, tasks, journal, concepts — the long-term store behind Jo's memory.",
    },
    {
        "node": "supervisor",
        "title": "The supervisor",
        "note": "Keeps workers running, queues tasks, watches health, and restarts OmniRoute/backend when needed.",
    },
    {
        "node": "gui.status",
        "title": "The settings & status",
        "note": "Backend discovery, connection health, model picker, theme, and chat history export/import.",
    },
]

OUTSIDE_SERVICES: List[Dict[str, Any]] = [
    {
        "id": "omniroute",
        "label": "OmniRoute",
        "summary": "Model gateway for Jo web chat: dynamic /models discovery, usability probes (/health, /v1/models) and chat completions at OMNIROUTE_BASE_URL. OmniRoute-only for web generation (no local/direct/public fallback in server/app.py).",
        "hosts": ["127.0.0.1:20128"],
    },
    {
        "id": "cloudflare-tunnel",
        "label": "Cloudflare tunnel (trycloudflare.com)",
        "summary": "Ephemeral HTTPS tunnel from GitHub Actions to the local backend; the tunnel URL is published as gui/backend.json so the hosted GUI can reach the backend.",
        "hosts": [],
    },
    {
        "id": "github-pages",
        "label": "GitHub Pages",
        "summary": "Hosts the Jo web GUI (gui/) with the auto-discovered backend base URL from gui/backend.json.",
        "hosts": ["josolinap.github.io/jo"],
    },
    {
        "id": "github-actions",
        "label": "GitHub Actions",
        "summary": "Owns the live backend deployment: starts OmniRoute + backend, opens the tunnel, publishes gui/backend.json, deploys Pages, keeps the backend alive.",
        "hosts": ["api.github.com"],
    },
    {
        "id": "playwright",
        "label": "Playwright",
        "summary": "Drives the GUI end-to-end in the smoke test: opens gui/ with a real Chromium, stubs the backend contract, asserts the chat flow renders the backend reply.",
        "hosts": [],
    },
]

# ---------------------------------------------------------------------------
# Scanning helpers
# ---------------------------------------------------------------------------


def truncate(s: str, n: int = 110) -> str:
    s = " ".join(str(s or "").split())
    return s[: n - 1] + "…" if len(s) > n else s


def git_files() -> List[str]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
            capture_output=True,
            timeout=60,
            check=True,
        )
    except Exception as exc:  # pragma: no cover - defensive
        raise SystemExit(f"git ls-files failed: {exc}")
    return [f for f in out.stdout.decode("utf-8", "replace").split("\0") if f]


def file_description(path: str) -> str:
    """Best-effort description of a file: docstring, then first non-empty line for docs."""
    full = ROOT / path
    try:
        text = full.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    for pattern in (r'"""(.*?)"""', r"'''(.*?)'''"):
        m = re.search(pattern, text, re.S)
        if m:
            for line in m.group(1).splitlines():
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 3:
                    return truncate(line, 110)
    if path.endswith((".md", ".markdown")):
        for line in text.splitlines():
            line = line.strip().lstrip("#").strip()
            if line and len(line) > 3:
                return truncate(line, 110)
    # fallback: first comment line for .js/.ts files
    if path.endswith((".js", ".ts")):
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("//") and len(line[2:].strip()) > 5:
                return truncate(line[2:].strip(), 110)
    return ""


def extract_endpoints() -> List[Dict[str, str]]:
    """Server endpoints from server/app.py decorators: @app.get/post/...("path")."""
    text = (ROOT / "server/app.py").read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r'@app\.(get|post|put|patch|delete)\(\s*["\']([^"\']+)["\']')
    seen = set()
    out = []
    for m in pattern.finditer(text):
        method, path = m.group(1).upper(), m.group(2)
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        out.append({"method": method, "path": path})
    return sorted(out, key=lambda e: (e["method"], e["path"]))


def extract_gui_requests() -> List[str]:
    """GUI backend calls from gui/app.js: fetch(base + "/...") / fetch("./backend.json")."""
    text = (ROOT / "gui/app.js").read_text(encoding="utf-8", errors="replace")
    pattern = re.compile(r'fetch\((?:base \+ )?["\']([^"\']+)["\']')
    seen = set()
    out = []
    for m in pattern.finditer(text):
        p = m.group(1).strip()
        if p.startswith("./"):
            p = p[2:]
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return sorted(out)


def _pattern_matches(pattern: str, path: str) -> bool:
    if pattern.endswith("/**"):
        return path.startswith(pattern[:-2])
    if pattern.endswith("/"):
        return path.startswith(pattern)
    return path == pattern


def _depth(node_id: str) -> int:
    return len([p for p in node_id.split(".") if p]) or 1


def assign_file(nodes: List[Dict[str, Any]], path: str) -> Optional[Dict[str, Any]]:
    """Assign a file to the deepest node claiming it (longest literal pattern on ties)."""
    best: Optional[Dict[str, Any]] = None
    best_key = (-1, -1)
    for n in nodes:
        matched = 0
        for pat in n.get("paths", []):
            if _pattern_matches(pat, path):
                matched = max(matched, len(pat))
        if not matched:
            continue
        key = (_depth(n["id"]), matched)
        if key > best_key:
            best, best_key = n, key
    if best is None:
        for n in nodes:
            if n["id"] == "docs":
                best = n
                break
    return best


def match_gui_requests(gui_paths: List[str], endpoints: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Map each GUI request to the server endpoint that answers it."""
    out = []
    for p in gui_paths:
        if p == "backend.json":
            out.append({"guiRequest": p, "endpoint": None, "matched": True, "kind": "discovery"})
            continue
        hits = [f'{e["method"]} {e["path"]}' for e in endpoints if p == e["path"]]
        if hits:
            for h in hits:
                out.append({"guiRequest": p, "endpoint": h, "matched": True})
        else:
            out.append({"guiRequest": p, "endpoint": None, "matched": False})
    return out


# ---------------------------------------------------------------------------
# Graph data (graph.json)
# ---------------------------------------------------------------------------

GUI_TO_SERVER_DESCRIPTIONS: Dict[str, str] = {
    "GET /health": "gui/app.js checkHealth() polls GET /health (init, 30s loop, refresh); the status card shows reachability, provider/model, OmniRoute, probe and web chat mode/tools flags.",
    "GET /v1/models": "refreshModels() loads the model select from GET /v1/models (settings + header pill); the GUI shows 'auto' plus discovered OmniRoute free models.",
    "POST /v1/chat/stream": "sendToJo(): the GUI posts the chat message; the backend streams SSE deltas into the message bubble; the done event stores the full response with provider/model/elapsed_ms.",
    "POST /v1/chat": "sendToJo(): fallback when /v1/chat/stream is unavailable or not SSE; the GUI reads response/session_id/provider/model/elapsed_ms.",
}


def merge_edges(edges_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop duplicate connections (same from/to/kind/label)."""
    seen = set()
    out = []
    for e in edges_list:
        key = (e["from"], e["to"], e["kind"], e["label"])
        if key in seen:
            continue
        seen.add(key)
        out.append(e)
    return out


def build_graph() -> Dict[str, Any]:
    files = git_files()
    endpoints = extract_endpoints()
    gui_paths = extract_gui_requests()

    nodes_out: List[Dict[str, Any]] = []
    for n in NODES:
        assigned = [f for f in files if assign_file(NODES, f)["id"] == n["id"]]
        node: Dict[str, Any] = {
            "id": n["id"],
            "label": n["label"],
            "kind": n["kind"],
            "parent": n.get("parent"),
            "summary": n["summary"],
            "paths": n.get("paths", []),
            "files": [{"path": f, "description": file_description(f)} for f in sorted(assigned)],
            "endpoints": n.get("endpoints", []),
            "screens": n.get("screens", []),
        }
        nodes_out.append(node)

    # GUI -> server endpoint edges, derived from the GUI's real calls.
    request_matches = match_gui_requests(gui_paths, endpoints)
    gui_server_edges: List[Dict[str, Any]] = []
    seen_eps = set()
    for m in request_matches:
        if not m["matched"] or not m["endpoint"] or m["endpoint"] in seen_eps:
            continue
        seen_eps.add(m["endpoint"])
        gui_server_edges.append(
            {
                "from": "gui",
                "to": "server",
                "kind": "http",
                "label": m["endpoint"],
                "description": GUI_TO_SERVER_DESCRIPTIONS.get(m["endpoint"], f"gui calls {m['endpoint']}"),
            }
        )

    graph_edges = merge_edges(EDGES + gui_server_edges)

    graph = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generatedBy": "scripts/build_floorplan.py",
        "project": {
            "name": "Jo",
            "summary": (
                "Jo is a self-modifying AI agent (the Ouroboros agent core) with a FastAPI web chat backend "
                "(server/) and a browser GUI (gui/). Web chat: GUI → server (/v1/chat, /v1/chat/stream) → "
                "Ouroboros agent workflow (tools, memory, self-evolution) or the lightweight LLM path via "
                "OmniRoute. The supervisor manages workers; the vault is Jo's narrative memory; prompts, "
                "config, scripts and tests surround the app."
            ),
            "entrypoints": ["ouroboros/agent.py", "server/app.py", "gui/index.html"],
        },
        "nodes": nodes_out,
        "edges": graph_edges,
        "requestToEndpoint": request_matches,
        "outsideServices": OUTSIDE_SERVICES,
        "counts": {
            "nodes": len(nodes_out),
            "files": sum(len(n["files"]) for n in nodes_out),
            "endpoints": len(endpoints),
            "edges": len(graph_edges),
            "screens": sum(len(n["screens"]) for n in nodes_out),
        },
    }
    return graph


# ---------------------------------------------------------------------------
# Map writer (floorplan/index.html)
# ---------------------------------------------------------------------------

INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jo — Floorplan map</title>
<style>
:root { --bg:#f5f7fb; --panel:#fff; --ink:#1c2430; --muted:#6b768c; --line:#dde4ee;
        --accent:#2563eb; --chip:#eef2f7; --card-hover:#f0f4fb; --shadow:#00000010; }
html[data-theme="dark"] { --bg:#11161d; --panel:#1a2129; --ink:#e8edf5; --muted:#9aa6b8;
        --line:#2a3341; --accent:#6ea8fe; --chip:#242d38; --card-hover:#202836; --shadow:#00000066; }
* { box-sizing: border-box; }
body { margin:0; font:14px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; color:var(--ink); background:var(--bg); }
.top { display:flex; align-items:center; gap:16px; padding:14px 20px; background:var(--panel); border-bottom:1px solid var(--line); position:sticky; top:0; z-index:2; flex-wrap:wrap; }
.top h1 { font-size:16px; margin:0; }
.top .sub { color:var(--muted); font-size:12px; }
.top-right { display:flex; gap:8px; align-items:center; margin-left:auto; }
input[type=search] { width:220px; padding:6px 10px; border:1px solid var(--line); border-radius:8px; background:var(--bg); color:var(--ink); }
button.icon { padding:6px 10px; border:1px solid var(--line); border-radius:8px; background:var(--panel); color:var(--ink); cursor:pointer; }
button.icon:hover { background:var(--card-hover); }
.wrap { display:flex; }
.board-wrap { position:relative; overflow:hidden; height:calc(100vh - 56px); flex:1; }
.board { display:grid; grid-template-columns:repeat(auto-fill, minmax(300px, 1fr)); gap:14px; padding:18px; transform-origin:0 0; transition:transform 80ms linear; }
.card { border:1px solid var(--line); border-radius:10px; background:var(--panel); padding:12px 14px; cursor:pointer; transition:transform 80ms, box-shadow 80ms, border-color 80ms; }
.card:hover { transform:translateY(-2px); box-shadow:0 6px 18px var(--shadow); border-color:var(--accent); }
.card-head { display:flex; gap:8px; align-items:center; }
.card-id { font-weight:650; }
.card-summary { margin:8px 0 0; color:var(--ink); font-size:12.5px; }
.card-foot { margin-top:8px; color:var(--muted); font-size:11px; }
.chip { font-size:10px; font-weight:600; padding:2px 7px; border-radius:999px; background:var(--chip); color:var(--muted); }
.chip-ui { background:#e6f0ff; color:#1d4ed8; }
.chip-service { background:#e6f0ff; color:#1d4ed8; }
.chip-worker { background:#fef3c7; color:#92400e; }
.chip-library { background:#ede9fe; color:#5b21b6; }
.chip-feature { background:#e0e7ff; color:#3730a3; }
.chip-data { background:#d1fae5; color:#065f46; }
.chip-config { background:#fef3c4; color:#8a5a00; }
.chip-test { background:#fee2e2; color:#991b1b; }
.chip-infra { background:#e0e0e0; color:#374151; }
.chip-files { background:var(--chip); color:var(--muted); }
.detail { position:fixed; right:0; top:0; bottom:0; width:36%; background:var(--panel); border-left:1px solid var(--line); overflow-y:auto; padding:18px 22px; display:none; z-index:3; }
.detail[hidden] { display:none; }
.detail-head { display:flex; align-items:center; gap:10px; }
.detail-head h2 { font-size:15px; margin:0; }
.detail-summary { color:var(--muted); font-size:12.5px; margin:8px 0 0; }
.detail section { margin-top:16px; }
.detail h3 { font-size:11px; text-transform:uppercase; letter-spacing:.06em; color:var(--muted); margin:0 0 6px; }
.file-item { padding:5px 0; border-bottom:1px dashed var(--line); }
.file-item .file-path { display:block; font-size:12px; font-family:ui-monospace, Consolas, monospace; }
.file-item .file-desc { display:block; font-size:11px; color:var(--muted); }
.node-tag { font-size:11px; color:var(--muted); }
.edge { padding:6px 0; border-bottom:1px dashed var(--line); font-size:12px; }
.edge .edge-dir { display:block; font-size:11px; font-family:ui-monospace, Consolas, monospace; }
.edge .edge-label { display:inline-block; font-size:11px; font-weight:650; color:var(--accent); margin-left:4px; }
.edge .edge-desc { display:block; font-size:11px; color:var(--muted); margin-top:2px; }
.ep { font-size:12px; font-family:ui-monospace, Consolas, monospace; padding:3px 0; }
.screen { font-size:12px; font-family:ui-monospace, Consolas, monospace; padding:3px 0; }
.note { color:var(--muted); font-size:11px; }
.footer { color:var(--muted); font-size:11px; padding:8px 22px 40px; }
@media (max-width:820px) { .detail { width:100%; } .top h1 { display:none; } input[type=search] { width:140px; } }
</style>
</head>
<body>
<header class="top">
  <h1>Jo · Floorplan</h1>
  <span class="sub" id="stats"></span>
  <span class="sub" id="project-summary"></span>
  <div class="top-right">
    <input type="search" id="search" placeholder="Search nodes…" aria-label="Search nodes">
    <button class="icon" id="reset-zoom" title="Reset zoom">Reset zoom</button>
    <button class="icon" id="theme-toggle" title="Toggle theme">Theme</button>
  </div>
</header>
<main class="wrap">
  <div class="board-wrap" id="board-wrap">
    <div class="board" id="board"></div>
  </div>
  <aside class="detail" id="detail" hidden>
    <div class="detail-head"><button class="back" id="detail-back" style="cursor:pointer">← Back</button><h2 id="detail-title"></h2><span class="chip chip-ui" id="detail-kind"></span></div>
    <p class="detail-summary" id="detail-summary"></p>
    <section><h3>Files</h3><div id="detail-files"></div></section>
    <section><h3>Children</h3><div id="detail-children"></div></section>
    <section><h3>Endpoints</h3><div id="detail-endpoints"></div></section>
    <section><h3>Screens</h3><div id="detail-screens"></div></section>
    <section><h3>Connections</h3><div id="detail-edges"></div></section>
  </aside>
</main>
<p class="footer">Jo Floorplan — interactive map of Jo. Regenerate with <code>python scripts/build_floorplan.py</code>.</p>
<script>var GRAPH = __GRAPH_JSON__;</script>
<script>__MAP_JS__</script>
</body>
</html>
"""

# ---------------------------------------------------------------------------
# architecture.json
# ---------------------------------------------------------------------------


def architecture_doc() -> Dict[str, Any]:
    return {
        "$schema": "floorplan/architecture@1",
        "project": {
            "name": "Jo",
            "summary": (
                "Jo is a self-modifying AI agent (the Ouroboros agent core) with a FastAPI web chat backend "
                "(server/) and a browser GUI (gui/). Web chat: GUI → server (/v1/chat, /v1/chat/stream) → "
                "Ouroboros agent workflow (tools, memory, self-evolution) or the lightweight LLM path via "
                "OmniRoute. The supervisor manages workers; the vault is Jo's narrative memory."
            ),
            "entrypoints": ["ouroboros/agent.py", "server/app.py", "gui/index.html"],
        },
        "nodes": [
            {
                "id": n["id"],
                "label": n["label"],
                "kind": n["kind"],
                "parent": n.get("parent"),
                "summary": n["summary"],
                "details": n.get("details", ""),
                "paths": n.get("paths", []),
                "endpoints": n.get("endpoints", []),
                "screens": n.get("screens", []),
            }
            for n in NODES
        ],
        "edges": EDGES,
        "flows": FLOWS,
        "tour": TOUR,
        "audience": "everyone",
    }


# ---------------------------------------------------------------------------
# Writers & validators
# ---------------------------------------------------------------------------


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_descriptions(graph: Dict[str, Any]) -> None:
    ddir = OUT / "descriptions"
    ddir.mkdir(parents=True, exist_ok=True)
    for n in graph["nodes"]:
        doc = {
            "name": n["label"],
            "description": n["summary"],
            "files": [f["path"] for f in n["files"]],
            "endpoints": n["endpoints"],
            "screens": n["screens"],
        }
        if n.get("parent"):
            doc["parent"] = n["parent"]
        write_json(ddir / f"{n['id']}.json", doc)


def write_readme() -> None:
    (OUT / "README.md").write_text(
        """# Jo Floorplan map

An interactive map of the Jo app — the **whole picture** of the web chat stack:

- **Jo Web GUI** (`gui/`) — the polished chat interface hosted on GitHub Pages; discovers the backend via `gui/backend.json` and polls its health.
- **Jo Web Backend** (`server/app.py`) — the FastAPI web contract: `POST /v1/chat`, `POST /v1/chat/stream` (SSE), `GET /health`, `GET /v1/status`, `GET /v1/models`.
- **Ouroboros** — Jo's agent core (`ouroboros/`, ~115 modules + the `ouroboros/tools/` plugin registry).
- **Jo Supervisor** — process management (`supervisor/`).
- **Vault** — Jo's narrative memory (`vault/`); **Identity & scratchpad** (`memory/`).
- **Prompts**, **Config**, **Scripts**, **Tests**, **Docs** and **GitHub CI & deployment**.

Every edge was checked in code — e.g. the GUI↔backend wiring (`gui.chat → server: POST /v1/chat/stream`, `server.chat → ouroboros: generate_response`, `server → omniroute`) is extracted from the actual calls in `gui/app.js` and `server/app.py` by `scripts/build_floorplan.py`; `requestToEndpoint` lists every GUI request and the server endpoint it reaches.

## Open the map

Open [`index.html`](index.html) (it is self-contained, no dependencies), or serve it:

```bash
python -m http.server -d floorplan 8000   # then open http://localhost:8000/
```

- Search the board by node name, part, summary, or file path.
- Click a part (or a child part) to zoom into it: its files, children, endpoints, screens and connections.
- Wheel to zoom, drag to pan, Esc to go back, `/` to focus search.
- Toggle dark/light from the header.

## Regenerate & validate

```bash
python scripts/build_floorplan.py            # regenerate the map (graph.json, architecture.json, descriptions/, index.html)
python scripts/build_floorplan.py --check    # validate artifacts + wiring only (what CI runs)
```

The builder scans the repo via `git ls-files` (so `.gitignore` is respected), extracts the
server endpoints from `server/app.py` and the GUI's backend calls from `gui/app.js`, and asserts
that every GUI request reaches a real server endpoint, every node id referenced by an edge exists,
and every listed file exists on disk.
""",
        encoding="utf-8",
    )


def build_recent_work(limit: int = 10) -> Dict[str, Any]:
    """Recent work from recent git commits (Floorplan format: tasks with items)."""

    def _run(cmd):
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, timeout=30)
            return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else ""
        except Exception:
            return ""

    shas = _run(["git", "log", f"-{limit}", "--pretty=format:%H"]).split()
    tasks = []
    for sha in shas:
        subject = _run(["git", "show", "-s", "--pretty=format:%s", sha]).strip()
        body = _run(["git", "show", "-s", "--pretty=format:%b", sha]).strip()
        title = truncate(subject, 70) or sha[:7]
        stat = _run(["git", "show", "--name-status", "--format=", sha])
        items = []
        for line in stat.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            status = parts[0] if parts else ""
            path = parts[-1] if len(parts) > 1 else ""
            if not path:
                continue
            change = "new" if status.startswith("A") else "changed"
            note = f"{status} — {truncate(subject, 60)}" if subject else status
            items.append({"ref": path, "change": change, "note": note})
        if not items:
            continue
        summary = (body.splitlines()[0] if body else "") or subject or ""
        tasks.append(
            {
                "title": title,
                "request": title,
                "summary": truncate(summary or f"Committed {sha[:7]}.", 160),
                "items": items[:25],
            }
        )
    return {"updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "tasks": tasks}


def generate() -> Dict[str, Any]:
    graph = build_graph()
    write_json(OUT / "graph.json", graph)
    write_json(OUT / "architecture.json", architecture_doc())
    write_descriptions(graph)
    write_json(OUT / "recent-work.json", build_recent_work())
    map_js = (ROOT / "scripts/floorplan_map.js").read_text(encoding="utf-8")
    index_html = INDEX_HTML.replace("__MAP_JS__", map_js)
    index_html = index_html.replace("__GRAPH_JSON__", json.dumps(graph, indent=2, ensure_ascii=False))
    (OUT / "index.html").write_text(index_html, encoding="utf-8")
    write_readme()
    return graph


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate(graph: Optional[Dict[str, Any]] = None, errors: Optional[List[str]] = None) -> List[str]:
    errors = errors if errors is not None else []
    graph = graph if graph is not None else (
        json.loads((OUT / "graph.json").read_text(encoding="utf-8")) if (OUT / "graph.json").exists() else {}
    )
    nodes = graph.get("nodes") or []
    ids = [n["id"] for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids in graph.json")

    all_ids = set(ids) | {s["id"] for s in graph.get("outsideServices", [])}
    for e in graph.get("edges", []):
        if e.get("from") not in all_ids:
            errors.append(f"edge from unknown node: {e.get('from')}")
        if e.get("to") not in all_ids:
            errors.append(f"edge to unknown node: {e.get('to')}")

    # Every server endpoint extracted from server/app.py must be on the map.
    endpoints = extract_endpoints()
    on_map = set()
    for n in nodes:
        for ep in n.get("endpoints", []):
            on_map.add((ep.get("method"), ep.get("path")))
    for e in endpoints:
        if (e["method"], e["path"]) not in on_map:
            errors.append(f"server endpoint missing from map: {e['method']} {e['path']}")

    # GUI requests must reach a server endpoint (or be the backend.json discovery file).
    for m in graph.get("requestToEndpoint", []):
        if not m.get("matched"):
            if m.get("guiRequest") == "backend.json":
                continue
            errors.append(f"GUI request {m.get('guiRequest')} has no server endpoint")

    # Every listed file must exist.
    for n in nodes:
        for f in n.get("files", []):
            if not (ROOT / f["path"]).exists():
                errors.append(f"node {n['id']}: file missing on disk: {f['path']}")

    # architecture.json: nodes must exist in the graph.
    arch_path = OUT / "architecture.json"
    if arch_path.exists():
        arch = json.loads(arch_path.read_text(encoding="utf-8"))
        for n in arch.get("nodes", []):
            if n["id"] not in set(ids):
                errors.append(f"architecture node missing from graph: {n['id']}")
            for ep in n.get("endpoints", []):
                if (ep.get("method"), ep.get("path")) not in on_map:
                    errors.append(f"architecture node {n['id']}: unknown endpoint {ep.get('method')} {ep.get('path')}")

    # descriptions/*.json exist for every architecture node.
    ddir = OUT / "descriptions"
    if arch_path.exists():
        for n in arch.get("nodes", []):
            p = ddir / f"{n['id']}.json"
            if not p.exists():
                errors.append(f"missing description: {p.name}")
                continue
            try:
                doc = json.loads(p.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                errors.append(f"description {p.name}: invalid JSON: {exc}")
                continue
            if not doc.get("name") or not doc.get("description"):
                errors.append(f"description {p.name}: missing name/description")

    if not (OUT / "index.html").exists() or len((OUT / "index.html").read_text(encoding="utf-8")) < 1000:
        errors.append("floorplan/index.html missing or too small")

    if not (OUT / "recent-work.json").exists():
        errors.append("missing: floorplan/recent-work.json")
    else:
        try:
            rw = json.loads((OUT / "recent-work.json").read_text(encoding="utf-8"))
            if not isinstance(rw.get("tasks"), list):
                errors.append("floorplan/recent-work.json: missing tasks list")
        except json.JSONDecodeError as exc:
            errors.append(f"floorplan/recent-work.json: invalid JSON: {exc}")

    # The map logic lives in scripts/floorplan_map.js; it must parse as JS.
    map_js_path = ROOT / "scripts/floorplan_map.js"
    if not map_js_path.exists():
        errors.append("missing: scripts/floorplan_map.js")
    else:
        try:
            subprocess.run(["node", "--check", str(map_js_path)], cwd=ROOT, capture_output=True, check=True, timeout=30)
        except subprocess.CalledProcessError as exc:
            detail = ""
            if isinstance(exc.stderr, bytes):
                detail = exc.stderr.decode("utf-8", "replace").strip()
            elif exc.stderr:
                detail = str(exc.stderr)
            errors.append("floorplan_map.js: node --check failed: " + (detail[:200] or str(exc)))
        except FileNotFoundError:
            errors.append("node not available to check floorplan_map.js")
        except Exception as exc:
            errors.append("floorplan_map.js: node --check error: " + str(exc))
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Build or validate the Jo Floorplan map.")
    parser.add_argument("--check", action="store_true", help="validate artifacts + wiring only")
    args = parser.parse_args(argv)

    if args.check:
        graph_path = OUT / "graph.json"
        if not graph_path.exists():
            errors = ["floorplan/graph.json missing — run: python scripts/build_floorplan.py"]
        else:
            graph = json.loads(graph_path.read_text(encoding="utf-8"))
            errors = validate(graph)
        if errors:
            print("Floorplan validation FAILED:")
            for e in errors:
                print("  - " + e)
            return 1
        graph = json.loads(graph_path.read_text(encoding="utf-8"))
        wired = sum(1 for m in graph["requestToEndpoint"] if m["matched"])
        print(
            f"Floorplan validation OK: {graph['counts']['nodes']} parts, "
            f"{graph['counts']['files']} files, {graph['counts']['endpoints']} endpoints, "
            f"{graph['counts']['edges']} connections, {graph['counts']['screens']} screens; "
            f"{wired}/{len(graph['requestToEndpoint'])} GUI requests wired to server endpoints."
        )
        return 0

    graph = generate()
    errors = validate(graph)
    if errors:
        print("Floorplan validation FAILED after generation:")
        for e in errors:
            print("  - " + e)
        return 1
    print(
        f"Floorplan generated in {OUT}: {graph['counts']['nodes']} parts, "
        f"{graph['counts']['files']} files, {graph['counts']['endpoints']} endpoints, "
        f"{graph['counts']['edges']} connections, {graph['counts']['screens']} screens. "
        f"Open: {OUT / 'index.html'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
