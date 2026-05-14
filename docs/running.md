# Running the Servers

## Option 1 — stdio transport (local only)

The default transport. No API key required. Intended for local development and testing with tools that speak stdio MCP directly.

**Greet server:**
```bash
uv run -m mcp_examples.server
```

**Contact server:**
```bash
uv run -m mcp_examples.contacts
```

**Weather server:**
```bash
OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather
```

> stdio transport does not require an API key and is not accessible remotely. The Weather server always requires `OPENWEATHER_API_KEY` regardless of transport.

## Option 2 — HTTP transport (authenticated remote access)

Starts the server as an HTTP endpoint. All requests require a valid `X-API-Key` header. See [authentication.md](authentication.md) for how to get and use your API key.

**Greet server:**
```bash
uv run -m mcp_examples.server --transport streamable-http --port 8000
```

**Contact server:**
```bash
uv run -m mcp_examples.contacts --transport streamable-http --port 8000
```

**Weather server:**
```bash
OPENWEATHER_API_KEY=<key> uv run -m mcp_examples.weather --transport streamable-http --port 8000
```

The server endpoint is `http://localhost:8000/mcp`.

### Custom database path

**macOS:**
```bash
MCP_DB_PATH=/tmp/mcp_keys.db uv run -m mcp_examples.server --transport streamable-http --port 8000
```

**Windows (PowerShell):**
```powershell
$env:MCP_DB_PATH = "C:\data\mcp_keys.db"
uv run -m mcp_examples.server --transport streamable-http --port 8000
```

## Option 3 — FastMCP CLI

The `fastmcp` CLI provides three commands for working with the servers without writing any client code.

### Inspect a server's tools

Shows all registered tools, their parameters, and descriptions without starting the server:

```bash
# Greet server
uv run fastmcp inspect mcp_examples/server.py

# Contact server
uv run fastmcp inspect mcp_examples/contacts.py
```

### Interactive testing with MCP Inspector

Starts the server and opens the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) UI in your browser. No API key required — `dev` mode uses stdio transport and bypasses the HTTP middleware.

```bash
# Greet server
uv run fastmcp dev mcp_examples/server.py

# Contact server
uv run fastmcp dev mcp_examples/contacts.py
```

The Inspector UI opens at `http://localhost:5173` by default.

### Connect to a running remote server

Creates a local proxy to an already-running HTTP server:

```bash
uv run fastmcp run http://localhost:8000/mcp --transport streamable-http
```
