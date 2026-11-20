# Jo Floorplan map

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
