---
title: MCP Server
created: 2026-03-23T14:00:00.000000+00:00
modified: 2026-03-23T14:00:00.000000+00:00
type: concept
status: active
tags: [mcp, protocol, tools, interop, ruvector]
---

# MCP Server

Exposes Jo's tools via Model Context Protocol (MCP). Other AI agents can use Jo's 138 tools through a standard protocol.

## Protocol

MCP uses JSON-RPC 2.0 over stdio:

- `initialize` — handshake, returns server info
- `tools/list` — list all available tools with schemas
- `tools/call` — execute a tool with arguments
- `resources/list` — list available resources
- `resources/read` — read a resource (status, constitution)

## Module

`ouroboros/mcp_server.py`

## Usage

```python
from ouroboros.mcp_server import MCPServer

mcp = MCPServer(repo_dir=repo_dir)
resp = mcp.handle_request({
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {"name": "repo_read", "arguments": {"file_path": "README.md"}}
})
```

For stdio mode: `python -m ouroboros.mcp_server`

## Exposed Resources

- `jo://status` — server info, tool count
- `jo://constitution` — constitution.json content

## Integration

- Auto-loads all 138 tools from the registry
- Delegates tool execution to `ToolRegistry.execute()`
- Error responses follow JSON-RPC 2.0 spec

## Design Decisions

- Minimal implementation (no streaming, no sampling)
- Stdio-first (most common MCP transport)
- Resources provide read-only access to Jo's state
- No authentication (local use by default)

Related: [[tools]], [[architecture]], [[principle_3__llm-first]]
