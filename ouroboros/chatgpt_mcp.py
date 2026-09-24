"""ChatGPT-facing MCP gateway for Jo.

Jo's own supervisor remains the 24/7 runtime. This process only exposes the
existing ToolRegistry to ChatGPT through MCP Streamable HTTP.

The gateway is deliberately read-only by default. Set JO_MCP_ALLOW_WRITE=1
or provide an explicit allowlist to expose mutating tools.

Run:
    python -m ouroboros.chatgpt_mcp
"""

from __future__ import annotations

import os
import pathlib
from typing import Any, Dict, List, Set

from mcp.server import Server
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, PaginatedRequestParams, TextContent, Tool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


READ_ONLY_TOOLS: Set[str] = {
    "repo_read",
    "repo_list",
    "drive_read",
    "drive_list",
    "git_status",
    "git_diff",
    "web_search",
    "browse_page",
    "analyze_screenshot",
    "chat_history",
    "knowledge_read",
    "vault_read",
    "vault_list",
    "vault_search",
    "vault_backlinks",
    "vault_outlinks",
    "vault_graph",
    "system_map",
    "get_task_ontology",
    "get_ontology_insights",
}

WRITE_TOOLS: Set[str] = {
    "repo_write_commit",
    "repo_commit_push",
    "drive_write",
    "run_shell",
    "code_edit",
    "code_edit_lines",
    "ai_code_edit",
    "schedule_task",
    "update_scratchpad",
    "update_identity",
    "send_owner_message",
    "request_restart",
    "promote_to_stable",
    "vault_create",
    "vault_write",
    "vault_delete",
    "task_create",
    "worktree_create",
    "worktree_remove",
}


def repo_dir() -> pathlib.Path:
    return pathlib.Path(
        os.environ.get("JO_MCP_REPO_DIR", os.environ.get("REPO_DIR", pathlib.Path.cwd()))
    ).resolve()


def data_root() -> pathlib.Path:
    return pathlib.Path(
        os.environ.get(
            "JO_MCP_DATA_ROOT",
            os.environ.get("DATA_ROOT", pathlib.Path.home() / ".jo_data"),
        )
    ).resolve()


def build_registry() -> Any:
    from ouroboros.tools.registry import ToolRegistry

    return ToolRegistry(repo_dir=repo_dir(), drive_root=data_root())


def allowed_names(registry: Any) -> Set[str]:
    explicit = os.environ.get("JO_MCP_TOOL_ALLOWLIST", "").strip()
    if explicit:
        names = {v.strip() for v in explicit.split(",") if v.strip()}
    else:
        names = set(READ_ONLY_TOOLS)
        if os.environ.get("JO_MCP_ALLOW_WRITE", "0") == "1":
            names.update(WRITE_TOOLS)

    available = set(registry.available_tools())
    return names & available


class BearerAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/", "/healthz"}:
            return await call_next(request)

        if os.environ.get("JO_MCP_ALLOW_ANONYMOUS", "0") == "1":
            return await call_next(request)

        expected = os.environ.get("JO_MCP_AUTH_TOKEN", "").strip()
        if not expected:
            return JSONResponse(
                {"ok": False, "error": "JO_MCP_AUTH_TOKEN is not configured"},
                status_code=503,
            )

        supplied = request.headers.get("authorization", "")
        if supplied != "Bearer " + expected:
            return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)

        return await call_next(request)


def build_server() -> Server:
    registry = build_registry()
    names = allowed_names(registry)
    schemas: Dict[str, Dict[str, Any]] = {}

    tools: List[Tool] = []
    for entry in registry._entries.values():
        if entry.name not in names:
            continue
        schema = entry.schema
        schemas[entry.name] = schema
        tools.append(
            Tool(
                name=entry.name,
                description=str(schema.get("description") or "")[:2000],
                inputSchema=schema.get(
                    "parameters",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                ),
            )
        )

    async def list_tools(
        ctx: Any,
        params: PaginatedRequestParams | None,
    ) -> ListToolsResult:
        return ListToolsResult(tools=tools)

    async def call_tool(ctx: Any, params: CallToolRequestParams) -> CallToolResult:
        if params.name not in schemas:
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=f"Tool '{params.name}' is not exposed by this Jo gateway.",
                    )
                ],
                isError=True,
            )

        args = params.arguments or {}
        result = registry.execute(params.name, dict(args))
        failed = str(result).startswith("⚠️ TOOL_") or str(result).startswith("⚠️ TOOL_ARG")
        return CallToolResult(
            content=[TextContent(type="text", text=str(result))],
            isError=failed,
        )

    return Server(
        os.environ.get("JO_MCP_SERVER_NAME", "Jo"),
        on_list_tools=list_tools,
        on_call_tool=call_tool,
    )


def build_app() -> Any:
    from starlette.responses import PlainTextResponse

    server = build_server()
    app = server.streamable_http_app(
        streamable_http_path="/mcp",
        stateless_http=True,
        json_response=True,
        host=os.environ.get("JO_MCP_HOST", "127.0.0.1"),
    )

    async def root(request: Request):
        return JSONResponse(
            {
                "service": "jo-chatgpt-mcp",
                "endpoint": "/mcp",
                "free_only": True,
                "write_enabled": os.environ.get("JO_MCP_ALLOW_WRITE", "0") == "1",
            }
        )

    async def health(request: Request):
        registry = build_registry()
        names = allowed_names(registry)
        return JSONResponse(
            {
                "ok": True,
                "service": "jo-chatgpt-mcp",
                "tools": len(names),
                "free_only": True,
                "write_enabled": os.environ.get("JO_MCP_ALLOW_WRITE", "0") == "1",
                "repo_dir": str(repo_dir()),
                "data_root": str(data_root()),
            }
        )

    async def health_plain(request: Request):
        return PlainTextResponse("ok")

    app.router.routes.append(__import__("starlette.routing", fromlist=["Route"]).Route("/", root, methods=["GET"]))
    app.router.routes.append(__import__("starlette.routing", fromlist=["Route"]).Route("/healthz", health, methods=["GET"]))
    app.add_middleware(BearerAuthMiddleware)
    return app


app = build_app()


def main() -> None:
    import uvicorn

    host = os.environ.get("JO_MCP_HOST", "127.0.0.1")
    port = int(os.environ.get("JO_MCP_PORT", "8000"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
