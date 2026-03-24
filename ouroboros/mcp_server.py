"""MCP Tool Exposure — Expose Jo's tools via Model Context Protocol.

Inspired by RuVector's MCP server and SAFLA's MCP integration:
- Standard MCP protocol for tool discovery and execution
- Other AI agents can use Jo's tools via MCP
- Enables agent-to-agent communication
- Tools are exposed as MCP tool definitions with JSON schemas

MCP uses JSON-RPC 2.0 over stdio or HTTP.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

log = logging.getLogger(__name__)


class MCPServer:
    """Minimal MCP server exposing Jo's tools.

    Supports:
    - tools/list: List available tools
    - tools/call: Execute a tool
    - resources/list: List available resources
    - resources/read: Read a resource
    """

    def __init__(self, repo_dir: Path, drive_root: Optional[Path] = None):
        self.repo_dir = Path(repo_dir)
        self.drive_root = Path(drive_root) if drive_root else self.repo_dir
        self._tools: Dict[str, Any] = {}
        self._resources: Dict[str, Any] = {}
        self._load_tools()

    def _load_tools(self) -> None:
        """Load tools from the registry."""
        try:
            from ouroboros.tools.registry import ToolRegistry

            registry = ToolRegistry(repo_dir=self.repo_dir, drive_root=self.drive_root)
            for schema in registry.schemas():
                name = schema.get("function", {}).get("name", "")
                if name:
                    self._tools[name] = {
                        "name": name,
                        "description": schema.get("function", {}).get("description", ""),
                        "inputSchema": schema.get("function", {}).get("parameters", {}),
                    }
            log.info("MCP: Loaded %d tools", len(self._tools))
        except Exception as e:
            log.warning("MCP: Failed to load tools: %s", e)

    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an MCP JSON-RPC 2.0 request."""
        method = request.get("method", "")
        params = request.get("params", {})
        req_id = request.get("id", 0)

        try:
            if method == "initialize":
                return self._response(
                    req_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {"listChanged": False}},
                        "serverInfo": {"name": "jo-mcp", "version": "6.4.0"},
                    },
                )
            elif method == "tools/list":
                return self._response(req_id, {"tools": list(self._tools.values())})
            elif method == "tools/call":
                return self._handle_tool_call(req_id, params)
            elif method == "resources/list":
                return self._response(req_id, {"resources": list(self._resources.values())})
            elif method == "resources/read":
                return self._handle_resource_read(req_id, params)
            else:
                return self._error(req_id, -32601, f"Method not found: {method}")
        except Exception as e:
            return self._error(req_id, -32603, str(e))

    def _handle_tool_call(self, req_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool call."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if tool_name not in self._tools:
            return self._error(req_id, -32602, f"Unknown tool: {tool_name}")

        try:
            from ouroboros.tools.registry import ToolRegistry

            registry = ToolRegistry(repo_dir=self.repo_dir, drive_root=self.drive_root)
            result = registry.execute(tool_name, arguments)
            return self._response(req_id, {"content": [{"type": "text", "text": str(result)}]})
        except Exception as e:
            return self._response(
                req_id,
                {
                    "content": [{"type": "text", "text": f"⚠️ Tool error: {e}"}],
                    "isError": True,
                },
            )

    def _handle_resource_read(self, req_id: int, params: Dict[str, Any]) -> Dict[str, Any]:
        """Read a resource."""
        uri = params.get("uri", "")

        # Built-in resources
        if uri == "jo://status":
            return self._response(
                req_id,
                {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(
                                {
                                    "tools": len(self._tools),
                                    "server": "jo-mcp",
                                    "version": "6.4.0",
                                }
                            ),
                        }
                    ]
                },
            )
        elif uri == "jo://constitution":
            try:
                const = (self.repo_dir / "constitution.json").read_text(encoding="utf-8")
                return self._response(
                    req_id, {"contents": [{"uri": uri, "mimeType": "application/json", "text": const}]}
                )
            except Exception:
                return self._error(req_id, -32602, "Constitution not found")
        else:
            return self._error(req_id, -32602, f"Unknown resource: {uri}")

    @staticmethod
    def _response(req_id: int, result: Any) -> Dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    @staticmethod
    def _error(req_id: int, code: int, message: str) -> Dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": message},
        }

    def run_stdio(self) -> None:
        """Run MCP server on stdin/stdout."""
        log.info("MCP server starting on stdio...")
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                response = self.handle_request(request)
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except json.JSONDecodeError:
                sys.stdout.write(json.dumps(self._error(0, -32700, "Parse error")) + "\n")
                sys.stdout.flush()

    def get_tools_summary(self) -> str:
        """Get human-readable tools summary."""
        lines = ["## MCP Exposed Tools", "", f"**Total:** {len(self._tools)}", ""]
        for name, tool in sorted(self._tools.items()):
            desc = tool["description"][:80] if tool["description"] else "No description"
            lines.append(f"- **{name}**: {desc}")
        return "\n".join(lines)


if __name__ == "__main__":
    import os

    repo_dir = Path(os.environ.get("REPO_DIR", "."))
    logging.basicConfig(level=logging.INFO)
    server = MCPServer(repo_dir=repo_dir)
    server.run_stdio()
